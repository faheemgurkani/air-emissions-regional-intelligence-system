# AERIS — Air Emissions Regional Intelligence System

## Project Documentation

This document describes the established architectures, current functionality, and utilities of the AERIS (Air Emissions Regional Intelligence System) project, developed for the **NASA Space Apps Challenge (2025)**.

---

## 1. Project Overview

**AERIS** is a web application that processes **NASA TEMPO** (Tropospheric Emissions: Monitoring of Pollution) satellite data to provide real-time air quality analysis and intelligence. It was originally developed for monitoring the Madre Wildfire Region in New Cuyama, California, and can be adapted to any geographic area and time window.

### Team

- Muhammad Faheem (faheemgurkani@gmail.com)
- Muhammad Zeeshan
- Amar Rameez

### Core Value Proposition

- Integrates **NASA Harmony API**, scientific data processing, and interactive web visualization.
- Delivers real-time regional air quality intelligence for environmental monitoring and public health protection.

---

## 2. Established Architecture

For a **high-level diagram** of the data layer (Clients → FastAPI → PostgreSQL/Redis/S3) and a concise architecture summary, see [ARCHITECTURE.md](ARCHITECTURE.md).

### 2.1 High-Level Architecture

The system follows a **modular, layered architecture** with clear separation of concerns:

| Layer | Components | Description |
|-------|-------------|-------------|
| **Web Server** | FastAPI + Uvicorn | Serves web dashboard and handles all HTTP/API requests |
| **Frontend** | Jinja2 templates, CSS, Leaflet.js | Renders UI, forms, results, and interactive maps |
| **Computation** | NumPy, SciPy, Xarray | NASA TEMPO data parsing, clustering, and analysis |
| **Visualization** | Matplotlib, Cartopy | Pollution heatmaps, tripanel figures, geospatial overlays |
| **AI Services** | GROQ API (Llama 3.1 8B Instant) | Concise, actionable interpretations and commute advice |
| **Weather Integration** | WeatherAPI.com | Real-time weather and optional air quality (AQI) |
| **Data layer** | PostgreSQL + PostGIS, Redis, S3/MinIO | Users, saved routes, pollution grid, NetCDF metadata; cache; object storage for NetCDF blobs |

### 2.2 Data Layer (PostgreSQL, Redis, Object Storage)

- **PostgreSQL + PostGIS:** Stores users (auth), saved_routes (per user), pollution_grid (gridded cells with geometry), netcdf_files (metadata for objects in bucket). PostGIS extensions and GIST index on `pollution_grid.geom` for spatial queries. Async driver: asyncpg; ORM: SQLAlchemy 2.x + GeoAlchemy2; migrations: Alembic.
- **Redis:** Optional (when `REDIS_URL` is set). Caches weather API responses and pollutant movement predictions (TTL 600 s); reduces repeat calls to WeatherAPI.com.
- **Object storage (S3 or MinIO):** Optional (when `OBJECT_STORAGE_PROVIDER` is set). NetCDF files stored by key; metadata (file_name, bucket_path, timestamp, gas_type) in `netcdf_files`. Resolver: latest file per gas from DB → download to temp file → use in analysis; fallback to local `TempData/` when not configured.

### 2.3 Request Flow

1. **User** → Web UI (location, gases, radius, options).
2. **api_server.py** → Geocoding (if needed). Resolve NetCDF: query `netcdf_files` and download from S3/MinIO when configured, else scan `TempData/`.
3. **Data pipeline** → NetCDF → xarray Datatree → quality filtering → hotspot detection → regional alerts. Optionally persist pollution grid cells to PostGIS when `PERSIST_POLLUTION_GRID=true`.
4. **Visualization** → Multi-gas heatmaps + per-gas tripanel figures → saved to `static/outputs/`.
5. **Optional** → Weather/pollutant movement (cached in Redis when available) → GROQ interpretations.
6. **Response** → Rendered HTML (result/route) with images, alerts, hotspots, and map.

### 2.4 Directory and File Layout

```
air-emissions-regional-intelligence-system/
├── api_server.py              # Main FastAPI app: routes, analysis, visualization, routing, auth, saved-routes
├── config.py                  # Pydantic Settings: DB, Redis, JWT, object storage, feature flags
├── database/
│   ├── models.py              # SQLAlchemy + GeoAlchemy2: User, SavedRoute, PollutionGrid, NetcdfFile
│   ├── session.py             # Async engine, get_db, init_db_extensions
│   └── schemas.py             # Pydantic: UserRegister, Token, SavedRouteCreate, etc.
├── auth.py                    # Password hashing, JWT, get_current_user dependency
├── cache.py                   # Redis key builders, get/set, get_weather_cached, get_pollutant_movement_cached
├── storage.py                 # S3/MinIO: upload_netcdf, download_netcdf_to_path, is_configured
├── netcdf_resolver.py         # resolve_netcdf_paths_for_gases(session, gases) → overrides + temp paths
├── alembic.ini, alembic/      # Migrations (initial: users, saved_routes, pollution_grid, netcdf_files + PostGIS)
├── docker-compose.yml         # Local dev: postgres (PostGIS), redis, minio
├── weather_service.py         # WeatherAPI.com client; triggers pollutant prediction
├── groq_service.py            # GROQ API: weather & prediction interpretations
├── pollutant_predictor.py     # 3-hour pollutant movement from wind/humidity
├── celery_app.py              # Celery app (Redis broker), Beat schedule: fetch_tempo_hourly
├── tasks/
│   └── pollution_tasks.py     # fetch_tempo_hourly, recompute_saved_route_exposure
├── services/
│   ├── harmony_service.py     # Harmony: token, rangeset URL, submit, poll, download GeoTIFF
│   └── raster_normalizer.py  # GeoTIFF → pollution_grid rows (WKT, severity)
├── pollution_utils.py         # Shared POLLUTION_THRESHOLDS, classify_pollution_level
├── TEMPO.py                   # Standalone: Harmony NO2 fetch + process + map (Madre wildfire)
├── tempo_all.py               # TempoMultiGasAnalyzer: multi-gas Harmony fetch + analysis
├── GroundSensorAnalysis.py    # EPA AirNow ground sensor integration (standalone)
├── templates/
│   ├── index.html             # Main form: location, coords, radius, gases, weather/prediction toggles
│   ├── result.html            # Analysis results: images, alerts, hotspots, weather, map
│   └── route.html             # Route safety: OSRM routes, exposure scoring, Leaflet map
├── static/
│   ├── style.css              # Shared styles
│   └── outputs/               # Generated analysis images (gitignored)
├── TempData/                  # Cached TEMPO NetCDF files (fallback when object storage not used)
├── GroundData/                # Ground sensor / placeholder data
├── docs/
│   └── PROJECT_DOCUMENTATION.md
├── requirements.txt
├── .env.example               # Documented env vars (commit); .env (gitignored)
└── README.md
```

---

## 3. Core Components (Technical Detail)

### 3.1 api_server.py (Application Core)

- **Framework:** FastAPI; static files and Jinja2 templates mounted.
- **Domain config:**
  - `VARIABLE_NAMES`: TEMPO product paths (e.g. `product/vertical_column_troposphere` for NO2/CH2O).
  - `UNITS`: Display units per gas (molecules/cm², index, Dobson Units, etc.).
  - `POLLUTION_THRESHOLDS`: Per-gas thresholds for moderate / unhealthy / very_unhealthy / hazardous.
- **Helpers:**
  - **Geocoding:** `geocode_location`, `reverse_geocode` (with in-memory cache).
  - **Data:** `find_latest_file_for_gas(gas)` — scans `TempData/` and `TempData/{gas}/` for latest `.nc`/`.nc4`. When object storage is configured, routes use `resolve_netcdf_paths_for_gases(db, gases)` to get latest from `netcdf_files` and download from S3/MinIO, then pass `file_overrides` into `load_and_analyze_for_gases`.
  - **Classification:** `classify_pollution_level(value, gas)` → level name + severity 0–4.
  - **Hotspots:** `detect_hotspots(data, lats, lons, gas)` — connected-component clustering (SciPy `ndimage.label`) above thresholds; returns list of dicts (center, level, area_km2, etc.).
  - **Regional alerts:** `check_regional_alerts(...)` — alerts for a circular region around a center.
  - **Visualization:** `visualize_multi_gas`, `visualize_tripanel_for_gas` — Cartopy/Matplotlib maps; output to `static/outputs/`.
  - **GeoJSON:** `gather_hotspots_geojson`, `build_hotspot_circles` — for Leaflet overlays.
  - **Pollution grid persist:** When `PERSIST_POLLUTION_GRID=true`, `persist_pollution_grid_cells(session, gas_data, timestamp)` bulk-inserts gridded cells into `pollution_grid` (PostGIS) after analysis.
- **Analysis pipeline:** `load_and_analyze_for_gases(gases, center_lat, center_lon, radius, location_name, file_overrides=None)` loads NetCDF (from file_overrides or disk), applies quality flag, runs hotspot + alert logic per gas, returns `gas_data`, `all_hotspots`, `all_alerts`.

### 3.2 TEMPO Data and Variables

- **Data source:** NASA TEMPO Level-3 (and related) products via **NASA Harmony** (optional; see `TEMPO.py` / `tempo_all.py`). The web app primarily **reads pre-downloaded/cached NetCDF** from `TempData/`.
- **Supported gases and product paths:**

| Gas | Variable Path | Units |
|-----|----------------|-------|
| NO2 | product/vertical_column_troposphere | molecules/cm² |
| CH2O | product/vertical_column_troposphere | molecules/cm² |
| AI  | product/aerosol_index_354_388       | index |
| PM  | product/aerosol_optical_depth_550   | dimensionless |
| O3  | product/ozone_total_column         | Dobson Units |

- **Quality:** When present, `product/main_data_quality_flag == 0` is used to mask valid data.

### 3.3 TEMPO.py (Standalone Script)

- **Purpose:** Fetch NO2 TEMPO data for a fixed Madre wildfire spatio-temporal window via **Harmony** (Earthdata login).
- **Config:** `SPATIAL_BOUNDS`, `TIME_CONFIG`, `MONITORED_REGIONS`, `POLLUTION_THRESHOLDS`.
- **Flow:** Harmony request → submit job → wait → download to `TempData/` → classify levels → detect hotspots → check regional alerts → generate maps and text report.
- **Output:** Local NetCDF and visualizations; no web server.

### 3.4 tempo_all.py (Multi-Gas Analyzer Class)

- **Class:** `TempoMultiGasAnalyzer` — credentials (interactive or passed), Harmony client.
- **Collections:** Maps each gas (NO2, CH2O, AI, PM, O3) to a TEMPO Harmony collection ID.
- **Capabilities:** Geocoding, dynamic spatial bounds from (lat, lon, radius), multi-gas request, same threshold/unit conventions as `api_server.py`. Used for **fetching** multi-gas data; the web app uses it conceptually but loads from disk via `find_latest_file_for_gas` in practice.

### 3.5 weather_service.py

- **Dependencies:** `requests`, `python-dotenv`; `WEATHER_API_KEY` from `.env`.
- **Endpoints used:** WeatherAPI.com `current.json` and `forecast.json` with `aqi=yes`.
- **get_weather_data(lat, lon, days):** Returns location, current (temp, humidity, wind, condition), `air_quality` (if available), and forecast days.
- **get_pollutant_movement_prediction(lat, lon):** Calls `get_weather_data`, then `pollutant_predictor.predict_pollutant_movement(forecast_hours)` for next 3 hours; returns location + `predictions_next_3h`.

### 3.6 pollutant_predictor.py

- **Function:** `predict_pollutant_movement(hourly_data)` — list of hourly forecast dicts from WeatherAPI.
- **Logic:** For hours 1–3: wind vector → displacement (dx, dy) in km; humidity-based dispersion factor; predicted air quality per pollutant scaled by dispersion. Returns list of dicts with `time`, `wind_kph`, `wind_dir_deg`, `displacement_km`, `predicted_air_quality`.

### 3.7 groq_service.py

- **Dependencies:** `GROQ_API_KEY` from `.env`; `requests`.
- **Model:** GROQ OpenAI-compatible API, model `llama-3.1-8b-instant`.
- **Functions:**
  - `generate_weather_interpretation(weather_data, location_name)` — 2–3 sentence summary: air quality status, best time, key precaution; markdown stripped for HTML.
  - `generate_prediction_interpretation(pollutant_predictions, location_name)` — trend, best time, risk from next-3h predictions.
- **Utility:** `clean_markdown_formatting(text)` for safe display in templates.

### 3.8 GroundSensorAnalysis.py

- **Purpose:** Standalone EPA **AirNow** integration for ground-level AQI (PM2.5, PM10, O3) in the Madre wildfire region.
- **Config:** `AQI_THRESHOLDS`, `MONITORED_REGIONS`, `SPATIAL_BOUNDS`, `TIME_CONFIG`.
- **Flow:** Fetches by zip code, processes thresholds, can visualize; **not** wired into the FastAPI app. Data directory: `GroundData/`.

### 3.9 Celery ingestion and scheduler

- **Purpose:** Headless, scheduled ingestion of TEMPO data via **NASA Harmony** (production: `harmony.earthdata.nasa.gov`), persistence to `pollution_grid`, optional S3/MinIO audit, Redis last-update marker, and recompute of saved-route exposure scores.
- **Config:** `REDIS_URL` (broker and backend), `BEARER_TOKEN` or `EARTHDATA_USERNAME` / `EARTHDATA_PASSWORD` in `.env`. Optional bbox: `TEMPO_BBOX_WEST`, `TEMPO_BBOX_SOUTH`, `TEMPO_BBOX_EAST`, `TEMPO_BBOX_NORTH` (default CONUS).
- **Tasks:**
  - **fetch_tempo_hourly:** For each gas (NO2, CH2O, AI, PM, O3), calls Harmony → GeoTIFF → `services/raster_normalizer` → bulk insert into `pollution_grid`; optionally uploads GeoTIFF to S3/MinIO (`audit/geotiff/...`); sets Redis key `tempo:last_update` (TTL 3600 s); then triggers **recompute_saved_route_exposure**.
  - **recompute_saved_route_exposure:** For each row in `saved_routes`, builds route line, queries `pollution_grid` with `ST_Intersects` for the latest hour, computes exposure score, updates `last_computed_score` and `last_updated_at`.
- **Beat schedule:** `fetch_tempo_hourly` runs hourly at minute 0 (UTC).
- **Running (from project root):**
  - **Worker:** `celery -A celery_app worker -l info`
  - **Beat:** `celery -A celery_app beat -l info`
  - **Development (worker + beat in one process):** `celery -A celery_app worker -l info -B`
- **Dependencies:** `celery[redis]`, `rasterio`, `psycopg2-binary` (sync DB for workers). Database URL is derived for sync use by replacing `postgresql+asyncpg` with `postgresql+psycopg2`.

---

## 4. Web Interface and Routes

### 4.1 Pages

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | **Index:** Form for location (name or lat/lon), radius, gases (NO2, CH2O, AI, PM, O3), “Include Weather”, “Include Pollutant Movement Prediction”. |
| `/analyze` | POST | Runs analysis; returns **result.html** with multi-gas image, per-gas tripanels, alerts, hotspots, weather, predictions, GROQ interpretations, Leaflet map. |
| `/route` | POST | **Route safety:** Origin/destination (geocoded), gases, grid step. Returns **route.html** with OSRM route(s), exposure scoring, safest route selection, hotspot overlay. |
| `/route/alternate` | GET | Same as route analysis with query params; renders route page. |

### 4.2 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/weather` | GET | `lat`, `lon`, `days` — returns WeatherAPI.com response (cached in Redis when configured). |
| `/api/pollutant_movement` | GET | `lat`, `lon` — next-3h pollutant movement predictions (cached in Redis when configured). |
| `/api/combined_analysis` | GET | `lat`, `lon`, `radius`, `gases` — combined weather + satellite alerts/hotspots + overall status. |
| `/api/analyze` | POST | Form: location, latitude, longitude, radius, gases — returns JSON with location, coordinates, gases, overall_status, alerts, hotspots, image_url. |
| `/api/hotspots` | GET | `location` or `latitude`/`longitude`, `radius`, `gases` — returns GeoJSON FeatureCollection of hotspots (for maps). |
| **Auth** | | |
| `/auth/register` | POST | Body: `email`, `password` — create user; returns 201 User or 409 if email exists. |
| `/auth/login` | POST | Body: `email`, `password` — returns `access_token`, `token_type: bearer`. |
| `/auth/me` | GET | Header: `Authorization: Bearer <token>` — returns current user (protected). |
| **Saved routes** (all require `Authorization: Bearer <token>`) | | |
| `/api/saved-routes` | POST | Body: `origin_lat`, `origin_lon`, `dest_lat`, `dest_lon`, optional `activity_type` — create saved route; returns 201. |
| `/api/saved-routes` | GET | List saved routes for current user. |
| `/api/saved-routes/{route_id}` | GET | Get one saved route (404 if not found or not owned). |
| `/api/saved-routes/{route_id}` | DELETE | Delete saved route (204). |

### 4.3 Frontend Assets

- **Templates:** Jinja2; inline and shared styles; Leaflet (result + route) for maps.
- **Static:** `style.css`; generated images under `static/outputs/`.
- **Maps:** OpenStreetMap tiles; result page: single map with overlay; route page: route segments colored by severity, origin/destination markers, hotspot circles.

---

## 5. Route Safety (Algorithm Summary)

- **Geocoding:** `robust_geocode` — coordinates string, place name, or name + US/California bias.
- **Routing:** `fetch_osrm_routes(o_lat, o_lon, d_lat, d_lon)` — OSRM public driving API; optional alternatives; returns list of routes with GeoJSON geometry.
- **Sampling:** `resample_polyline_km(coords, step_km)` — resample route to points roughly every `step_km` km.
- **Exposure scoring:** `score_route_exposure(samples, gas_data, gas_list, proximity_km, hotspot_circles, ...)` — for each sample point, max severity across gases (and hotspot circles); per-point severity list; “blocked” if any point ≥ `hard_block_threshold` (3). Blocked routes get a large score penalty so the safest route is chosen (unblocked preferred, then by score, then by distance).
- **Safest route:** Among OSRM alternatives (or single direct line if OSRM fails), the route with lowest exposure score is marked `safest: true` and returned; others are dropped in the current implementation (only safest is sent to template).
- **Visualization:** Route drawn as segments colored by severity (green → yellow → orange → red → purple); danger points and hotspots rendered on Leaflet.

---

## 6. Pollution Thresholds (Reference)

Defined in `api_server.POLLUTION_THRESHOLDS` (and mirrored in `tempo_all.py` / `TEMPO.py` for consistency):

| Gas | Moderate | Unhealthy | Very Unhealthy | Hazardous |
|-----|----------|-----------|----------------|-----------|
| NO2 | 5.0e15   | 1.0e16    | 2.0e16         | 3.0e16 (molecules/cm²) |
| CH2O| 8.0e15   | 1.6e16    | 3.2e16         | 6.4e16 (molecules/cm²) |
| AI  | 1.0      | 2.0       | 4.0            | 7.0 (index) |
| PM  | 0.2      | 0.5       | 1.0            | 2.0 (dimensionless) |
| O3  | 220      | 280       | 400            | 500 (Dobson Units) |

Severity levels: 0 = good, 1 = moderate, 2 = unhealthy, 3 = very unhealthy, 4 = hazardous.

---

## 7. Dependencies (requirements.txt)

- **Web:** fastapi, uvicorn, jinja2, python-multipart  
- **Geocoding:** geopy  
- **Scientific:** numpy, scipy, xarray  
- **Viz:** matplotlib, cartopy  
- **Data structures:** datatree  
- **HTTP:** requests  
- **Data layer:** sqlalchemy[asyncio], asyncpg, geoalchemy2, alembic, redis, boto3, pydantic-settings  
- **Auth:** passlib[bcrypt], python-jose[cryptography], email-validator  

Note: Harmony client is used only in `TEMPO.py` and `tempo_all.py` (optional for data fetch).

---

## 8. Configuration and Environment

- **`.env`** (see `.env.example`; do not commit `.env`):  
  - **Database:** `DATABASE_URL` — e.g. `postgresql+asyncpg://postgres:postgres@localhost:5432/aeris`.  
  - **Redis:** `REDIS_URL` — e.g. `redis://localhost:6379/0` (empty = no cache).  
  - **JWT:** `SECRET_KEY`, `ALGORITHM` (default HS256), `ACCESS_TOKEN_EXPIRE_MINUTES`.  
  - **Object storage:** `OBJECT_STORAGE_PROVIDER` (minio | s3), `OBJECT_STORAGE_ENDPOINT_URL` (MinIO), `OBJECT_STORAGE_BUCKET`; for S3: `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`.  
  - **Feature flag:** `PERSIST_POLLUTION_GRID` (true/false) — persist pollution grid cells to PostGIS after analysis.  
  - **Existing:** `WEATHER_API_KEY`, `GROQ_API_KEY` (optional).  
- **Customization (from README):**
  - `SPATIAL_BOUNDS` / `TIME_CONFIG` — in `TEMPO.py` for Harmony fetch.
  - `thresholds` — in `api_server.py` (and tempo_all/TEMPO for consistency).
  - Templates — `templates/` for UI changes.

---

## 9. Data Flow Summary

1. **TEMPO data:** Either pre-downloaded into `TempData/` (and optionally per-gas subdirs), or metadata in `netcdf_files` with blobs in S3/MinIO. Resolver: latest per gas from DB → download to temp file → pass as `file_overrides` into `load_and_analyze_for_gases`; fallback to filesystem scan when object storage not configured.
2. **Web request:** User submits location + parameters → geocode (if needed) → resolve NetCDF paths (DB + object storage or TempData) → `load_and_analyze_for_gases` → optionally persist pollution grid when `PERSIST_POLLUTION_GRID=true` → hotspots + alerts.
3. **Images:** Multi-gas and tripanel figures written to `static/outputs/`; URLs passed to templates.
4. **Weather/predictions:** Optional; when enabled, responses are cached in Redis (when configured); GROQ summaries generated when key present.
5. **Route:** OSRM routes → resample → exposure score with pollution grids + hotspot circles → safest route and GeoJSON hotspots to template.
6. **Auth:** Register/login issue JWT; saved-routes CRUD use `get_current_user` and store `user_id`.

---

## 10. Current Limitations and Notes

- **Data availability:** Web app expects existing NetCDF in `TempData/` or in object storage with metadata in `netcdf_files`; no automatic Harmony fetch from the UI.
- **Ground sensors:** `GroundSensorAnalysis.py` is standalone; not integrated into FastAPI.
- **Route:** Only the single “safest” route is returned to the route page; alternatives are computed but not shown.
- **A* avoid pollution:** `a_star_avoid_pollution` exists in `api_server` but is not used in the current route flow (OSRM + exposure scoring is used instead).
- **DB/Redis/object storage:** All optional; app runs with fallbacks (no DB = no auth/saved-routes/object-storage resolver; no Redis = no cache; no object storage = TempData only). Use `docker-compose up -d` and `alembic upgrade head` for full data layer.

This document reflects the state of the codebase as of the latest review and serves as the single source of truth for architecture, functionality, and utilities.
