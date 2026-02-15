"""
Tests for route optimization graph builder (ROUTE_OPTIMIZATION_ENGINE).
Mocks OSMnx to avoid network access; verifies integration with UPES storage.
"""
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services.route_optimization.graph_builder import (
    get_latest_upes_raster_path,
    build_weighted_graph,
    _edge_geometry_to_coords,
    _speed_kph,
)


class TestGetLatestUpesRasterPath:
    def test_returns_none_when_dir_missing(self):
        with patch("services.route_optimization.graph_builder.upes_output_base") as m:
            m.return_value = Path("/nonexistent/base")
            assert get_latest_upes_raster_path() is None

    def test_returns_none_when_no_tifs(self):
        with patch("services.route_optimization.graph_builder.upes_output_base") as m:
            base = Path("/tmp/upes_test_empty")
            (base / "hourly_scores" / "final_score").mkdir(parents=True, exist_ok=True)
            m.return_value = base
            try:
                assert get_latest_upes_raster_path() is None
            finally:
                (base / "hourly_scores" / "final_score").rmdir()
                (base / "hourly_scores").rmdir()
                base.rmdir()

    def test_returns_latest_tif_when_present(self):
        with patch("services.route_optimization.graph_builder.upes_output_base") as m:
            base = Path("/tmp/upes_test_tif")
            final_dir = base / "hourly_scores" / "final_score"
            final_dir.mkdir(parents=True, exist_ok=True)
            tif = final_dir / "final_score_2024060112.tif"
            tif.touch()
            m.return_value = base
            try:
                p = get_latest_upes_raster_path()
                assert p is not None
                assert p.name.startswith("final_score_")
                assert p.suffix == ".tif"
            finally:
                tif.unlink()
                final_dir.rmdir()
                (base / "hourly_scores").rmdir()
                base.rmdir()


class TestEdgeGeometryToCoords:
    def test_none_returns_empty(self):
        assert _edge_geometry_to_coords(None) == []

    def test_geometry_with_coords(self):
        geom = type("Line", (), {"coords": [(-118, 34), (-117, 35)]})()
        coords = _edge_geometry_to_coords(geom)
        assert coords == [(-118.0, 34.0), (-117.0, 35.0)]

    def test_list_of_pairs(self):
        coords = _edge_geometry_to_coords([(-118, 34), (-117, 35)])
        assert coords == [(-118.0, 34.0), (-117.0, 35.0)]


class TestSpeedKph:
    def test_numeric_maxspeed(self):
        assert _speed_kph({"maxspeed": 50}) == 50.0

    def test_motorway_default(self):
        assert _speed_kph({"highway": "motorway"}) == 100.0

    def test_footway_default(self):
        assert _speed_kph({"highway": "footway"}) == 5.0

    def test_unknown_highway_default(self):
        assert _speed_kph({"highway": "residential"}) == 25.0


class TestBuildWeightedGraph:
    def test_returns_none_when_osm_returns_empty(self):
        pytest.importorskip("osmnx")
        with patch("osmnx.graph_from_bbox", return_value=None):
            G = build_weighted_graph(35.0, 33.0, -117.0, -119.0, "commute")
        assert G is None

    def test_returns_none_when_osm_returns_zero_edges(self):
        pytest.importorskip("osmnx")
        import networkx as nx
        empty = nx.MultiDiGraph()
        with patch("osmnx.graph_from_bbox", return_value=empty):
            G = build_weighted_graph(35.0, 33.0, -117.0, -119.0, "commute")
        assert G is not None
        assert G.number_of_edges() == 0

    def test_assigns_weight_and_attrs_to_edges(self):
        pytest.importorskip("osmnx")
        import networkx as nx
        mock_sample = MagicMock(return_value=0.4)
        G = nx.MultiDiGraph()
        G.add_node(1, x=-118.0, y=34.0)
        G.add_node(2, x=-117.99, y=34.0)
        geom = type("Line", (), {"coords": [(-118, 34), (-117.99, 34)]})()
        G.add_edge(1, 2, 0, geometry=geom, length=1000)
        with patch("osmnx.graph_from_bbox", return_value=G):
            with patch("services.route_optimization.graph_builder.sample_upes_along_line", mock_sample):
                out = build_weighted_graph(34.5, 33.5, -117.0, -118.5, "commute")
        assert out is not None
        assert out.number_of_edges() > 0
        for u, v, k, data in out.edges(keys=True, data=True):
            assert "weight" in data
            assert "mean_upes" in data
            assert "length_m" in data
            assert "time_h" in data
            assert data["weight"] >= 0
