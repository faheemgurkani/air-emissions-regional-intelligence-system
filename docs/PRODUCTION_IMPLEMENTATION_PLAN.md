# AERIS Backend — Production-Grade Implementation Plan

This document consolidates the **as-built** backend architecture, data flows, and priority roadmap for AERIS (Air Emissions Regional Intelligence System). It aligns the production-grade vision with the current implementation: a **modular monolith** (FastAPI + Celery) with clear domain boundaries for Ingestion, Scoring, Routing, and Alerts.

---

## 1. System Architecture Overview

AERIS is a **real-time, pollution-aware navigation system** that ingests satellite and weather data, computes unified exposure scores, offers pollution-optimized routing, and delivers personalized alerts.

### High-Level Data Flow

```
      Satellite APIs (NASA TEMPO)
                 ↓
        Traffic APIs / Weather APIs
                 ↓
          Ingestion Service
                 ↓
      ------------------------
      | Scoring Service       |
      | - UPES                |
      | - Time-decay smoothing|
      | - Humidity/Wind/Traffic|
      ------------------------
                 ↓
             PostGIS Grid
                 ↓
      ------------------------
      | Routing Service       |
      | - Pollution-aware     |
      | - Multi-objective     |
      |   (Exposure/Time/Dist)|
      ------------------------
                 ↓
      ------------------------
      | Alert Service         |
      | - Route deterioration  |
      | - Hazard and Wind shift |
      | - User personalization|
      ------------------------
                 ↓
               FastAPI
                 ↓
        Web / Mobile Frontend
```

### As-Built Architecture: Modular Monolith

The system is implemented as a **single FastAPI application** plus **Celery workers**, not as physically separate microservices. Logical domains are clearly separated and can be split into separate services later if needed:

- **Ingestion:** Celery task `fetch_tempo_hourly`, Harmony integration, raster normalization → PostGIS; see [DATA_INGESTION_AND_SCHEDULER_LAYER.md](DATA_INGESTION_AND_SCHEDULER_LAYER.md).
- **Scoring (UPES):** Celery task `compute_upes_hourly`; humidity, wind, traffic factors; GeoTIFF output; see [POLLUTION_INTELLIGENCE_ENGINE_UPES.md](POLLUTION_INTELLIGENCE_ENGINE_UPES.md).
- **Routing:** OSMnx graph, UPES along edges, multi-objective cost (α·Exposure + β·Distance + γ·Time), mode modifiers, Dijkstra/k-shortest; see [ROUTE_OPTIMIZATION_ENGINE.md](ROUTE_OPTIMIZATION_ENGINE.md).
- **Alerts:** UPES-based route scoring, deterioration/hazard/wind-shift/time-based detection, sensitivity scaling, n8n webhook; see [ALERTS_AND_PERSONALIZATION.md](ALERTS_AND_PERSONALIZATION.md).

Data layer: [DATA_LAYER.md](DATA_LAYER.md). Full API and configuration: [PROJECT_DOCUMENTATION.md](PROJECT_DOCUMENTATION.md).

---

## 2. Data Storage and Caching

| Component   | Purpose |
|------------|---------|
| **PostGIS** | Pollution grids, users, saved routes, route_exposure_history, alert_log; spatial queries. |
| **Redis**  | Cache for weather, pollutant movement, route results; pipeline timestamps (`tempo:last_update`, `upes:last_update`). |
| **Postgres** | Same as PostGIS (users, alert history, route preferences). |
| **Docker Volumes** | Persistent storage for Postgres, Redis, MinIO when using docker-compose. |

---

## 3. Scheduling and Recompute

- **Celery + Redis:** Hourly at :00 fetch TEMPO; at :15 compute UPES; at :20 compute UPES along saved routes; at :25 run alert pipeline.
- **Scalable:** Run multiple Celery workers to parallelize tasks; ingestion and scoring are independent of request load.

---

## 4. Priority Implementation Roadmap

| Step | Description                                    | Status     |
|------|------------------------------------------------|------------|
| 1    | Unified Pollution Exposure Score (UPES)        | Done       |
| 2    | PostGIS spatial storage                        | Done       |
| 3    | Hourly recompute engine (Celery + Redis)       | Done       |
| 4    | Traffic integration and weighted grid adjustment | Planned  |
| 5    | Pollution-aware routing (OSMnx + Dijkstra)   | Done       |
| 6    | Alerts and personalizations (n8n workflow)   | Done       |
| 7    | FastAPI endpoints + WebSocket push            | Partial (endpoints done; WebSocket planned) |

---

## 5. Deployment and Next Steps

- **Current:** Docker Compose provides Postgres (PostGIS), Redis, and MinIO for local development. FastAPI and Celery run on the host (or in separate containers if wired manually).
- **Optional:** Containerize the FastAPI app and Celery worker for reproducible deployment; use the same Compose stack for dependencies.
- **Planned:** Traffic API integration (phase 2) for traffic-weighted UPES; WebSocket endpoint for real-time in-app alert push (currently clients poll `GET /api/alerts`).
- **Future:** If scaling demands it, the four logical domains (Ingestion, Scoring, Routing, Alerts) can be split into independently deployable services with the same data contracts (PostGIS, Redis).

---

This plan reflects the state of the codebase and documentation as of the latest review.
