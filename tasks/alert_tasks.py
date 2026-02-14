"""
Celery tasks: UPES-based saved route scoring (history) and alert pipeline.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

from celery_app import app
from sqlalchemy import create_engine, desc, func
from sqlalchemy.orm import sessionmaker, joinedload

from config import settings
from database.models import AlertLog, RouteExposureHistory, SavedRoute, User
from services.alerts.detection import run_detection
from services.alerts.route_exposure import compute_upes_along_saved_route
from services.route_optimization.graph_builder import get_latest_upes_raster_path

logger = logging.getLogger(__name__)


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


@app.task(bind=True, name="tasks.alert_tasks.compute_saved_route_upes_scores")
def compute_saved_route_upes_scores(self):
    """
    For each saved route: sample UPES along origin->dest line, insert into route_exposure_history,
    update saved_routes.last_upes_score and last_upes_updated_at.
    Run after compute_upes_hourly when UPES rasters are available.
    """
    raster_path = get_latest_upes_raster_path()
    if not raster_path or not raster_path.exists():
        logger.info("No UPES raster; skip compute_saved_route_upes_scores")
        return {"status": "skipped", "reason": "no_raster"}
    session = _get_sync_session()
    try:
        routes = session.query(SavedRoute).all()
        now = datetime.now(timezone.utc)
        count = 0
        for route in routes:
            try:
                mean_upes, max_upes = compute_upes_along_saved_route(
                    route.origin_lat,
                    route.origin_lon,
                    route.dest_lat,
                    route.dest_lon,
                    raster_path=raster_path,
                )
                hist = RouteExposureHistory(
                    route_id=route.id,
                    timestamp=now,
                    upes_score=round(mean_upes, 6),
                    max_upes_along_route=round(max_upes, 6) if max_upes is not None else None,
                    score_source="upes",
                )
                session.add(hist)
                route.last_upes_score = round(mean_upes, 6)
                route.last_upes_updated_at = now
                session.add(route)
                count += 1
            except Exception as e:
                logger.warning("UPES route score failed for route %s: %s", route.id, e)
        session.commit()
        logger.info("Computed UPES scores for %s saved routes", count)
        return {"status": "ok", "routes_updated": count}
    finally:
        session.close()


def _channels_from_preferences(prefs: Optional[dict]) -> List[str]:
    """Build list of channel names from notification_preferences dict (e.g. email, push, in_app)."""
    if not prefs or not isinstance(prefs, dict):
        return ["in_app"]
    out = []
    if prefs.get("email"):
        out.append("email")
    if prefs.get("push"):
        out.append("push")
    if prefs.get("in_app", True):
        out.append("in_app")
    return out if out else ["in_app"]


def _prev_and_min_upes(session, route_id: int, since: datetime) -> Tuple[Optional[float], Optional[float]]:
    """Return (previous score, recent min score) for route from history."""
    rows = (
        session.query(RouteExposureHistory)
        .filter(RouteExposureHistory.route_id == route_id)
        .order_by(desc(RouteExposureHistory.timestamp))
        .limit(2)
        .all()
    )
    prev = rows[1].upes_score if len(rows) >= 2 else None
    min_row = (
        session.query(func.min(RouteExposureHistory.upes_score))
        .filter(RouteExposureHistory.route_id == route_id, RouteExposureHistory.timestamp >= since)
        .scalar()
    )
    recent_min = float(min_row) if min_row is not None else None
    return prev, recent_min


@app.task(bind=True, name="tasks.alert_tasks.run_alert_pipeline")
def run_alert_pipeline(self):
    """
    For each saved route: get current/prev UPES, weather at midpoint; run detection;
    insert alert_log rows; POST payload to n8n webhook if configured.
    """
    if not getattr(settings, "alerts_enabled", True):
        logger.info("Alerts disabled; skip run_alert_pipeline")
        return {"status": "skipped", "reason": "disabled"}
    session = _get_sync_session()
    try:
        routes = (
            session.query(SavedRoute)
            .options(joinedload(SavedRoute.user))
            .all()
        )
        since_24h = datetime.now(timezone.utc) - timedelta(hours=24)
        webhook_url = getattr(settings, "alerts_n8n_webhook_url", None) or ""
        webhook_url = webhook_url.strip()
        n8n_payload: List[Dict[str, Any]] = []
        alert_count = 0
        for route in routes:
            user = route.user
            if not user:
                continue
            current_upes = route.last_upes_score
            if current_upes is None:
                continue
            max_upes = current_upes  # use same; or query latest history row for max_upes_along_route
            hist_rows = (
                session.query(RouteExposureHistory)
                .filter(RouteExposureHistory.route_id == route.id)
                .order_by(desc(RouteExposureHistory.timestamp))
                .limit(2)
                .all()
            )
            if hist_rows and hist_rows[0].max_upes_along_route is not None:
                max_upes = hist_rows[0].max_upes_along_route
            prev_upes, recent_min_upes = _prev_and_min_upes(session, route.id, since_24h)
            wind_kph = None
            wind_degree = None
            try:
                from weather_service import get_weather_data
                mid_lat = (route.origin_lat + route.dest_lat) / 2.0
                mid_lon = (route.origin_lon + route.dest_lon) / 2.0
                w = get_weather_data(mid_lat, mid_lon, days=1)
                if w and "error" not in w and w.get("current"):
                    wind_kph = float(w["current"].get("wind_kph", 0))
                    wind_degree = float(w["current"].get("wind_degree", 0))
            except Exception as e:
                logger.debug("Weather for alert pipeline: %s", e)
            mid_lat = (route.origin_lat + route.dest_lat) / 2.0
            mid_lon = (route.origin_lon + route.dest_lon) / 2.0
            alerts = run_detection(
                user_id=user.id,
                route_id=route.id,
                current_upes=current_upes,
                max_upes=max_upes,
                prev_upes=prev_upes,
                recent_min_upes=recent_min_upes,
                user_sensitivity_level=user.exposure_sensitivity_level,
                wind_kph=wind_kph,
                wind_degree=wind_degree,
                route_mid_lat=mid_lat,
                route_mid_lon=mid_lon,
                source_lat=None,
                source_lon=None,
            )
            channels = _channels_from_preferences(user.notification_preferences)
            for a in alerts:
                log = AlertLog(
                    user_id=user.id,
                    route_id=route.id,
                    alert_type=a["type"],
                    score_before=a.get("score_before"),
                    score_after=a.get("score_after"),
                    threshold=a.get("threshold"),
                    alert_metadata=a.get("metadata") or {},
                    notified_channels=channels,
                )
                session.add(log)
                session.flush()
                alert_count += 1
                n8n_payload.append({
                    "alert_id": log.id,
                    "user_id": user.id,
                    "route_id": route.id,
                    "alert_type": a["type"],
                    "message": _alert_message(a),
                    "score_before": a.get("score_before"),
                    "score_after": a.get("score_after"),
                    "channels": channels,
                })
        session.commit()
        if webhook_url and n8n_payload:
            try:
                resp = requests.post(
                    webhook_url,
                    json={"alerts": n8n_payload, "timestamp": datetime.now(timezone.utc).isoformat()},
                    timeout=15,
                )
                if resp.status_code >= 400:
                    logger.warning("n8n webhook POST failed: %s %s", resp.status_code, resp.text)
            except Exception as e:
                logger.warning("n8n webhook POST error: %s", e)
        logger.info("Alert pipeline: %s alerts logged", alert_count)
        return {"status": "ok", "alerts_count": alert_count}
    finally:
        session.close()


def _alert_message(a: Dict[str, Any]) -> str:
    """Short human-readable message for n8n."""
    t = a.get("type", "")
    if t == "route_deterioration":
        return f"Route exposure increased from {a.get('score_before', 0):.2f} to {a.get('score_after', 0):.2f}."
    if t == "hazard":
        return f"High pollution (UPES {a.get('score_after', 0):.2f}) detected along your route."
    if t == "wind_shift":
        return "Wind may be moving pollution toward your route."
    if t == "time_based":
        return "Recent exposure is higher than your recent best; consider traveling at a different time."
    return f"Alert: {t}"
