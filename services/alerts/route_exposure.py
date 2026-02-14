"""
Compute UPES along a saved route (origin -> dest line) for alert scoring and history.
"""
from pathlib import Path
from typing import List, Optional, Tuple

from services.route_optimization.graph_builder import get_latest_upes_raster_path
from services.route_optimization.upes_sampling import sample_upes_along_line_mean_max


def route_line_coords(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
) -> List[Tuple[float, float]]:
    """Return [(origin_lon, origin_lat), (dest_lon, dest_lat)] for WGS84 line."""
    return [(float(origin_lon), float(origin_lat)), (float(dest_lon), float(dest_lat))]


def compute_upes_along_saved_route(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    raster_path: Optional[Path] = None,
    step_m: float = 50.0,
) -> Tuple[float, float]:
    """
    Sample UPES along the straight line from origin to destination.
    Returns (mean_upes, max_upes) in [0, 1]. Uses latest raster if raster_path is None.
    """
    coords = route_line_coords(origin_lat, origin_lon, dest_lat, dest_lon)
    path = raster_path if raster_path is not None else get_latest_upes_raster_path()
    return sample_upes_along_line_mean_max(path, coords, step_m=step_m)
