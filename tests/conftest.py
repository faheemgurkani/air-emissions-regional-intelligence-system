"""
Pytest configuration and shared fixtures for AERIS DATA_LAYER tests.
"""
import os
import sys
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# Ensure project root is on path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Pytest-asyncio mode
pytest_plugins = ["pytest_asyncio"]


def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: mark test as async (pytest-asyncio).")
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration (needs DB/Redis; skip if env not set).",
    )


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Fake async Redis for cache tests (get/setex return OK)."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock(return_value=True)
    redis.ping = AsyncMock(return_value=True)
    return redis


@pytest.fixture
def sample_weather_data() -> dict:
    """Sample weather API response for cache tests."""
    return {
        "location": {"name": "Test City", "lat": 34.0, "lon": -118.0},
        "current": {"temp_c": 22, "humidity": 50, "wind_kph": 10},
        "forecast": {"forecastday": []},
    }


@pytest.fixture
def sample_pollutant_movement() -> dict:
    """Sample pollutant movement prediction for cache tests."""
    return {
        "location": {"lat": 34.0, "lon": -118.0},
        "predictions_next_3h": [
            {"time": "12:00", "displacement_km": 5, "predicted_air_quality": "moderate"},
        ],
    }


# Optional: real DB session for integration tests (skip if DATABASE_URL not set or not postgres)
def _get_test_db_url() -> str | None:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url or "postgresql" not in url:
        return None
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


@pytest.fixture(scope="session")
def database_url() -> str | None:
    return _get_test_db_url()


@pytest.fixture
def skip_if_no_db(database_url):
    """Skip the test if DATABASE_URL is not set (no Postgres)."""
    if not database_url:
        pytest.skip("DATABASE_URL not set or not PostgreSQL — skip DB integration test")
