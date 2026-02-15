# Route Optimization Engine Verification Report

This document confirms that the **Route / Pollution Intelligence Engine** described in [ROUTE_OPTIMIZATION_ENGINE.md](ROUTE_OPTIMIZATION_ENGINE.md) is **implemented**, **tested**, and **aligned** with the Data Layer ([DATA_LAYER.md](DATA_LAYER.md), [DATA_LAYER_VERIFICATION.md](DATA_LAYER_VERIFICATION.md)) and the Data Ingestion and Scheduler Layer ([DATA_INGESTION_AND_SCHEDULER_LAYER.md](DATA_INGESTION_AND_SCHEDULER_LAYER.md)).

---

## 1. Inputs (Section 2 of ROUTE_OPTIMIZATION_ENGINE.md)

| Doc requirement | Status | Implementation | Test / verification |
|-----------------|--------|-----------------|---------------------|
| UPES raster: latest `final_score_*.tif` from `upes_output_base()/hourly_scores/final_score/` | ✅ | `graph_builder.get_latest_upes_raster_path()` uses `upes_output_base()` and `hourly_scores/final_score/`; rasterio used in `upes_sampling`. | `test_route_optimization_graph_builder.py`: `get_latest_upes_raster_path` returns path when dir has TIF, `None` when empty or missing. |
| Fallback scalar 0.5 when no UPES file exists | ✅ | `sample_upes_along_line(..., fallback=0.5)`; graph builder passes `upes_raster_path=None` → sampling uses fallback. | `test_route_optimization_upes_sampling.py`: fallback when raster path is None; graph_builder tests mock `sample_upes_along_line` with fallback. |
| OSM graph: osmnx bbox with `route_osm_buffer_km` | ✅ | `graph_builder.build_weighted_graph` uses config and `ox.graph_from_bbox(..., network_type='all')`. | `test_route_optimization_graph_builder.py`: OSM fetch mocked; bbox derived from bounds. |
| User mode: commute / jogger / cyclist | ✅ | API and analyze route accept `mode`; normalized in `cache.key_route_optimized` and in weights. | `test_route_optimization_weights.py`: all modes; `test_route_optimization_api.py`: mode in cache key and params. |

**Verdict:** Implemented and tested. UPES path contract matches ingestion layer output directory.

---

## 2. UPES Sampling (Section 3)

| Doc requirement | Status | Implementation | Test / verification |
|-----------------|--------|-----------------|---------------------|
| `sample_upes_along_line(raster_path, line_coords, step_m=50, fallback=0.5)` | ✅ | `services/route_optimization/upes_sampling.py`: resample line at step_m, sample with rasterio, return mean in [0,1] or fallback. | `test_route_optimization_upes_sampling.py`: `_resample_line`, `sample_upes_along_line` (no raster → fallback), valid raster → mean. |
| `sample_upes_along_line_mean_max` for exposure stats | ✅ | Same module: returns (mean, max). | `test_route_optimization_upes_sampling.py`: mean/max tests. |

**Verdict:** Implemented and tested.

---

## 3. Edge Weights and Mode Modifiers (Section 4)

| Doc requirement | Status | Implementation | Test / verification |
|-----------------|--------|-----------------|---------------------|
| Mode weights (α, β, γ) sum to 1.0; commute/jogger/cyclist | ✅ | `weights.py`: `MODE_WEIGHTS`, `get_weights(mode)`; commute/commuter, jogger/jog, cyclist/cycle aliases. | `test_route_optimization_weights.py`: all modes sum to one, aliases, unknown → commute. |
| Jogger: penalty motorway/trunk; bonus park/footway/path/pedestrian | ✅ | `mode_modifier(edge_data, mode)` in `weights.py`. | Tests: jogger penalty motorway/trunk, bonus footway/park. |
| Cyclist: bonus cycleway; penalty motorway/trunk | ✅ | Same. | Tests: cyclist bonus cycleway, penalty motorway. |
| Commuter: penalty footway/path when not accessible | ✅ | Same. | Tests: commuter penalty footway; no penalty with access. |
| Modifier clamped [0.1, 5.0]; `highway` as list (use first) | ✅ | Clamp in `mode_modifier`; list handled (first element). | Test: `test_highway_list_takes_first`; `test_modifier_clamped`. |

**Verdict:** Implemented and tested.

---

## 4. Graph Construction and Pathfinding (Section 5)

| Doc requirement | Status | Implementation | Test / verification |
|-----------------|--------|-----------------|---------------------|
| `get_latest_upes_raster_path()` → latest final_score TIF or None | ✅ | `graph_builder.get_latest_upes_raster_path()`: `upes_output_base()/hourly_scores/final_score/`, glob `final_score_*.tif`, sort by mtime. | Graph builder tests: returns path when TIF present, None when not. |
| `build_weighted_graph(n,s,e,w,mode,upes_raster_path)` with weight, length_m, mean_upes, time_h | ✅ | `graph_builder.build_weighted_graph`: OSMnx graph, sample UPES per edge, apply weights and modifiers. | `test_route_optimization_graph_builder.py`: `_edge_geometry_to_coords`, `_speed_kph`, `build_weighted_graph` (OSM mocked). |
| Nearest nodes: `ox.nearest_nodes(G, lon, lat)` | ✅ | `pathfinding._nearest_node` uses osmnx; tests patch it. | Pathfinding tests patch `osmnx.nearest_nodes` for deterministic nodes. |
| Shortest path: `nx.shortest_path(G, src, tgt, weight='weight')` | ✅ | `pathfinding.shortest_path_optimized`. | `test_route_optimization_pathfinding.py`: route dict shape, empty graph → None, no path → None. |
| K-shortest: `nx.shortest_simple_paths` (up to k alternatives) | ✅ | `pathfinding.k_shortest_paths`: MultiDiGraph converted to simple DiGraph for `shortest_simple_paths`; geometry/metrics from original G. | `test_route_optimization_pathfinding.py`: list of routes, respects k, empty graph → []. |
| Aggregation: LineString, total exposure, distance_km, time_min, cost | ✅ | `_route_geometry_and_metrics`; edge geometry and attrs aggregated. | Tests: geometry and metrics present; dedupe consecutive coords. |

**Verdict:** Implemented and tested. MultiDiGraph handling for k-shortest verified.

---

## 5. API (Section 6)

| Doc requirement | Status | Implementation | Test / verification |
|-----------------|--------|-----------------|---------------------|
| GET `/api/route/optimized` with start_lat, start_lon, end_lat, end_lon, mode, optional alternatives | ✅ | `api_server.api_route_optimized`: query params; returns JSON with `routes`. | `test_route_optimization_api.py`: GET params, response shape (`routes`, geometry, exposure, distance_km, time_min, cost). |
| POST `/api/route/optimized` with origin/destination, mode, alternatives | ✅ | `api_route_optimized_post`: body parsed; same response shape. | POST tests: body params, 422/400 on invalid input. |
| When `route_optimization_enabled` false or engine fails → error or empty routes | ✅ | 503 when disabled; on failure empty routes or error as appropriate. | Test: disabled → 503. |

**Verdict:** Implemented and tested (API tests skip if api_server/httpx unavailable).

---

## 6. Caching (Section 7) — Conformance with Data Layer

| Doc requirement | Status | Implementation | Test / verification |
|-----------------|--------|-----------------|---------------------|
| Key `route_opt:{start_lat}:{start_lon}:{end_lat}:{end_lon}:{mode}` | ✅ | `cache.key_route_optimized(start_lat, start_lon, end_lat, end_lon, mode)`; mode normalized (strip, lower). | `test_cache.py`: key format and mode normalization; `test_route_optimization_api.py`: cache key. |
| TTL from config `route_result_cache_ttl` (default 300) | ✅ | `api_server`: `ttl = getattr(app_settings, "route_result_cache_ttl", 300)`; `cache_set(redis, cache_key, result, ttl)`. | DATA_LAYER_VERIFICATION confirms route_opt cache and TTL. |
| Check cache → on miss build graph and path → SETEX | ✅ | GET/POST: `cache_get(redis, cache_key)`; on miss `build_weighted_graph`, pathfinding, then `cache_set`. | Same as Data Layer request flow. |
| Redis optional (no cache when REDIS_URL unset) | ✅ | `cache_get`/`cache_set` accept `redis=None` and skip; app.state.redis can be None. | DATA_LAYER_VERIFICATION §2, §6; `test_cache.py`: cache_get/cache_set when redis is None. |

**Verdict:** Route engine caching conforms to [DATA_LAYER.md](DATA_LAYER.md) and [DATA_LAYER_VERIFICATION.md](DATA_LAYER_VERIFICATION.md).

---

## 7. Configuration (Section 8)

| Doc requirement | Status | Implementation | Test / verification |
|-----------------|--------|-----------------|---------------------|
| `route_optimization_enabled` (default True) | ✅ | `config.py`: `route_optimization_enabled: bool = True`. | API test: disabled → 503. |
| `route_osm_buffer_km` (default 3.0) | ✅ | `config.py`; used in graph_builder bbox. | Config present. |
| `route_result_cache_ttl` (default 300) | ✅ | `config.py`; used in api_server for route cache. | Used in GET/POST route optimized. |
| `route_graph_cache_ttl` (reserved) | ✅ | In config; not yet used (OSM graph cache optional). | Doc and config aligned. |

**Verdict:** Implemented.

---

## 8. Conformance with Data Ingestion and Scheduler Layer

| Ingestion contract | Route engine usage | Status |
|--------------------|--------------------|--------|
| UPES pipeline writes `final_score_{ts}.tif` under `upes_output_base()/hourly_scores/final_score/` | `get_latest_upes_raster_path()` reads that directory, globs `final_score_*.tif`, picks latest by mtime | ✅ |
| Celery UPES pipeline: `write_upes_rasters` → `hourly_scores/final_score/` (see `services/upes/storage.write_upes_rasters`) | Graph builder uses same path layout; no duplicate constants | ✅ |
| If no raster exists (e.g. before first run) | Edges use fallback 0.5; API still returns routes when OSM graph available | ✅ |
| `upes_output_base` from config / default | `graph_builder` and `upes.storage` share `upes_output_base()` | ✅ |

**Verdict:** Route engine correctly consumes the ingestion layer’s UPES output; no contract violations.

---

## 9. Conformance with Data Layer

| Data layer contract | Route engine usage | Status |
|---------------------|--------------------|--------|
| Redis key pattern `route_opt:...` | `cache.key_route_optimized` builds that key | ✅ (see DATA_LAYER_VERIFICATION §2) |
| cache_get / cache_set with TTL | GET/POST `/api/route/optimized` use `cache_get`, `cache_set` with `key_route_optimized` and `route_result_cache_ttl` | ✅ |
| Redis optional | Same `redis` from app.state; cache_get/cache_set handle None | ✅ |

**Verdict:** Route engine fully conforms to the Data Layer cache contract.

---

## 10. Test Suite Summary

| Test file | Scope |
|-----------|--------|
| `test_route_optimization_weights.py` | MODE_WEIGHTS, get_weights, mode_modifier (including highway list, clamp). |
| `test_route_optimization_upes_sampling.py` | _resample_line, sample_upes_along_line (fallback, valid raster), sample_upes_along_line_mean_max. |
| `test_route_optimization_pathfinding.py` | _route_geometry_and_metrics, shortest_path_optimized, k_shortest_paths (with MultiDiGraph→simple conversion). |
| `test_route_optimization_graph_builder.py` | get_latest_upes_raster_path, _edge_geometry_to_coords, _speed_kph, build_weighted_graph (OSM mocked). |
| `test_route_optimization_api.py` | key_route_optimized (data layer compatibility); GET/POST `/api/route/optimized` (503 when disabled, params, response shape); **TestRouteEngineWithDataAndIngestionLayers**: full stack with mocked OSM (200 + response shape), cache hit with fake Redis (second request skips build_weighted_graph, key `route_opt:...`). |

**Run command:** `pytest tests/test_route_optimization_*.py -v`

Some tests skip when `osmnx` or the full `api_server`/`httpx` stack is not available; with `osmnx` and `xarray` installed, route optimization tests run and pass.

---

## 11. Production and testing behaviour (in conjunction with Data and Ingestion layers)

The following describes how the route engine behaves when run **with** the other two backend layers, as in production or a testing environment.

### 11.1 Request flow (GET/POST `/api/route/optimized`)

1. **Config:** If `route_optimization_enabled` is false → respond with 503 and empty routes.
2. **Data Layer (Redis):** `redis = request.app.state.redis` (set at lifespan from `REDIS_URL`). Cache key built with `key_route_optimized(start_lat, start_lon, end_lat, end_lon, mode)`.
3. **Cache lookup:** `cached = await cache_get(redis, cache_key)`. If `redis` is `None` (no REDIS_URL), `cache_get` returns `None` and no exception is raised.
4. **Cache hit:** If `cached is not None`, return `JSONResponse(cached)` immediately; no graph build or pathfinding.
5. **Cache miss:** Run `_compute()` in a thread pool: compute bbox from origin/destination and `route_osm_buffer_km`, call `build_weighted_graph(north, south, east, west, mode=mode)`.
6. **Ingestion Layer (UPES):** Inside `build_weighted_graph`, `raster_path = upes_raster_path or get_latest_upes_raster_path()`. `get_latest_upes_raster_path()` uses `upes_output_base()/hourly_scores/final_score/` (same path the Celery UPES pipeline writes to). If no `final_score_*.tif` exists, it returns `None`; edges then use `sample_upes_along_line(None, coords)` → fallback 0.5.
7. **Pathfinding:** `shortest_path_optimized` or `k_shortest_paths` on the weighted graph; geometry and metrics aggregated.
8. **Cache write:** If routes are non-empty, `await cache_set(redis, cache_key, result, ttl)`. If `redis` is `None`, `cache_set` is a no-op.

**Evidence:** Code in `api_server.py` (GET/POST handlers), `cache.py` (`cache_get`/`cache_set` when `redis is None`), `graph_builder.get_latest_upes_raster_path()` and `build_weighted_graph`, and `services/upes/storage.write_upes_rasters` (same path). Unit tests: `test_cache.py` (cache_get/cache_set with None), `test_route_optimization_graph_builder.py` (get_latest_upes_raster_path, build_weighted_graph). Integration tests: `test_route_optimization_api.py::TestRouteEngineWithDataAndIngestionLayers::test_full_stack_with_mocked_osm_returns_200` (full pipeline with mocked OSM), `test_cache_hit_skips_compute_when_redis_provided` (fake Redis: first request misses and caches, second request hits cache and does not call `build_weighted_graph` again; key format `route_opt:...` and mode in key verified).

### 11.2 Environment scenarios

| Scenario | Behaviour |
|--------|-----------|
| **Production: REDIS_URL set, UPES pipeline has run** | Cache hit for repeated (start, end, mode); on miss, graph built with latest `final_score_*.tif`, pathfinding runs, result cached with TTL. |
| **Production: REDIS_URL set, no UPES raster yet** | Cache miss; `get_latest_upes_raster_path()` returns `None`; all edges use UPES fallback 0.5; routes still returned if OSM graph is available; result cached. |
| **Testing / dev: REDIS_URL unset** | `app.state.redis` is `None`; every request is cache miss; `cache_get` returns `None`, `cache_set` no-op; graph and pathfinding run every time. No crash. |
| **Testing / dev: REDIS_URL set, fake or real Redis** | Same as production; cache hit on second identical request; integration test `test_cache_hit_skips_compute_when_redis_provided` asserts this with an in-memory fake Redis. |

### 11.3 Conformance summary

- **Data Layer:** Redis is optional; key `route_opt:{...}:{mode}` and TTL are used when Redis is present; `cache_get`/`cache_set` handle `redis=None`. Verified by `test_cache.py`, `test_route_optimization_api.py` (cache key tests and `TestRouteEngineWithDataAndIngestionLayers`).
- **Ingestion Layer:** Route engine reads from `upes_output_base()/hourly_scores/final_score/` via `get_latest_upes_raster_path()`; when no raster exists, fallback 0.5 is used. Same path as `write_upes_rasters` in the Celery UPES pipeline. Verified by `test_route_optimization_graph_builder.py` and the request flow above.

The route / pollution intelligence engine is verified to behave accordingly in conjunction with the Data Layer and the Data Ingestion and Scheduler Layer in both production-like and testing environments.

---

## Summary

- **Route Optimization Engine:** All requirements from [ROUTE_OPTIMIZATION_ENGINE.md](ROUTE_OPTIMIZATION_ENGINE.md) are implemented and covered by the tests above.
- **Data Layer:** Caching (key format, cache_get/cache_set, TTL, optional Redis) matches [DATA_LAYER.md](DATA_LAYER.md) and [DATA_LAYER_VERIFICATION.md](DATA_LAYER_VERIFICATION.md).
- **Data Ingestion Layer:** UPES raster input path and fallback behavior match the Celery UPES pipeline output described in [DATA_INGESTION_AND_SCHEDULER_LAYER.md](DATA_INGESTION_AND_SCHEDULER_LAYER.md).
- **Production/testing behaviour:** Request flow, Redis-optional behaviour, and UPES path usage are documented in §11 and verified by unit and integration tests.

All three layers (Data, Data Ingestion and Schedulers, Route / Pollution Intelligence Engine) are aligned and verified.
