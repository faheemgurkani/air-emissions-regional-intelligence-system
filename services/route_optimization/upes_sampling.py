"""
Sample UPES raster along a line geometry (e.g. road edge); return mean exposure in [0, 1].
"""
from pathlib import Path
from typing import List, Optional, Tuple, Union

import numpy as np

# Fallback when no raster or all samples invalid
DEFAULT_UPES_FALLBACK = 0.5

# Approximate meters per degree at equator
M_PER_DEG_LAT = 111_320
M_PER_DEG_LON_AT_EQUATOR = 111_320


def _haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Approximate distance in meters between two WGS84 points."""
    import math
    R = 6_371_000  # Earth radius m
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _resample_line(
    coords: List[Tuple[float, float]],
    step_m: float,
) -> List[Tuple[float, float]]:
    """Resample line (list of (lon, lat)) at step_m intervals. Returns (lon, lat) list."""
    if not coords or step_m <= 0:
        return list(coords) if coords else []
    out: List[Tuple[float, float]] = [coords[0]]
    acc = 0.0
    for i in range(1, len(coords)):
        lon1, lat1 = coords[i - 1]
        lon2, lat2 = coords[i]
        seg_m = _haversine_m(lon1, lat1, lon2, lat2)
        if seg_m <= 0:
            continue
        acc += seg_m
        while acc >= step_m:
            t = step_m / acc if acc > 0 else 1.0
            # interpolate
            lon = lon1 + t * (lon2 - lon1)
            lat = lat1 + t * (lat2 - lat1)
            out.append((lon, lat))
            acc -= step_m
            lon1, lat1 = lon, lat
        if acc > 0:
            lon1, lat1 = lon2, lat2
    if coords and out[-1] != coords[-1]:
        out.append(coords[-1])
    return out


def sample_upes_along_line(
    raster_path: Optional[Union[str, Path]],
    line_coords: List[Tuple[float, float]],
    step_m: float = 50.0,
    fallback: float = DEFAULT_UPES_FALLBACK,
) -> float:
    """
    Sample UPES raster along a line (list of (lon, lat)). Resamples line at step_m,
    samples raster at each point, returns mean of valid values in [0, 1].
    If raster_path is None or missing, or no valid samples, return fallback.
    """
    if not line_coords:
        return fallback
    path = Path(raster_path) if raster_path else None
    if not path or not path.exists():
        return fallback
    points = _resample_line(line_coords, step_m)
    if not points:
        return fallback
    try:
        import rasterio
        from rasterio.transform import rowcol
        values = []
        with rasterio.open(path) as src:
            for lon, lat in points:
                r, c = rowcol(src.transform, lon, lat)
                if 0 <= r < src.height and 0 <= c < src.width:
                    try:
                        v = float(src.read(1, window=((r, r + 1), (c, c + 1)))[0, 0])
                        if not np.isnan(v):
                            values.append(max(0.0, min(1.0, v)))
                    except Exception:
                        pass
        if not values:
            return fallback
        return float(np.mean(values))
    except Exception:
        return fallback


def sample_upes_along_line_mean_max(
    raster_path: Optional[Union[str, Path]],
    line_coords: List[Tuple[float, float]],
    step_m: float = 50.0,
    fallback: float = DEFAULT_UPES_FALLBACK,
) -> Tuple[float, float]:
    """
    Sample UPES raster along a line; return (mean, max) of valid values in [0, 1].
    If no valid samples, return (fallback, fallback).
    """
    if not line_coords:
        return fallback, fallback
    path = Path(raster_path) if raster_path else None
    if not path or not path.exists():
        return fallback, fallback
    points = _resample_line(line_coords, step_m)
    if not points:
        return fallback, fallback
    try:
        import rasterio
        from rasterio.transform import rowcol
        values = []
        with rasterio.open(path) as src:
            for lon, lat in points:
                r, c = rowcol(src.transform, lon, lat)
                if 0 <= r < src.height and 0 <= c < src.width:
                    try:
                        v = float(src.read(1, window=((r, r + 1), (c, c + 1)))[0, 0])
                        if not np.isnan(v):
                            values.append(max(0.0, min(1.0, v)))
                    except Exception:
                        pass
        if not values:
            return fallback, fallback
        return float(np.mean(values)), float(np.max(values))
    except Exception:
        return fallback, fallback
