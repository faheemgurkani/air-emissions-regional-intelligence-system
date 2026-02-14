"""
Application configuration from environment variables.
"""
from typing import Optional
from pydantic_settings import BaseSettings


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
