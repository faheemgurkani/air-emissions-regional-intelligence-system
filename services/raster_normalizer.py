"""
Convert GeoTIFF from Harmony to pollution_grid rows: raster → cells with WKT geom and severity.
"""
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Union

import numpy as np
import rasterio
from rasterio.transform import xy

from pollution_utils import classify_pollution_level

DEFAULT_CHUNK_SIZE = 2000
DEFAULT_MAX_CELLS = 5000


def _pixel_bounds(
    transform: Any,
    col: int,
    row: int,
) -> tuple:
    """Return (lon_min, lat_min, lon_max, lat_max) for a pixel center (col, row)."""
    lon_c, lat_c = xy(transform, row, col)
    # Approximate pixel size from transform (cell size)
    dx = abs(transform[0])
    dy = abs(transform[4])
    if dx <= 0:
        dx = 0.025
    if dy <= 0:
        dy = 0.025
    return (
        lon_c - dx / 2,
        lat_c - dy / 2,
        lon_c + dx / 2,
        lat_c + dy / 2,
    )


def _cell_to_wkt(lon_min: float, lat_min: float, lon_max: float, lat_max: float) -> str:
    """Build WKT POLYGON for a small box (closed ring)."""
    return (
        f"POLYGON(({lon_min} {lat_min}, {lon_max} {lat_min}, "
        f"{lon_max} {lat_max}, {lon_min} {lat_max}, {lon_min} {lat_min}))"
    )


def geotiff_to_grid_rows(
    geotiff_path: Union[str, Path],
    gas_type: str,
    timestamp: datetime,
    *,
    subsample: Optional[int] = None,
    max_cells: int = DEFAULT_MAX_CELLS,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> Iterator[List[Dict[str, Any]]]:
    """
    Read GeoTIFF with rasterio; yield chunks of grid row dicts for pollution_grid bulk insert.

    Each row dict has: timestamp, gas_type, geom_wkt, pollution_value, severity_level.
    Optionally subsample (e.g. subsample=4 → every 4th row/col) to limit cell count.
    """
    path = Path(geotiff_path)
    if not path.exists():
        raise FileNotFoundError(f"GeoTIFF not found: {path}")

    with rasterio.open(path) as src:
        band = src.read(1)
        transform = src.transform
        height, width = band.shape

    # Subsample step: if subsample is None, choose step to cap total cells roughly
    total_pixels = height * width
    if subsample is not None:
        step = max(1, subsample)
    else:
        step = 1
        if total_pixels > max_cells:
            # approximate: step so that (height/step)*(width/step) <= max_cells
            step = max(1, int((total_pixels / max_cells) ** 0.5))

    chunk: List[Dict[str, Any]] = []
    count = 0
    for i in range(0, height, step):
        if count >= max_cells:
            break
        for j in range(0, width, step):
            if count >= max_cells:
                break
            val = float(band[i, j])
            if np.isnan(val):
                continue
            lon_min, lat_min, lon_max, lat_max = _pixel_bounds(transform, j, i)
            wkt = _cell_to_wkt(lon_min, lat_min, lon_max, lat_max)
            _, severity = classify_pollution_level(val, gas_type)
            chunk.append({
                "timestamp": timestamp,
                "gas_type": gas_type,
                "geom_wkt": wkt,
                "pollution_value": val,
                "severity_level": severity,
            })
            count += 1
            if len(chunk) >= chunk_size:
                yield chunk
                chunk = []
    if chunk:
        yield chunk
