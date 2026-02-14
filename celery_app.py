"""
Celery app for AERIS: broker Redis, Beat schedule for TEMPO hourly ingestion.
"""
from celery import Celery
from celery.schedules import crontab

from config import settings

broker = (settings.redis_url or "redis://localhost:6379/0").strip()
app = Celery(
    "aeris",
    broker=broker,
    backend=broker,
    include=["tasks.pollution_tasks", "tasks.alert_tasks"],
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

# Celery Beat: fetch_tempo_hourly at :00; compute_upes_hourly at :15; UPES route scores at :20; alert pipeline at :25
app.conf.beat_schedule = {
    "fetch-tempo-hourly": {
        "task": "tasks.pollution_tasks.fetch_tempo_hourly",
        "schedule": crontab(minute=0),
    },
    "compute-upes-hourly": {
        "task": "tasks.pollution_tasks.compute_upes_hourly",
        "schedule": crontab(minute=15),
    },
    "compute-saved-route-upes-scores": {
        "task": "tasks.alert_tasks.compute_saved_route_upes_scores",
        "schedule": crontab(minute=20),
    },
    "run-alert-pipeline": {
        "task": "tasks.alert_tasks.run_alert_pipeline",
        "schedule": crontab(minute=25),
    },
}
