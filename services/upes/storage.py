"""
UPES output: write GeoTIFF rasters and JSON logs.
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

from config import settings
from services.upes.grid_aggregation import GridSpec


def upes_output_base() -> Path:
    """Base directory for UPES outputs; default outputs/ under project root."""
    base = getattr(settings, "upes_output_base", None)
    if base:
        return Path(base)
    return Path(__file__).resolve().parents[2] / "outputs"


def ensure_dirs(base: Path) -> None:
    """Create raw, normalized, hourly_scores/satellite_score, hourly_scores/final_score, logs."""
    (base / "raw").mkdir(parents=True, exist_ok=True)
    (base / "normalized").mkdir(parents=True, exist_ok=True)
    (base / "hourly_scores" / "satellite_score").mkdir(parents=True, exist_ok=True)
    (base / "hourly_scores" / "final_score").mkdir(parents=True, exist_ok=True)
    (base / "logs").mkdir(parents=True, exist_ok=True)


def write_geotiff(
    path: Path,
    data: np.ndarray,
    spec: GridSpec,
) -> None:
    """Write 2D array as GeoTIFF with WGS84 transform from GridSpec."""
    import rasterio
    from rasterio.crs import CRS
    from rasterio.transform import from_bounds

    transform = from_bounds(
        spec.west, spec.south, spec.east, spec.north,
        spec.nx, spec.ny,
    )
    arr = np.asarray(data, dtype=np.float32)
    if arr.ndim == 2:
        arr = arr[np.newaxis, ...]
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=spec.ny,
        width=spec.nx,
        count=arr.shape[0],
        dtype=arr.dtype,
        crs=CRS.from_epsg(4326),
        transform=transform,
        nodata=np.nan,
    ) as dst:
        for k in range(arr.shape[0]):
            dst.write(arr[k], k + 1)


def write_upes_rasters(
    timestamp: datetime,
    satellite_score: np.ndarray,
    final_score: np.ndarray,
    spec: GridSpec,
) -> Dict[str, str]:
    """
    Write satellite_score and final_score GeoTIFFs for the hour; return paths used.
    """
    base = upes_output_base()
    ensure_dirs(base)
    ts = timestamp.strftime("%Y%m%d_%H")
    sat_path = base / "hourly_scores" / "satellite_score" / f"satellite_score_{ts}.tif"
    final_path = base / "hourly_scores" / "final_score" / f"final_score_{ts}.tif"
    write_geotiff(sat_path, satellite_score, spec)
    write_geotiff(final_path, final_score, spec)
    return {"satellite_score": str(sat_path), "final_score": str(final_path)}


def write_upes_log(
    timestamp: datetime,
    satellite_score_mean: float,
    humidity_factor: float,
    wind_factor: float,
    traffic_factor: float,
    final_score_mean: float,
    granule_ids: Optional[list] = None,
) -> str:
    """Write JSON log for the run; return path."""
    base = upes_output_base()
    ensure_dirs(base)
    ts = timestamp.strftime("%Y%m%d_%H")
    path = base / "logs" / f"upes_{ts}.json"
    payload = {
        "timestamp": timestamp.isoformat(),
        "granule_ids": granule_ids or [],
        "satellite_score": round(satellite_score_mean, 4),
        "humidity_factor": round(humidity_factor, 4),
        "wind_factor": round(wind_factor, 4),
        "traffic_factor": round(traffic_factor, 4),
        "final_score": round(final_score_mean, 4),
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    return str(path)
