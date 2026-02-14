"""
Integration tests for DATA INGESTION: real Harmony token, optional live fetch, format validation.
Requires .env with BEARER_TOKEN or EARTHDATA_USERNAME + EARTHDATA_PASSWORD.
Run with: pytest tests/test_data_ingestion_integration.py -v -m integration
Or: pytest tests/test_data_ingestion_integration.py -v (skips live fetch unless INGESTION_LIVE=1)
"""
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# Add project root
import sys
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _has_earthdata_credentials() -> bool:
    try:
        from config import settings
        return bool(getattr(settings, "bearer_token", None)) or (
            bool(getattr(settings, "earthdata_username", None))
            and bool(getattr(settings, "earthdata_password", None))
        )
    except Exception:
        return False


@pytest.mark.integration
class TestHarmonyTokenIntegration:
    """Token resolution with real .env credentials."""

    def test_get_bearer_token_returns_non_empty(self):
        if not _has_earthdata_credentials():
            pytest.skip("No BEARER_TOKEN or EARTHDATA_USERNAME/EARTHDATA_PASSWORD in .env")
        from services.harmony_service import get_bearer_token
        token = get_bearer_token()
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 20


@pytest.mark.integration
class TestRangesetUrlFormat:
    """Built URL matches Harmony OGC API Coverages pattern (notebook)."""

    def test_built_url_structure(self):
        from services.harmony_service import (
            HARMONY_BASE_URL,
            build_tempo_rangeset_url,
            TEMPO_COLLECTION_IDS,
            DEFAULT_VARIABLE,
        )
        start = datetime.now(timezone.utc) - timedelta(hours=1)
        end = datetime.now(timezone.utc)
        url = build_tempo_rangeset_url(
            TEMPO_COLLECTION_IDS["NO2"],
            DEFAULT_VARIABLE,
            -120.0, 34.0, -118.0, 36.0,
            start, end,
            output_format="image/tiff",
        )
        assert url.startswith(HARMONY_BASE_URL)
        assert "ogc-api-coverages/1.0.0" in url
        assert "rangeset" in url
        assert "subset=lon(" in url
        assert "subset=lat(" in url
        assert "subset=time(" in url
        assert "format=image/tiff" in url


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("INGESTION_LIVE"),
    reason="Set INGESTION_LIVE=1 to run live Harmony fetch",
)
class TestLiveFetchAndProcess:
    """Live fetch one gas and validate GeoTIFF + grid row format."""

    def test_fetch_tempo_geotiff_returns_valid_geotiff(self):
        if not _has_earthdata_credentials():
            pytest.skip("No Earthdata credentials in .env")
        from services.harmony_service import fetch_tempo_geotiff
        # Small bbox, last completed hour
        end_time = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        start_time = end_time - timedelta(hours=1)
        path = fetch_tempo_geotiff(
            "NO2",
            west=-118.5, south=33.5, east=-117.5, north=34.5,
            start_time=start_time, end_time=end_time,
        )
        if path is None:
            pytest.skip("Harmony returned no data (e.g. no granules for time/bbox)")
        try:
            import rasterio
            with rasterio.open(path) as src:
                assert src.count >= 1
                assert src.width > 0 and src.height > 0
                data = src.read(1)
                assert data is not None
        finally:
            if path and os.path.exists(path):
                os.unlink(path)

    def test_fetched_geotiff_produces_valid_grid_rows(self):
        if not _has_earthdata_credentials():
            pytest.skip("No Earthdata credentials in .env")
        from services.harmony_service import fetch_tempo_geotiff
        from services.raster_normalizer import geotiff_to_grid_rows
        end_time = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        start_time = end_time - timedelta(hours=1)
        path = fetch_tempo_geotiff(
            "NO2",
            west=-118.5, south=33.5, east=-117.5, north=34.5,
            start_time=start_time, end_time=end_time,
        )
        if path is None:
            pytest.skip("Harmony returned no data")
        try:
            ts = start_time
            row_count = 0
            required_keys = {"timestamp", "gas_type", "geom_wkt", "pollution_value", "severity_level"}
            for chunk in geotiff_to_grid_rows(path, "NO2", ts, max_cells=100):
                for row in chunk:
                    assert required_keys.issubset(row.keys())
                    assert row["gas_type"] == "NO2"
                    assert 0 <= row["severity_level"] <= 4
                    assert row["geom_wkt"].startswith("POLYGON((")
                    row_count += 1
            assert row_count > 0
        finally:
            if path and os.path.exists(path):
                os.unlink(path)
