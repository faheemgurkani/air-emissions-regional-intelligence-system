"""
Tests for object storage layer (DATA_LAYER): S3/MinIO is_configured, upload_netcdf, download_netcdf_to_path.
Unit tests only; integration tests require real MinIO/S3.
"""
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from storage import download_netcdf_to_path, is_configured, upload_netcdf


class TestIsConfigured:
    def test_false_when_provider_unset(self):
        with patch("storage.settings") as s:
            s.object_storage_provider = None
            s.object_storage_endpoint_url = "http://localhost:9000"
            s.aws_access_key_id = "x"
            s.aws_secret_access_key = "y"
            assert is_configured() is False

    def test_false_when_provider_invalid(self):
        with patch("storage.settings") as s:
            s.object_storage_provider = "gcs"
            assert is_configured() is False

    def test_minio_requires_endpoint(self):
        with patch("storage.settings") as s:
            s.object_storage_provider = "minio"
            s.object_storage_endpoint_url = None
            assert is_configured() is False
            s.object_storage_endpoint_url = "http://localhost:9000"
            assert is_configured() is True

    def test_s3_requires_credentials(self):
        with patch("storage.settings") as s:
            s.object_storage_provider = "s3"
            s.aws_access_key_id = None
            s.aws_secret_access_key = "y"
            assert is_configured() is False
            s.aws_access_key_id = "x"
            s.aws_secret_access_key = "y"
            assert is_configured() is True


class TestUploadNetcdf:
    def test_raises_when_not_configured(self):
        with patch("storage._client", return_value=None):
            with pytest.raises(RuntimeError, match="not configured"):
                upload_netcdf(b"data", "key.nc")

    def test_raises_file_not_found_for_missing_path(self):
        with patch("storage._client") as mock_client:
            mock_client.return_value = object()
            with pytest.raises(FileNotFoundError):
                upload_netcdf("/nonexistent/path.nc", "key.nc")


class TestDownloadNetcdfToPath:
    def test_raises_when_not_configured(self):
        with patch("storage._client", return_value=None):
            with pytest.raises(RuntimeError, match="not configured"):
                download_netcdf_to_path("any/key.nc")
