# AERIS Tests

Tests for the **DATA_LAYER** and backend, aligned with [docs/DATA_LAYER.md](../docs/DATA_LAYER.md) and [docs/PROJECT_DOCUMENTATION.md](../docs/PROJECT_DOCUMENTATION.md).

## Scope

| Layer | Test Module | Coverage |
|-------|-------------|----------|
| **PostgreSQL + PostGIS** | `test_database_models.py` | User, SavedRoute, PollutionGrid, RouteExposureHistory, AlertLog, NetcdfFile — table names, columns, check constraints, Base.metadata |
| | `test_database_schemas.py` | Pydantic schemas: UserRegister, UserLogin, Token, SavedRouteCreate/Update/Response, UserUpdate, AlertLogResponse — validation and aliases |
| | `test_database_session.py` | `get_db()` generator (mocked), optional integration: `init_db_extensions` (PostGIS), session query (requires `DATABASE_URL`) |
| **Redis** | `test_cache.py` | Cache key builders (weather, pollutant_movement, hotspots, route_exposure, route_optimized), `cache_get`/`cache_set`, `get_weather_cached`, `get_pollutant_movement_cached` with mock Redis |
| **S3 / MinIO** | `test_storage.py` | `is_configured()` (provider/endpoint/credentials), `upload_netcdf`/`download_netcdf_to_path` errors when not configured or file missing |
| **NetCDF resolver** | `test_netcdf_resolver.py` | `resolve_netcdf_paths_for_gases`: empty when storage off, empty when no DB rows, skip gas on download failure, override + temp path on success |
| **Auth** | `test_auth.py` | Password hash/verify (skipped if bcrypt backend unavailable), JWT create/decode |
| **Data ingestion & scheduler** | `test_harmony_service.py` | TEMPO collection IDs, rangeset URL format (Harmony OGC API), token resolution, submit/job/binary response handling |
| | `test_raster_normalizer.py` | GeoTIFF → grid rows: required keys (timestamp, gas_type, geom_wkt, pollution_value, severity_level), WKT polygon, max_cells, chunk_size, NaN skipped |
| | `test_pollution_utils_ingestion.py` | POLLUTION_THRESHOLDS for all gases, `classify_pollution_level` severity 0–4 |
| | `test_pollution_tasks.py` | Bbox env (TEMPO_BBOX_*), sync DB URL (asyncpg → psycopg2) |
| | `test_data_ingestion_integration.py` | Integration: token with .env, URL structure, optional live fetch when `INGESTION_LIVE=1` |

## Data ingestion validation script

From project root, with `.env` containing `BEARER_TOKEN` or `EARTHDATA_USERNAME` + `EARTHDATA_PASSWORD`:

```bash
python -m tests.run_ingestion_validation
INGESTION_LIVE=1 python -m tests.run_ingestion_validation
```

The script checks: credentials present → bearer token resolved → rangeset URL format. With `INGESTION_LIVE=1` it runs a live Harmony fetch for NO2 (small bbox, last hour) and validates GeoTIFF + grid row format.

- **Production:** `harmony.earthdata.nasa.gov` (default). Use a token from [urs.earthdata.nasa.gov](https://urs.earthdata.nasa.gov) or set `EARTHDATA_USERNAME` / `EARTHDATA_PASSWORD` for token refresh.
- **UAT (dev/test):** set `HARMONY_USE_UAT=1` and use credentials/token from [uat.urs.earthdata.nasa.gov](https://uat.urs.earthdata.nasa.gov). TEMPO collections may differ on UAT.
- If you get **403 Forbidden**, the token is not accepted for that environment or collection (e.g. expired or UAT token used against production). Refresh the token or use matching env (UAT vs production).

## Running tests

From the project root:

```bash
# Create venv and install deps (use project requirements or minimal set for tests)
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt   # or requirements-dev.txt
pip install pytest pytest-asyncio

# Run all tests except integration (no DB/Redis required)
pytest tests/ -v -m "not integration"

# Run everything including integration (requires DATABASE_URL to PostgreSQL)
pytest tests/ -v
```

Integration tests are marked with `@pytest.mark.integration` and are skipped unless `DATABASE_URL` is set to a PostgreSQL URL (e.g. `postgresql+asyncpg://user:pass@localhost:5432/aeris`). For full DATA_LAYER integration, start Postgres+PostGIS and Redis with `docker compose up -d` and run `alembic upgrade head` before running tests with `DATABASE_URL` and optionally `REDIS_URL` set.

## Configuration

- **`pytest.ini`**: `asyncio_mode = auto`, `testpaths = tests`.
- **`conftest.py`**: Adds project root to `sys.path`, defines `mock_redis`, `sample_weather_data`, `sample_pollutant_movement`, `database_url`, and `skip_if_no_db` for integration.

## Notes

- Password hashing tests are skipped when the passlib bcrypt backend is unavailable or incompatible (e.g. certain bcrypt 4.x / passlib combinations).
- The `AlertLog` model uses Python attribute `alert_metadata` with DB column `"metadata"` to avoid clashing with SQLAlchemy’s reserved `metadata`. `AlertLogResponse` uses `validation_alias="alert_metadata"` so `model_validate(orm_row)` works.
- Data ingestion tests align with [docs/DATA_INGESTION_AND_SCHEDULER_LAYER.md](../docs/DATA_INGESTION_AND_SCHEDULER_LAYER.md) and the Harmony API notebook (rangeset URL pattern, time RFC 3339, subset=lon/lat/time).
