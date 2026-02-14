"""
Tests for NetCDF resolver (DATA_LAYER): resolve_netcdf_paths_for_gases from DB + object storage.
"""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import NetcdfFile
from netcdf_resolver import resolve_netcdf_paths_for_gases


@pytest.mark.asyncio
async def test_resolve_returns_empty_when_storage_not_configured():
    with patch("netcdf_resolver.is_configured", return_value=False):
        session = AsyncMock(spec=AsyncSession)
        overrides, temp_paths = await resolve_netcdf_paths_for_gases(session, ["NO2", "O3"])
        assert overrides == {}
        assert temp_paths == []
        session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_returns_empty_when_no_rows_in_db():
    with patch("netcdf_resolver.is_configured", return_value=True):
        session = AsyncMock(spec=AsyncSession)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result_mock)

        overrides, temp_paths = await resolve_netcdf_paths_for_gases(session, ["NO2"])
        assert overrides == {}
        assert temp_paths == []


@pytest.mark.asyncio
async def test_resolve_skips_gas_on_download_failure():
    with patch("netcdf_resolver.is_configured", return_value=True):
        with patch("netcdf_resolver.download_netcdf_to_path", side_effect=Exception("download failed")):
            session = AsyncMock(spec=AsyncSession)
            row = NetcdfFile(
                id=1,
                file_name="no2.nc",
                bucket_path="bucket/no2.nc",
                timestamp=datetime.utcnow(),
                gas_type="NO2",
            )
            result_mock = MagicMock()
            result_mock.scalar_one_or_none.return_value = row
            session.execute = AsyncMock(return_value=result_mock)

            overrides, temp_paths = await resolve_netcdf_paths_for_gases(session, ["NO2"])
            assert overrides == {}
            assert temp_paths == []


@pytest.mark.asyncio
async def test_resolve_returns_override_and_temp_path_on_success():
    with patch("netcdf_resolver.is_configured", return_value=True):
        with patch("netcdf_resolver.download_netcdf_to_path", return_value="/tmp/fake_no2.nc"):
            session = AsyncMock(spec=AsyncSession)
            row = NetcdfFile(
                id=1,
                file_name="no2.nc",
                bucket_path="bucket/no2.nc",
                timestamp=datetime.utcnow(),
                gas_type="NO2",
            )
            result_mock = MagicMock()
            result_mock.scalar_one_or_none.return_value = row
            session.execute = AsyncMock(return_value=result_mock)

            overrides, temp_paths = await resolve_netcdf_paths_for_gases(session, ["NO2"])
            assert overrides == {"NO2": "/tmp/fake_no2.nc"}
            assert temp_paths == ["/tmp/fake_no2.nc"]
