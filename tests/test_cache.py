"""
Tests for Redis cache layer (DATA_LAYER): key builders, cache_get/cache_set, weather and pollutant cached helpers.
"""
import json
from unittest.mock import AsyncMock

import pytest

from cache import (
    TTL_POLLUTANT_MOVEMENT,
    TTL_WEATHER,
    cache_get,
    cache_set,
    get_pollutant_movement_cached,
    get_weather_cached,
    key_hotspots,
    key_route_exposure,
    key_route_optimized,
)


class TestCacheKeyBuilders:
    def test_key_weather_format(self):
        key = key_weather(34.0, -118.0, 3)
        assert key == "weather:34.0:-118.0:3"

    def test_key_pollutant_movement_format(self):
        key = key_pollutant_movement(34.0, -118.0)
        assert key == "pollutant_movement:34.0:-118.0"

    def test_key_hotspots_deterministic_for_same_gases(self):
        k1 = key_hotspots(34.0, -118.0, 0.3, ["NO2", "O3"])
        k2 = key_hotspots(34.0, -118.0, 0.3, ["O3", "NO2"])
        assert k1 == k2
        assert "hotspots:" in k1

    def test_key_route_exposure_includes_coords_and_gas_hash(self):
        key = key_route_exposure(34.0, -118.0, 35.0, -119.0, ["NO2"])
        assert "route_exposure:" in key
        assert "34.0" in key and "35.0" in key

    def test_key_route_optimized_includes_mode(self):
        key = key_route_optimized(34.0, -118.0, 35.0, -119.0, "commute")
        assert "route_opt:" in key
        assert "commute" in key

    def test_key_route_optimized_normalizes_mode(self):
        key = key_route_optimized(34.0, -118.0, 35.0, -119.0, "  Jogger  ")
        assert "jogger" in key


def key_weather(lat: float, lon: float, days: int) -> str:
    return f"weather:{lat}:{lon}:{days}"


def key_pollutant_movement(lat: float, lon: float) -> str:
    return f"pollutant_movement:{lat}:{lon}"


class TestCacheGetSet:
    @pytest.mark.asyncio
    async def test_cache_get_returns_none_when_redis_none(self):
        assert await cache_get(None, "any") is None

    @pytest.mark.asyncio
    async def test_cache_get_returns_none_on_miss(self, mock_redis):
        mock_redis.get.return_value = None
        assert await cache_get(mock_redis, "missing") is None

    @pytest.mark.asyncio
    async def test_cache_get_deserializes_json(self, mock_redis):
        data = {"a": 1, "b": "two"}
        mock_redis.get.return_value = json.dumps(data)
        result = await cache_get(mock_redis, "k")
        assert result == data

    @pytest.mark.asyncio
    async def test_cache_set_skips_when_redis_none(self):
        await cache_set(None, "k", {"x": 1}, 60)
        # no raise

    @pytest.mark.asyncio
    async def test_cache_set_calls_setex_with_ttl(self, mock_redis):
        await cache_set(mock_redis, "k", {"v": 1}, 120)
        mock_redis.setex.assert_called_once()
        args = mock_redis.setex.call_args[0]
        assert args[0] == "k"
        assert args[1] == 120
        assert json.loads(args[2]) == {"v": 1}


class TestGetWeatherCached:
    @pytest.mark.asyncio
    async def test_miss_calls_fetch_and_caches(self, mock_redis, sample_weather_data):
        fetch_fn = lambda lat, lon, days: sample_weather_data
        mock_redis.get.return_value = None
        result = await get_weather_cached(mock_redis, 34.0, -118.0, 1, fetch_fn)
        assert result == sample_weather_data
        mock_redis.setex.assert_called_once()
        assert mock_redis.setex.call_args[0][1] == TTL_WEATHER

    @pytest.mark.asyncio
    async def test_hit_returns_cached(self, mock_redis, sample_weather_data):
        mock_redis.get.return_value = json.dumps(sample_weather_data)
        fetch_fn = lambda lat, lon, days: {"never": "called"}
        result = await get_weather_cached(mock_redis, 34.0, -118.0, 1, fetch_fn)
        assert result == sample_weather_data


class TestGetPollutantMovementCached:
    @pytest.mark.asyncio
    async def test_miss_calls_fetch_and_caches(self, mock_redis, sample_pollutant_movement):
        fetch_fn = lambda lat, lon: sample_pollutant_movement
        mock_redis.get.return_value = None
        result = await get_pollutant_movement_cached(mock_redis, 34.0, -118.0, fetch_fn)
        assert result == sample_pollutant_movement
        mock_redis.setex.assert_called_once()
        assert mock_redis.setex.call_args[0][1] == TTL_POLLUTANT_MOVEMENT

    @pytest.mark.asyncio
    async def test_hit_returns_cached(self, mock_redis, sample_pollutant_movement):
        mock_redis.get.return_value = json.dumps(sample_pollutant_movement)
        fetch_fn = lambda lat, lon: {"never": "called"}
        result = await get_pollutant_movement_cached(mock_redis, 34.0, -118.0, fetch_fn)
        assert result == sample_pollutant_movement
