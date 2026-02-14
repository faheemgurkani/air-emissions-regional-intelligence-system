"""
Application configuration from environment variables.
"""
from typing import Dict, Optional
from pydantic_settings import BaseSettings


# UPES gas weights (default); sum should be 1.0
UPES_DEFAULT_WEIGHTS: Dict[str, float] = {
    "NO2": 0.3,
    "PM": 0.35,
    "O3": 0.2,
    "CH2O": 0.1,
    "AI": 0.05,
}


class Settings(BaseSettings):
    """Settings loaded from environment (and .env)."""

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/aeris"

    # Redis (empty = no cache)
    redis_url: Optional[str] = "redis://localhost:6379/0"

    # JWT
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours

    # Object storage (env-driven: minio | s3)
    object_storage_provider: Optional[str] = None  # "minio" or "s3"
    object_storage_endpoint_url: Optional[str] = None  # MinIO: http://localhost:9000
    object_storage_bucket: str = "aeris-netcdf"
    aws_region: Optional[str] = None
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None

    # Optional feature flags
    persist_pollution_grid: bool = False

    # Earthdata / Harmony (production: urs.earthdata.nasa.gov, harmony.earthdata.nasa.gov)
    bearer_token: Optional[str] = None
    earthdata_username: Optional[str] = None
    earthdata_password: Optional[str] = None

    # Existing
    weather_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None

    # UPES (Unified Pollution Exposure Score)
    upes_output_base: Optional[str] = None  # default: outputs/ under project root
    upes_grid_resolution_deg: float = 0.05  # degrees per cell
    upes_bbox_west: Optional[float] = None  # override TEMPO bbox
    upes_bbox_south: Optional[float] = None
    upes_bbox_east: Optional[float] = None
    upes_bbox_north: Optional[float] = None
    upes_traffic_alpha: float = 0.1  # TF = 1 + alpha * traffic_density, in [0.05, 0.2]
    upes_ema_lambda: Optional[float] = 0.6  # None = disable EMA
    upes_alert_threshold: float = 0.5  # FinalScore > threshold = high-risk
    upes_enabled: bool = True  # set False to skip compute_upes_hourly

    # Route optimization (pollution-aware OSM graph)
    route_optimization_enabled: bool = True
    route_osm_buffer_km: float = 3.0  # bbox buffer around origin/dest for OSM fetch
    route_result_cache_ttl: int = 300  # seconds
    route_graph_cache_ttl: int = 600  # seconds for OSM graph by bbox

    # Alerts & Personalization
    alerts_enabled: bool = True
    alerts_deterioration_base_pct: float = 0.15  # 15% for Normal; scaled by sensitivity
    alerts_hazard_threshold: float = 0.85  # UPES >= this along route = hazard
    alerts_wind_speed_min_kph: float = 5.0
    alerts_wind_angle_deg: float = 45.0  # wind toward route within this angle
    alerts_n8n_webhook_url: Optional[str] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()

# Production Earthdata / Harmony base URLs (do not use UAT in production)
CMR_BASE_URL = "https://cmr.earthdata.nasa.gov"
HARMONY_BASE_URL = "https://harmony.earthdata.nasa.gov"
URSA_TOKEN_URL = "https://urs.earthdata.nasa.gov/api/users/token"
URSA_TOKENS_URL = "https://urs.earthdata.nasa.gov/api/users/tokens"
