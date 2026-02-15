# Alerts & Personalization Engine — Verification and n8n Setup

This document verifies the **Alerts & Personalization** backend layer ([ALERTS_AND_PERSONALIZATION.md](ALERTS_AND_PERSONALIZATION.md)), its **integration with previous backend layers** (Data, Data Ingestion, Route/Pollution Intelligence), and explains **how to set up n8n workflows** to receive and deliver alerts.

---

## 1. Verification Summary

| Area | Implementation | Tests |
|------|----------------|-------|
| Sensitivity mapping (1–5 → scale/label) | `services/alerts/constants.py` | `tests/test_alerts_constants.py` |
| Alert detection (deterioration, hazard, wind shift, time-based) | `services/alerts/detection.py` | `tests/test_alerts_detection.py` |
| UPES along saved route (integration with UPES raster) | `services/alerts/route_exposure.py` | `tests/test_alerts_route_exposure.py` |
| Celery tasks (score routes, run pipeline, webhook payload) | `tasks/alert_tasks.py` | `tests/test_alert_tasks.py` |
| API GET /api/alerts, PATCH /auth/me | `api_server.py` | `tests/test_alerts_api.py` |
| DB models | `database/models.py` (AlertLog, RouteExposureHistory; User.notification_preferences, exposure_sensitivity_level; SavedRoute.last_upes_*) | `tests/test_database_models.py` |

**Run alerts tests:** `pytest tests/test_alerts_constants.py tests/test_alerts_detection.py tests/test_alerts_route_exposure.py tests/test_alert_tasks.py tests/test_alerts_api.py -v`

---

## 2. Integration with Previous Backend Layers

### 2.1 Data Layer

| Contract | Alerts usage | Status |
|----------|--------------|--------|
| **PostgreSQL** | `alert_log`, `route_exposure_history`, `saved_routes` (last_upes_score, last_upes_updated_at), `users` (exposure_sensitivity_level, notification_preferences). Celery tasks use sync session (`_get_sync_session()`); API uses async `get_db()`. | ✅ |
| **Redis** | Optional; not required by alerts. Pipeline can run without Redis. | ✅ |
| **Auth** | GET /api/alerts and PATCH /auth/me are **protected** (JWT). Tasks load user via `SavedRoute.user`. | ✅ |

### 2.2 Data Ingestion and Scheduler Layer

| Contract | Alerts usage | Status |
|----------|--------------|--------|
| **UPES raster path** | `compute_saved_route_upes_scores` uses `get_latest_upes_raster_path()` (same as route engine): `upes_output_base()/hourly_scores/final_score/`. If no raster, task returns `skipped` (no crash). | ✅ |
| **Schedule** | Celery: `compute_saved_route_upes_scores` at :20, `run_alert_pipeline` at :25 (after UPES hourly). See `celery_app.py` / Beat schedule. | ✅ |
| **pollution_grid / UPES** | Route exposure is computed from **UPES final_score raster** (output of `compute_upes_hourly`), not raw pollution_grid. History and alerts use UPES scores. | ✅ |

### 2.3 Route / Pollution Intelligence Engine

| Contract | Alerts usage | Status |
|----------|--------------|--------|
| **UPES sampling** | `services/alerts/route_exposure.compute_upes_along_saved_route` uses `get_latest_upes_raster_path()` and `sample_upes_along_line_mean_max()` from the route optimization module. Same raster and same sampling logic for consistency. | ✅ |
| **No circular dependency** | Alerts call into route_exposure → graph_builder (get_latest_upes_raster_path) and upes_sampling; route engine does not depend on alerts. | ✅ |

---

## 3. n8n Webhook Contract (Reminder)

- **Method:** POST  
- **URL:** Set in backend as `ALERTS_N8N_WEBHOOK_URL` (e.g. your n8n Webhook node URL).  
- **Content-Type:** application/json  
- **Body:**

```json
{
  "alerts": [
    {
      "alert_id": 123,
      "user_id": 1,
      "route_id": 2,
      "alert_type": "route_deterioration",
      "message": "Route exposure increased from 0.30 to 0.42.",
      "score_before": 0.3,
      "score_after": 0.42,
      "channels": ["email", "in_app"]
    }
  ],
  "timestamp": "2025-02-14T12:25:00.000000+00:00"
}
```

- **alert_type** can be: `route_deterioration`, `hazard`, `wind_shift`, `time_based`.  
- **channels** is derived from the user’s `notification_preferences` (e.g. `{"email": true, "push": false, "in_app": true}` → `["email", "in_app"]`). Use it to decide which delivery branch to run in n8n.

---

## 4. How to Establish n8n Workflows to Connect with the Backend

### Step 1: Create a Webhook trigger in n8n

1. In n8n, add a **Webhook** node.  
2. Set **HTTP Method** to `POST`.  
3. Set **Path** to something like `aeris-alerts` (or leave default).  
4. **Production URL** will look like:  
   `https://<your-n8n-domain>/webhook/<path>`  
   or for n8n cloud:  
   `https://<your-instance>.app.n8n.cloud/webhook/<path>`.  
5. Copy this **Production URL** and set it in your backend `.env` as:  
   `ALERTS_N8N_WEBHOOK_URL=https://...`  
   (No trailing slash needed.)

### Step 2: Payload format your workflow will receive

Each execution will have a **single** request body. Parse it in n8n as JSON:

- **`body.alerts`** — array of alert objects (one or more).  
- **`body.timestamp`** — ISO timestamp string.

You can use a **Code** node or **Set** node to map:

- `$json.body.alerts` → list of alerts  
- For “loop over alerts”, use n8n **SplitOut** or **Loop Over Items** so each alert is processed (e.g. per user/route/channel).

### Step 3: Branch by `alert_type` (optional)

If you want different logic per alert type:

- Add an **IF** node (or **Switch**):  
  - Condition: `alert_type === 'route_deterioration'` → one branch  
  - `alert_type === 'hazard'` → another  
  - `alert_type === 'wind_shift'` → another  
  - `alert_type === 'time_based'` → another  
- Downstream, you can still use the same **channels** to decide delivery (email / push / in_app).

### Step 4: Use `channels` to route delivery

For each alert (or after looping):

- Add **IF** nodes (or **Switch**) on `channels`:
  - If `channels` contains **"email"** → run **Email** node (SMTP, SendGrid, etc.). Use `message` (and optionally `alert_type`, `score_after`) for the body.
  - If `channels` contains **"push"** → run **Push** (e.g. FCM, OneSignal). You’ll need a mapping from `user_id` to device token (e.g. from your API or DB).
  - If `channels` contains **"in_app"** → you can either:
    - Call your backend (e.g. an internal endpoint that stores “unread” state), or  
    - Do nothing here and rely on the app polling **GET /api/alerts** (alerts are already stored in `alert_log`).

So: **one Webhook workflow** that receives the POST, optionally branches by `alert_type`, then for each alert branches by `channels` to Email / Push / In-App as needed.

### Step 5: Minimal workflow structure (conceptual)

```
[Webhook (POST)] → [Parse JSON / Set] → [Loop Over Items (alerts)]
  → [IF: "email" in channels] → [Send Email]
  → [IF: "push" in channels] → [Push notification]
  → [IF: "in_app" in channels] → (optional: call API or skip; app already has GET /api/alerts)
```

### Step 6: Security (recommended)

- Prefer **HTTPS** for the webhook URL.  
- Optionally add a **secret** query param or header and check it in n8n (e.g. **Header Auth** or a **Code** node that compares a shared secret). The backend currently does not send a secret; you can add one in `alert_tasks.py` (e.g. `X-Webhook-Secret`) and verify it in n8n.  
- Restrict n8n webhook URL to your backend’s IP in production if possible.

### Step 7: Testing the connection

1. Set `ALERTS_N8N_WEBHOOK_URL` and run the alert pipeline (e.g. trigger `run_alert_pipeline` or wait for :25).  
2. In n8n, use **Listen for Test Event** on the Webhook node and trigger an alert (e.g. create a saved route, run UPES, then run alert pipeline).  
3. Confirm the POST body in n8n matches the contract above and your branches (alert_type, channels) behave as expected.

---

## 5. Summary

- **Alerts & Personalization** is implemented and tested (constants, detection, route exposure, Celery tasks, API, DB).  
- It **integrates** with the Data Layer (PostgreSQL, auth), Data Ingestion (UPES raster path, schedule), and Route/Pollution Intelligence (same UPES raster and sampling).  
- **n8n:** Set `ALERTS_N8N_WEBHOOK_URL` to your n8n Webhook POST URL; use one workflow with Webhook → (optional split by alert_type) → branch by `channels` to Email / Push / In-App. The backend sends the payload in the format described in §3 and in [ALERTS_AND_PERSONALIZATION.md](ALERTS_AND_PERSONALIZATION.md) §6.
