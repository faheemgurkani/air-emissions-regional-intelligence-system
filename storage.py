"""
Object storage abstraction for S3 / MinIO. NetCDF files stored by key; metadata in DB.
"""
import os
import tempfile
from pathlib import Path
from typing import Union

from config import settings


def _client():
    """Create boto3 S3 client (MinIO or AWS)."""
    import boto3
    from botocore.config import Config

    provider = (settings.object_storage_provider or "").lower()
    if provider not in ("minio", "s3"):
        return None

    kwargs = {
        "service_name": "s3",
        "region_name": settings.aws_region or "us-east-1",
        "aws_access_key_id": settings.aws_access_key_id or "",
        "aws_secret_access_key": settings.aws_secret_access_key or "",
        "config": Config(signature_version="s3v4"),
    }
    if provider == "minio" and settings.object_storage_endpoint_url:
        kwargs["endpoint_url"] = settings.object_storage_endpoint_url
    return boto3.client(**kwargs)


def is_configured() -> bool:
    """True if object storage provider is set and credentials look present."""
    p = (settings.object_storage_provider or "").lower()
    if p not in ("minio", "s3"):
        return False
    if p == "minio":
        return bool(settings.object_storage_endpoint_url)
    return bool(settings.aws_access_key_id and settings.aws_secret_access_key)


def upload_netcdf(source: Union[str, Path, bytes], key: str) -> str:
    """
    Upload file or bytes to bucket. Returns the key (bucket_path).
    """
    client = _client()
    if not client:
        raise RuntimeError("Object storage not configured")
    bucket = settings.object_storage_bucket
    extra = {"ContentType": "application/octet-stream"}
    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.is_file():
            raise FileNotFoundError(str(path))
        client.upload_file(str(path), bucket, key, ExtraArgs=extra)
    else:
        import io
        client.upload_fileobj(io.BytesIO(source), bucket, key, ExtraArgs=extra)
    return key


def download_netcdf_to_path(key: str) -> str:
    """
    Download object to a temporary file and return its path. Caller should unlink when done.
    """
    client = _client()
    if not client:
        raise RuntimeError("Object storage not configured")
    bucket = settings.object_storage_bucket
    fd, path = tempfile.mkstemp(suffix=".nc")
    os.close(fd)
    try:
        client.download_file(bucket, key, path)
    except Exception:
        try:
            os.unlink(path)
        except Exception:
            pass
        raise
    return path


def get_presigned_url(key: str, expire_sec: int = 3600) -> str:
    """Generate presigned URL for GET (optional)."""
    client = _client()
    if not client:
        raise RuntimeError("Object storage not configured")
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.object_storage_bucket, "Key": key},
        ExpiresIn=expire_sec,
    )
