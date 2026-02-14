#!/usr/bin/env python3
"""
Data ingestion validation script: verify Harmony credentials, optional live fetch,
and that fetched data is in the required format and processed correctly.

Usage (from project root):
  python -m tests.run_ingestion_validation
  INGESTION_LIVE=1 python -m tests.run_ingestion_validation   # run live Harmony fetch

Expects .env with BEARER_TOKEN or EARTHDATA_USERNAME + EARTHDATA_PASSWORD.
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def main():
    print("AERIS Data Ingestion Validation")
    print("=" * 50)

    # 1. Config / credentials
    from config import settings
    has_token = bool(getattr(settings, "bearer_token", None))
    has_user_pwd = bool(getattr(settings, "earthdata_username", None)) and bool(
        getattr(settings, "earthdata_password", None)
    )
    if not has_token and not has_user_pwd:
        print("FAIL: No BEARER_TOKEN or EARTHDATA_USERNAME/EARTHDATA_PASSWORD in .env")
        return 1
    print("OK: Earthdata credentials present")

    # 2. Token resolution
    from services.harmony_service import get_bearer_token, build_tempo_rangeset_url, TEMPO_COLLECTION_IDS
    token = get_bearer_token()
    if not token:
        print("FAIL: get_bearer_token() returned None")
        return 1
    print("OK: Bearer token resolved")

    # 3. URL format (per Harmony notebook)
    start = datetime.now(timezone.utc) - timedelta(hours=1)
    end = datetime.now(timezone.utc)
    url = build_tempo_rangeset_url(
        TEMPO_COLLECTION_IDS["NO2"],
        "all",
        -120.0, 34.0, -118.0, 36.0,
        start, end,
        output_format="image/tiff",
    )
    assert "subset=lon(" in url and "subset=lat(" in url and "subset=time(" in url
    print("OK: Rangeset URL format valid")

    # 4. Optional live fetch
    if not os.environ.get("INGESTION_LIVE"):
        print("SKIP: Live fetch (set INGESTION_LIVE=1 to run)")
        print("Done.")
        return 0

    from services.harmony_service import fetch_tempo_geotiff
    from services.raster_normalizer import geotiff_to_grid_rows

    # Try last completed hour first; if "no matching granules", try same hour 7 days ago (TEMPO may have delay)
    end_time = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start_time = end_time - timedelta(hours=1)
    path = fetch_tempo_geotiff(
        "NO2",
        west=-118.5, south=33.5, east=-117.5, north=34.5,
        start_time=start_time, end_time=end_time,
    )
    if not path:
        start_time = start_time - timedelta(days=7)
        end_time = end_time - timedelta(days=7)
        path = fetch_tempo_geotiff(
            "NO2",
            west=-118.5, south=33.5, east=-117.5, north=34.5,
            start_time=start_time, end_time=end_time,
        )
    if not path:
        print("WARN: Harmony returned no GeoTIFF.")
        print("      Common causes: 403 (token), 400 'No matching granules' (try different time), or wrong env.")
        print("      Your token is from production (urs.earthdata.nasa.gov); do not set HARMONY_USE_UAT.")
        return 0
    try:
        import rasterio
        with rasterio.open(path) as src:
            assert src.count >= 1 and src.width > 0 and src.height > 0
        print("OK: GeoTIFF fetched and readable")

        required_keys = {"timestamp", "gas_type", "geom_wkt", "pollution_value", "severity_level"}
        row_count = 0
        for chunk in geotiff_to_grid_rows(path, "NO2", start_time, max_cells=200):
            for row in chunk:
                assert required_keys.issubset(row.keys())
                assert 0 <= row["severity_level"] <= 4
                assert row["geom_wkt"].startswith("POLYGON((")
                row_count += 1
        print(f"OK: Processed {row_count} grid rows with required format")
    finally:
        if path and os.path.exists(path):
            os.unlink(path)

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
