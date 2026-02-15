"""
Shortest path on weighted graph; aggregate geometry and exposure/distance/time.
"""
from typing import Any, Dict, List, Optional, Tuple

import networkx as nx


def _nearest_node(G: Any, lat: float, lon: float) -> Optional[int]:
    """Return nearest graph node to (lat, lon). OSMnx uses (x=lon, y=lat) in nodes."""
    try:
        import osmnx as ox
        return ox.nearest_nodes(G, lon, lat)
    except Exception:
        return None


def _route_geometry_and_metrics(
    G: Any,
    path: List[int],
) -> Tuple[List[Tuple[float, float]], float, float, float, float]:
    """
    From node path, concatenate edge geometries and sum length, exposure, time, cost.
    Returns (coords as (lon,lat) list, total_exposure, distance_km, time_h, total_cost).
    """
    coords: List[Tuple[float, float]] = []
    total_exposure = 0.0
    distance_km = 0.0
    time_h = 0.0
    total_cost = 0.0
    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        edge = G.get_edge_data(u, v)
        if not edge:
            # MultiDiGraph can have multiple keys
            for key in list(G[u][v].keys()):
                edge = G[u][v][key]
                break
        if not edge:
            continue
        geom = edge.get("geometry")
        if geom is not None and hasattr(geom, "coords"):
            for c in geom.coords:
                coords.append((float(c[0]), float(c[1])))
        else:
            xu, yu = G.nodes[u].get("x"), G.nodes[u].get("y")
            xv, yv = G.nodes[v].get("x"), G.nodes[v].get("y")
            if xu is not None and yu is not None:
                coords.append((float(xu), float(yu)))
            if xv is not None and yv is not None:
                coords.append((float(xv), float(yv)))
        length_m = edge.get("length_m") or edge.get("length") or 0
        length_km = length_m / 1000.0
        mean_upes = edge.get("mean_upes", 0.5)
        t = edge.get("time_h") or (length_km / 15.0)
        w = edge.get("weight", 0)
        total_exposure += mean_upes * length_km
        distance_km += length_km
        time_h += t
        total_cost += w
    if coords:
        # dedupe consecutive duplicates
        out = [coords[0]]
        for c in coords[1:]:
            if c != out[-1]:
                out.append(c)
        coords = out
    return coords, total_exposure, distance_km, time_h, total_cost


def shortest_path_optimized(
    G: Any,
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
) -> Optional[Dict[str, Any]]:
    """
    Find shortest path by weight from origin to dest; return route dict with
    nodes, geometry (LineString coords), exposure, distance_km, time_min, cost.
    Returns None if no path or nearest node fails.
    """
    if G is None or G.number_of_nodes() == 0:
        return None
    src = _nearest_node(G, origin_lat, origin_lon)
    tgt = _nearest_node(G, dest_lat, dest_lon)
    if src is None or tgt is None:
        return None
    try:
        path = nx.shortest_path(G, src, tgt, weight="weight")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None
    if not path or len(path) < 2:
        return None
    coords, exposure, distance_km, time_h, cost = _route_geometry_and_metrics(G, path)
    return {
        "nodes": path,
        "geometry": {"type": "LineString", "coordinates": coords},
        "exposure": round(exposure, 6),
        "distance_km": round(distance_km, 4),
        "time_min": round(time_h * 60.0, 2),
        "cost": round(cost, 6),
    }


def _to_simple_digraph(G: Any) -> Any:
    """Convert MultiDiGraph to DiGraph by keeping minimum-weight edge per (u,v). shortest_simple_paths requires a simple graph."""
    if not getattr(G, "is_multigraph", lambda: False) or not G.is_multigraph():
        return G
    H = nx.DiGraph()
    H.add_nodes_from(G.nodes(data=True))
    for u, v, key, data in G.edges(keys=True, data=True):
        w = data.get("weight", 0)
        if not H.has_edge(u, v) or H[u][v].get("weight", float("inf")) > w:
            H.add_edge(u, v, **data)
    return H


def k_shortest_paths(
    G: Any,
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    k: int = 3,
) -> List[Dict[str, Any]]:
    """
    Return up to k alternative routes, ordered by cost. Uses shortest_simple_paths.
    """
    if G is None or G.number_of_nodes() == 0:
        return []
    src = _nearest_node(G, origin_lat, origin_lon)
    tgt = _nearest_node(G, dest_lat, dest_lon)
    if src is None or tgt is None:
        return []
    routes = []
    G_simple = _to_simple_digraph(G)
    try:
        for path in nx.shortest_simple_paths(G_simple, src, tgt, weight="weight"):
            if len(path) < 2:
                continue
            coords, exposure, distance_km, time_h, cost = _route_geometry_and_metrics(G, path)
            routes.append({
                "nodes": path,
                "geometry": {"type": "LineString", "coordinates": coords},
                "exposure": round(exposure, 6),
                "distance_km": round(distance_km, 4),
                "time_min": round(time_h * 60.0, 2),
                "cost": round(cost, 6),
            })
            if len(routes) >= k:
                break
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        pass
    return routes
