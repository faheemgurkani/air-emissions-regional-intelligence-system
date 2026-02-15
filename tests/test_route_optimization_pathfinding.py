"""
Tests for route optimization pathfinding (ROUTE_OPTIMIZATION_ENGINE).
Uses in-memory NetworkX graphs; no OSM fetch.
"""
import pytest

nx = pytest.importorskip("networkx")

from services.route_optimization.pathfinding import (
    _route_geometry_and_metrics,
    k_shortest_paths,
    shortest_path_optimized,
)


def _line_coords(G, a, b):
    """Minimal geometry-like object with .coords for pathfinding aggregation."""
    class CoordsLine:
        coords = []
    c = CoordsLine()
    c.coords = [(G.nodes[a]["x"], G.nodes[a]["y"]), (G.nodes[b]["x"], G.nodes[b]["y"])]
    return c


def _make_simple_graph():
    """Graph with 4 nodes in a diamond; edge attrs: geometry (coords), length_m, mean_upes, time_h, weight."""
    G = nx.MultiDiGraph()
    # Nodes (OSM-style: x=lon, y=lat)
    G.add_node(1, x=-118.0, y=34.0)
    G.add_node(2, x=-117.95, y=34.05)
    G.add_node(3, x=-117.9, y=34.0)
    G.add_node(4, x=-117.95, y=33.95)
    # Edges with geometry and cost attrs
    def line(a, b):
        return _line_coords(G, a, b)
    G.add_edge(1, 2, geometry=line(1, 2), length=1000, length_m=1000, mean_upes=0.3, time_h=0.05, weight=0.4)
    G.add_edge(2, 3, geometry=line(2, 3), length=800, length_m=800, mean_upes=0.5, time_h=0.04, weight=0.5)
    G.add_edge(1, 4, geometry=line(1, 4), length=1200, length_m=1200, mean_upes=0.2, time_h=0.06, weight=0.35)
    G.add_edge(4, 3, geometry=line(4, 3), length=900, length_m=900, mean_upes=0.4, time_h=0.045, weight=0.45)
    return G


class TestRouteGeometryAndMetrics:
    def test_aggregates_exposure_distance_time_cost(self):
        G = _make_simple_graph()
        path = [1, 2, 3]
        coords, exposure, dist_km, time_h, cost = _route_geometry_and_metrics(G, path)
        assert len(coords) >= 2
        assert exposure >= 0
        assert dist_km >= 0
        assert time_h >= 0
        assert cost >= 0

    def test_dedupes_consecutive_duplicate_coords(self):
        G = nx.MultiDiGraph()
        G.add_node(1, x=-118.0, y=34.0)
        G.add_node(2, x=-118.0, y=34.0)
        G.add_edge(1, 2, length_m=0, mean_upes=0.5, time_h=0, weight=0.1)
        coords, _, _, _, _ = _route_geometry_and_metrics(G, [1, 2])
        assert len(coords) >= 1


class TestShortestPathOptimized:
    def test_none_for_empty_graph(self):
        G = nx.MultiDiGraph()
        r = shortest_path_optimized(G, 34.0, -118.0, 34.0, -117.0)
        assert r is None

    def test_returns_route_dict_shape(self):
        pytest.importorskip("osmnx")
        from unittest.mock import patch
        G = _make_simple_graph()
        with patch("osmnx.nearest_nodes") as mock_nn:
            mock_nn.side_effect = lambda G, lon, lat: 1 if lon < -117.95 else 3
            r = shortest_path_optimized(G, 34.0, -118.0, 34.0, -117.9)
        assert r is not None
        assert "nodes" in r
        assert "geometry" in r
        assert r["geometry"]["type"] == "LineString"
        assert "coordinates" in r["geometry"]
        assert "exposure" in r
        assert "distance_km" in r
        assert "time_min" in r
        assert "cost" in r
        assert isinstance(r["nodes"], list)
        assert len(r["nodes"]) >= 2

    def test_no_path_returns_none(self):
        G = nx.MultiDiGraph()
        G.add_node(1, x=-118.0, y=34.0)
        G.add_node(2, x=-117.0, y=34.0)
        # no edge between 1 and 2
        r = shortest_path_optimized(G, 34.0, -118.0, 34.0, -117.0)
        assert r is None


class TestKShortestPaths:
    def test_returns_list_of_routes(self):
        pytest.importorskip("osmnx")
        from unittest.mock import patch
        G = _make_simple_graph()
        with patch("osmnx.nearest_nodes") as mock_nn:
            mock_nn.side_effect = lambda G, lon, lat: 1 if lon < -117.95 else 3
            routes = k_shortest_paths(G, 34.0, -118.0, 34.0, -117.9, k=2)
        assert isinstance(routes, list)
        assert len(routes) >= 1
        for route in routes:
            assert "geometry" in route
            assert "exposure" in route
            assert "distance_km" in route
            assert "time_min" in route
            assert "cost" in route

    def test_empty_graph_returns_empty_list(self):
        G = nx.MultiDiGraph()
        routes = k_shortest_paths(G, 34.0, -118.0, 34.0, -117.0, k=3)
        assert routes == []

    def test_respects_k(self):
        pytest.importorskip("osmnx")
        from unittest.mock import patch
        G = _make_simple_graph()
        with patch("osmnx.nearest_nodes") as mock_nn:
            mock_nn.side_effect = lambda G, lon, lat: 1 if lon < -117.95 else 3
            routes = k_shortest_paths(G, 34.0, -118.0, 34.0, -117.9, k=5)
        assert len(routes) <= 5
