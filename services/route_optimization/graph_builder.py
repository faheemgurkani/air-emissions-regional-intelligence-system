"""
Build a pollution-weighted OSM graph: fetch OSMnx graph for bbox, sample UPES along edges, assign weight.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config import settings
from services.route_optimization.upes_sampling import sample_upes_along_line
from services.route_optimization.weights import get_weights, mode_modifier
from services.upes.storage import upes_output_base


def get_latest_upes_raster_path() -> Optional[Path]:
    """Return path to latest final_score GeoTIFF, or None if none found."""
    base = upes_output_base()
    final_dir = base / "hourly_scores" / "final_score"
    if not final_dir.exists():
        return None
    tifs = sorted(final_dir.glob("final_score_*.tif"), key=lambda p: p.stat().st_mtime, reverse=True)
    return tifs[0] if tifs else None


def _edge_geometry_to_coords(geom: Any) -> List[Tuple[float, float]]:
    """Extract (lon, lat) list from edge geometry (Shapely LineString or similar)."""
    if geom is None:
        return []
    if hasattr(geom, "coords"):
        return [(float(c[0]), float(c[1])) for c in geom.coords]
    if hasattr(geom, "__iter__") and not isinstance(geom, (str, bytes)):
        return [(float(p[0]), float(p[1])) for p in geom]
    return []


def _speed_kph(edge_data: Dict[str, Any]) -> float:
    """Infer speed in km/h from edge (maxspeed or default by highway)."""
    maxspeed = edge_data.get("maxspeed")
    if maxspeed is not None:
        if isinstance(maxspeed, (int, float)):
            return float(maxspeed)
        s = str(maxspeed).strip().upper().replace("MPH", "").strip()
        try:
            v = float(s)
            if "mph" in str(maxspeed).lower():
                v *= 1.60934
            return v
        except ValueError:
            pass
    highway = (edge_data.get("highway") or "").lower()
    if isinstance(highway, list):
        highway = highway[0] if highway else ""
    if highway in ("motorway", "motorway_link"):
        return 100.0
    if highway in ("trunk", "trunk_link"):
        return 80.0
    if highway in ("primary", "primary_link"):
        return 60.0
    if highway in ("secondary", "secondary_link"):
        return 50.0
    if highway in ("cycleway", "path"):
        return 15.0
    if highway in ("footway", "pedestrian"):
        return 5.0
    return 25.0


def build_weighted_graph(
    north: float,
    south: float,
    east: float,
    west: float,
    mode: str = "commute",
    upes_raster_path: Optional[Path] = None,
) -> Any:
    """
    Fetch OSM graph for bbox (north, south, east, west), assign edge weights using UPES + mode.
    Returns NetworkX MultiDiGraph with edge attribute 'weight' (and length, mean_upes, time_h for metrics).
    """
    import osmnx as ox
    import networkx as nx

    G = ox.graph_from_bbox(north, south, east, west, network_type="all", simplify=True, retain_all=False)
    if G is None or G.number_of_edges() == 0:
        return G
    raster_path = upes_raster_path or get_latest_upes_raster_path()
    alpha, beta, gamma = get_weights(mode)
    # Normalize so cost is scale-invariant (optional; we use raw for comparison)
    for u, v, key, data in G.edges(keys=True, data=True):
        geom = data.get("geometry")
        coords = _edge_geometry_to_coords(geom)
        if not coords and "length" in data:
            # fallback: midpoint from nodes
            try:
                u_lon = G.nodes[u].get("x")
                u_lat = G.nodes[u].get("y")
                v_lon = G.nodes[v].get("x")
                v_lat = G.nodes[v].get("y")
                if u_lon is not None and v_lon is not None:
                    coords = [(u_lon, u_lat), (v_lon, v_lat)]
            except Exception:
                pass
        mean_upes = sample_upes_along_line(raster_path, coords) if coords else 0.5
        length_m = float(data.get("length", 0)) or 1.0
        distance_km = length_m / 1000.0
        speed = _speed_kph(data)
        time_h = distance_km / max(speed, 5.0) if speed > 0 else distance_km / 5.0
        mod = mode_modifier(data, mode)
        cost = alpha * mean_upes + beta * distance_km + gamma * time_h
        data["weight"] = mod * cost
        data["length_m"] = length_m
        data["mean_upes"] = mean_upes
        data["time_h"] = time_h
    return G
