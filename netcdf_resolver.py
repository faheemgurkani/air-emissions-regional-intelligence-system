"""
Resolve latest NetCDF file per gas from DB + object storage; fallback to TempData scan.
"""
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import NetcdfFile
from storage import download_netcdf_to_path, is_configured


async def resolve_netcdf_paths_for_gases(
    session: AsyncSession, gases: List[str]
) -> Tuple[Dict[str, str], List[str]]:
    """
    For each gas, query latest netcdf_files row and download to temp file.
    Returns (gas -> local_path, list of temp paths to unlink later).
    """
    overrides: Dict[str, str] = {}
    temp_paths: List[str] = []
    if not is_configured():
        return overrides, temp_paths

    for gas in gases:
        stmt = (
            select(NetcdfFile)
            .where(NetcdfFile.gas_type == gas)
            .order_by(NetcdfFile.timestamp.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            continue
        try:
            path = download_netcdf_to_path(row.bucket_path)
            overrides[gas] = path
            temp_paths.append(path)
        except Exception:
            continue

    return overrides, temp_paths
