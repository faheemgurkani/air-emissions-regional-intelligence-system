"""
Redis cache helpers: key builders and async get/set with TTL.
Redis is optional (REDIS_URL empty = no cache).
"""
import hashlib
import json
from typing import Any, Optional

# Cache key prefixes and TTLs (seconds)
TTL_WEATHER = 600
TTL_POLLUTANT_MOVEMENT = 600
TTL_HOTSPOTS = 300
TTL_ROUTE_EXPOSURE = 300


def _key_weather(lat: float, lon: float, days: int) -> str:
    return f"weather:{lat}:{lon}:{days}"


def _key_pollutant_movement(lat: float, lon: float) -> str:
    return f"pollutant_movement:{lat}:{lon}"


def key_hotspots(lat: float, lon: float, radius: float, gases: list[str]) -> str:
    h = hashlib.sha256(",".join(sorted(gases)).encode()).hexdigest()[:12]
    return f"hotspots:{lat}:{lon}:{radius}:{h}"


def key_route_exposure(origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float, gases: list[str]) -> str:
    h = hashlib.sha256(",".join(sorted(gases)).encode()).hexdigest()[:12]
    return f"route_exposure:{origin_lat}:{origin_lon}:{dest_lat}:{dest_lon}:{h}"


def key_route_optimized(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    mode: str,
) -> str:
    """Cache key for pollution-optimized route result."""
    m = (mode or "commute").strip().lower()
    return f"route_opt:{start_lat}:{start_lon}:{end_lat}:{end_lon}:{m}"


async def cache_get(redis: Any, key: str) -> Optional[Any]:
    """Return deserialized value if key exists, else None."""
    if redis is None:
        return None
    try:
        raw = await redis.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception:
        return None


async def cache_set(redis: Any, key: str, value: Any, ttl: int) -> None:
    """Serialize value and set with TTL."""
    if redis is None:
        return
    try:
        await redis.setex(key, ttl, json.dumps(value, default=str))
    except Exception:
        pass


async def get_weather_cached(redis: Any, lat: float, lon: float, days: int, fetch_fn: Any) -> dict:
    """Return weather from cache or fetch and cache."""
    key = _key_weather(lat, lon, days)
    cached = await cache_get(redis, key)
    if cached is not None:
        return cached
    data = fetch_fn(lat, lon, days)
    await cache_set(redis, key, data, TTL_WEATHER)
    return data


async def get_pollutant_movement_cached(redis: Any, lat: float, lon: float, fetch_fn: Any) -> dict:
    """Return pollutant movement from cache or fetch and cache."""
    key = _key_pollutant_movement(lat, lon)
    cached = await cache_get(redis, key)
    if cached is not None:
        return cached
    data = fetch_fn(lat, lon)
    await cache_set(redis, key, data, TTL_POLLUTANT_MOVEMENT)
    return data
