"""
Celery tasks: TEMPO hourly fetch, raster → pollution_grid, optional S3 audit, Redis last_update, recompute saved routes.
"""
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from geoalchemy2 import WKTElement

from celery_app import app
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from config import settings
from database.models import PollutionGrid, SavedRoute
from services.harmony_service import TEMPO_COLLECTION_IDS, fetch_tempo_geotiff
from services.raster_normalizer import geotiff_to_grid_rows

logger = logging.getLogger(__name__)

# Sync DB for Celery (workers run outside async context)
def _sync_database_url() -> str:
    url = getattr(settings, "database_url", "") or ""
    if "+asyncpg" in url:
        return url.replace("postgresql+asyncpg", "postgresql+psycopg2", 1)
    if url.startswith("postgresql://") and "+" not in url:
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


_engine = None
_Session = None


def _get_sync_session():
    global _engine, _Session
    if _engine is None:
        sync_url = _sync_database_url()
        _engine = create_engine(sync_url, pool_pre_ping=True)
        _Session = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    return _Session()


# Default CONUS-style bbox (TEMPO coverage); override via env if needed
DEFAULT_WEST = -125.0
DEFAULT_SOUTH = 24.0
DEFAULT_EAST = -66.0
DEFAULT_NORTH = 50.0


def _get_bbox():
    west = float(os.environ.get("TEMPO_BBOX_WEST", DEFAULT_WEST))
    south = float(os.environ.get("TEMPO_BBOX_SOUTH", DEFAULT_SOUTH))
    east = float(os.environ.get("TEMPO_BBOX_EAST", DEFAULT_EAST))
    north = float(os.environ.get("TEMPO_BBOX_NORTH", DEFAULT_NORTH))
    return west, south, east, north


@app.task(bind=True, name="tasks.pollution_tasks.fetch_tempo_hourly")
def fetch_tempo_hourly(self):
    """
    For each TEMPO gas: Harmony request → GeoTIFF → raster normalizer → bulk insert into pollution_grid.
    Optionally upload GeoTIFF to S3/MinIO; set Redis tempo:last_update; trigger recompute_saved_route_exposure.
    """
    west, south, east, north = _get_bbox()
    # Last completed hour in UTC
    end_time = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start_time = end_time - timedelta(hours=1)
    timestamp = start_time
    gases = list(TEMPO_COLLECTION_IDS.keys())
    inserted_total = 0

    for gas in gases:
        path: Optional[str] = None
        try:
            path = fetch_tempo_geotiff(gas, west, south, east, north, start_time, end_time)
            if not path:
                continue
            # Optional: upload to S3/MinIO for audit
            try:
                from storage import is_configured, upload_netcdf
                if is_configured():
                    key = f"audit/geotiff/{timestamp.strftime('%Y-%m-%d')}/{gas}_{timestamp.strftime('%H')}.tif"
                    upload_netcdf(path, key)
                    logger.info("Uploaded GeoTIFF to %s", key)
            except Exception as e:
                logger.warning("S3/MinIO upload skip: %s", e)
            # Normalize and bulk-insert
            session = _get_sync_session()
            try:
                per_gas = 0
                for chunk in geotiff_to_grid_rows(path, gas, timestamp):
                    rows = [
                        PollutionGrid(
                            timestamp=row["timestamp"],
                            gas_type=row["gas_type"],
                            geom=WKTElement(row["geom_wkt"], srid=4326),
                            pollution_value=row["pollution_value"],
                            severity_level=row["severity_level"],
                        )
                        for row in chunk
                    ]
                    session.add_all(rows)
                    session.commit()
                    per_gas += len(rows)
                    inserted_total += len(rows)
                logger.info("Inserted %s cells for %s", per_gas, gas)
            finally:
                session.close()
        except Exception as e:
            logger.exception("fetch_tempo_hourly failed for %s: %s", gas, e)
        finally:
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except Exception:
                    pass

    if inserted_total > 0:
        try:
            redis_url = getattr(settings, "redis_url", None)
            if redis_url:
                import redis
                r = redis.from_url(redis_url)
                r.setex("tempo:last_update", 3600, timestamp.isoformat())
                r.close()
        except Exception as e:
            logger.warning("Redis tempo:last_update set failed: %s", e)
        recompute_saved_route_exposure.apply_async()

    return {"inserted": inserted_total, "gases": gases}


@app.task(bind=True, name="tasks.pollution_tasks.recompute_saved_route_exposure")
def recompute_saved_route_exposure(self):
    """
    For each saved_route: build route line, query pollution_grid ST_Intersects for latest time window,
    compute exposure score, update last_computed_score and last_updated_at.
    """
    session = _get_sync_session()
    try:
        routes = session.query(SavedRoute).all()
        # Latest timestamp in pollution_grid for time window
        r = session.execute(
            text("SELECT MAX(timestamp) AS t FROM pollution_grid")
        ).fetchone()
        max_ts = r[0] if r else None
        if not max_ts:
            logger.info("No pollution_grid data; skip recompute")
            return
        for route in routes:
            try:
                # Build line WKT: origin -> dest (no SRID in WKT for ST_GeomFromText; use 4326)
                wkt = (
                    f"LINESTRING({route.origin_lon} {route.origin_lat}, "
                    f"{route.dest_lon} {route.dest_lat})"
                )
                # Average pollution_value where grid intersects route, for latest hour
                row = session.execute(
                    text("""
                        SELECT AVG(pollution_value) AS avg_val,
                               SUM(severity_level) AS sum_sev
                        FROM pollution_grid
                        WHERE ST_Intersects(geom, ST_GeomFromText(:wkt, 4326))
                          AND timestamp >= :ts_start AND timestamp <= :ts_end
                    """),
                    {
                        "wkt": wkt,
                        "ts_start": max_ts - timedelta(hours=1),
                        "ts_end": max_ts,
                    },
                ).fetchone()
                if row and row[0] is not None:
                    avg_val = float(row[0])
                    sum_sev = int(row[1] or 0)
                    # Simple score: blend of average value and severity sum (normalize as needed)
                    score = avg_val * 0.5 + sum_sev * 10.0
                    route.last_computed_score = round(score, 4)
                else:
                    route.last_computed_score = None
                route.last_updated_at = datetime.now(timezone.utc)
                session.add(route)
            except Exception as e:
                logger.warning("Recompute failed for route %s: %s", route.id, e)
        session.commit()
        logger.info("Recomputed exposure for %s saved routes", len(routes))
    finally:
        session.close()
