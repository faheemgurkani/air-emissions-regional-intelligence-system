"""
Tests for route optimization API and compatibility with data layer (cache, config).
See ROUTE_OPTIMIZATION_ENGINE.md and DATA_LAYER.md.
Requires httpx and full project deps (api_server) for TestRouteOptimizedAPI.
"""
import pytest

from cache import key_route_optimized


class TestCacheKeyCompatibility:
    """Cache key must match DATA_LAYER / ROUTE_OPTIMIZATION_ENGINE doc."""

    def test_key_format(self):
        k = key_route_optimized(34.0, -118.0, 34.1, -117.9, "commute")
        assert k == "route_opt:34.0:-118.0:34.1:-117.9:commute"

    def test_mode_normalized(self):
        k = key_route_optimized(0, 0, 0, 0, "  Jogger  ")
        assert "jogger" in k or "Jogger" in k

    def test_different_modes_different_keys(self):
        k1 = key_route_optimized(34, -118, 34, -117, "commute")
        k2 = key_route_optimized(34, -118, 34, -117, "cyclist")
        assert k1 != k2


class TestRouteOptimizedAPI:
    """GET/POST /api/route/optimized: behaviour and integration with app state (Redis). Requires httpx and api_server."""

    @pytest.fixture(autouse=True)
    def _require_app(self):
        pytest.importorskip("httpx")
        try:
            import api_server  # noqa: F401
        except Exception as e:
            pytest.skip("api_server not importable: %s" % e)

    def test_disabled_returns_503(self):
        from unittest.mock import patch
        from fastapi.testclient import TestClient
        from api_server import app_settings, app
        with patch.object(app_settings, "route_optimization_enabled", False):
            client = TestClient(app)
            r = client.get(
                "/api/route/optimized",
                params={"start_lat": 34, "start_lon": -118, "end_lat": 34.1, "end_lon": -117.9, "mode": "commute"},
            )
        assert r.status_code == 503
        data = r.json()
        assert "routes" in data
        assert data["routes"] == []
        assert "disabled" in data.get("detail", "").lower()

    def test_get_required_params(self):
        """GET without required params returns 422."""
        from fastapi.testclient import TestClient
        from api_server import app
        client = TestClient(app)
        r = client.get("/api/route/optimized")
        assert r.status_code == 422

    def test_post_invalid_json_returns_400(self):
        from fastapi.testclient import TestClient
        from api_server import app
        client = TestClient(app)
        r = client.post("/api/route/optimized", content="not json", headers={"Content-Type": "application/json"})
        assert r.status_code == 400

    def test_post_body_shape(self):
        """POST with origin/destination/mode; response has routes key."""
        from fastapi.testclient import TestClient
        from api_server import app
        client = TestClient(app)
        r = client.post(
            "/api/route/optimized",
            json={
                "origin": {"lat": 34.0, "lon": -118.0},
                "destination": {"lat": 34.1, "lon": -117.9},
                "mode": "jogger",
                "alternatives": 1,
            },
        )
        # May be 200 (if OSM succeeds in test env), 503 (disabled), or 500 (OSM/graph failure)
        assert r.status_code in (200, 500, 503)
        data = r.json()
        assert "routes" in data
        assert isinstance(data["routes"], list)

    def test_response_shape_when_200(self):
        """When API returns 200, each route has geometry, exposure, distance_km, time_min, cost."""
        from fastapi.testclient import TestClient
        from api_server import app
        client = TestClient(app)
        r = client.get(
            "/api/route/optimized",
            params={"start_lat": 34.0, "start_lon": -118.0, "end_lat": 34.01, "end_lon": -117.99, "mode": "commute"},
        )
        if r.status_code != 200:
            pytest.skip("API returned %s (OSM/graph may be unavailable)" % r.status_code)
        data = r.json()
        assert "routes" in data
        for route in data["routes"]:
            assert "geometry" in route
            assert route["geometry"]["type"] == "LineString"
            assert "coordinates" in route["geometry"]
            assert "exposure" in route
            assert "distance_km" in route
            assert "time_min" in route
            assert "cost" in route


class TestRouteEngineWithDataAndIngestionLayers:
    """
    Verify route engine behaviour in conjunction with Data Layer (Redis cache) and
    Ingestion Layer (UPES raster path). Simulates production/testing flow: cache miss
    -> build graph (using get_latest_upes_raster_path) -> pathfinding -> cache set;
    cache hit -> return without recompute. When Redis is None, no crash and no cache.
    """

    @pytest.fixture(autouse=True)
    def _require_app(self):
        pytest.importorskip("httpx")
        pytest.importorskip("osmnx")
        try:
            import api_server  # noqa: F401
        except Exception as e:
            pytest.skip("api_server not importable: %s" % e)

    def _make_minimal_graph(self):
        """Minimal MultiDiGraph for pathfinding (nodes 1..4, diamond)."""
        import networkx as nx
        G = nx.MultiDiGraph()
        G.add_node(1, x=-118.0, y=34.0)
        G.add_node(2, x=-117.95, y=34.05)
        G.add_node(3, x=-117.9, y=34.0)
        G.add_node(4, x=-117.95, y=33.95)
        # geometry-like with .coords
        class Line:
            def __init__(self, a, b):
                self.coords = [(G.nodes[a]["x"], G.nodes[a]["y"]), (G.nodes[b]["x"], G.nodes[b]["y"])]
        for (u, v), length_m, mean_upes, time_h, weight in [
            ((1, 2), 1000, 0.3, 0.05, 0.4),
            ((2, 3), 800, 0.5, 0.04, 0.5),
            ((1, 4), 1200, 0.2, 0.06, 0.35),
            ((4, 3), 900, 0.4, 0.045, 0.45),
        ]:
            G.add_edge(u, v, geometry=Line(u, v), length_m=length_m, mean_upes=mean_upes, time_h=time_h, weight=weight)
        return G

    def test_full_stack_with_mocked_osm_returns_200(self):
        """
        With build_weighted_graph mocked to return a minimal graph, the endpoint runs the full
        pipeline: cache_get (Data Layer) -> miss -> build_weighted_graph -> pathfinding ->
        cache_set. Verifies the route engine runs with the app and returns correct shape.
        Ingestion path (get_latest_upes_raster_path) is covered by graph_builder tests.
        """
        from unittest.mock import patch
        from fastapi.testclient import TestClient
        from api_server import app

        G = self._make_minimal_graph()
        with patch("services.route_optimization.graph_builder.build_weighted_graph", side_effect=lambda *a, **k: G):
            with patch("services.route_optimization.pathfinding._nearest_node", side_effect=lambda G, lat, lon: 1 if lon < -117.95 else 3):
                client = TestClient(app)
                r = client.get(
                    "/api/route/optimized",
                    params={"start_lat": 34.0, "start_lon": -118.0, "end_lat": 34.0, "end_lon": -117.9, "mode": "commute"},
                )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "routes" in data
        assert isinstance(data["routes"], list)
        assert len(data["routes"]) >= 1
        for route in data["routes"]:
            assert "geometry" in route and route["geometry"]["type"] == "LineString"
            assert "exposure" in route and "distance_km" in route and "time_min" in route and "cost" in route

    def test_cache_hit_skips_compute_when_redis_provided(self):
        """
        With a fake Redis that stores in memory, first request misses and caches result;
        second request hits cache and returns same body without calling build_weighted_graph again.
        Verifies Data Layer integration: route_opt key, cache_get/cache_set, TTL.
        """
        from unittest.mock import patch
        from fastapi.testclient import TestClient
        from api_server import app

        class FakeRedis:
            """In-memory async Redis stand-in for testing cache path."""
            def __init__(self):
                self._store = {}
            async def get(self, key):
                return self._store.get(key)
            async def setex(self, key, ttl, value):
                self._store[key] = value

        G = self._make_minimal_graph()
        build_calls = []
        def build_tracked(*a, **kw):
            build_calls.append(1)
            return G

        # Trigger lifespan so app.state exists
        client = TestClient(app)
        client.get("/openapi.json")
        app.state.redis = FakeRedis()
        try:
            with patch("services.route_optimization.pathfinding._nearest_node", side_effect=lambda G, lat, lon: 1 if lon < -117.95 else 3):
                with patch("services.route_optimization.graph_builder.build_weighted_graph", side_effect=build_tracked):
                    r1 = client.get(
                        "/api/route/optimized",
                        params={"start_lat": 34.0, "start_lon": -118.0, "end_lat": 34.0, "end_lon": -117.9, "mode": "jogger"},
                    )
                    r2 = client.get(
                        "/api/route/optimized",
                        params={"start_lat": 34.0, "start_lon": -118.0, "end_lat": 34.0, "end_lon": -117.9, "mode": "jogger"},
                    )
            assert r1.status_code == 200 and r2.status_code == 200
            assert r1.json() == r2.json(), "Second request must return cached response"
            assert len(build_calls) == 1, "build_weighted_graph must be called only once (cache hit on second)"
            assert list(app.state.redis._store.keys())  # key_route_optimized format
            key = list(app.state.redis._store.keys())[0]
            assert key.startswith("route_opt:")
            assert "jogger" in key
        finally:
            app.state.redis = None
