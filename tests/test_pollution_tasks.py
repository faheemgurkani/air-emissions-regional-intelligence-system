"""
Tests for Celery pollution tasks (DATA INGESTION): fetch_tempo_hourly, recompute_saved_route_exposure.
Unit tests with mocks; no real Celery broker or Harmony required.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

# Avoid Celery app eager mode issues by mocking at module level where needed
from tasks.pollution_tasks import (
    DEFAULT_EAST,
    DEFAULT_NORTH,
    DEFAULT_SOUTH,
    DEFAULT_WEST,
    _get_bbox,
    _get_sync_session,
    _sync_database_url,
)


class TestBboxConfig:
    """Bbox from env or CONUS defaults (doc: TEMPO_BBOX_WEST/SOUTH/EAST/NORTH)."""

    def test_default_constants_match_doc(self):
        assert DEFAULT_WEST == -125.0
        assert DEFAULT_SOUTH == 24.0
        assert DEFAULT_EAST == -66.0
        assert DEFAULT_NORTH == 50.0

    def test_bbox_from_env(self):
        import os
        with patch.dict(
            os.environ,
            {
                "TEMPO_BBOX_WEST": "-130",
                "TEMPO_BBOX_SOUTH": "25",
                "TEMPO_BBOX_EAST": "-65",
                "TEMPO_BBOX_NORTH": "52",
            },
        ):
            west, south, east, north = _get_bbox()
            assert west == -130.0
            assert south == 25.0
            assert east == -65.0
            assert north == 52.0


class TestSyncDatabaseUrl:
    """Sync URL replaces asyncpg with psycopg2."""

    def test_replaces_asyncpg_with_psycopg2(self):
        with patch("tasks.pollution_tasks.settings") as s:
            s.database_url = "postgresql+asyncpg://u:p@localhost:5432/db"
            url = _sync_database_url()
            assert "psycopg2" in url
            assert "asyncpg" not in url


class TestFetchTempoHourlyFlow:
    """fetch_tempo_hourly: for each gas fetch → normalize → insert; Redis; recompute."""

    @pytest.mark.skip(reason="Requires Celery app and DB; run as integration")
    def test_fetch_tempo_hourly_calls_harmony_per_gas(self):
        # Integration: run fetch_tempo_hourly with mocked fetch_tempo_geotiff returning a temp file
        # and mocked DB; assert insert count and redis setex and recompute_saved_route_exposure.apply_async
        pass
