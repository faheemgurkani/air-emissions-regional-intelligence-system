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
    include=["tasks.pollution_tasks"],
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

# Celery Beat: run fetch_tempo_hourly every hour at minute 0
app.conf.beat_schedule = {
    "fetch-tempo-hourly": {
        "task": "tasks.pollution_tasks.fetch_tempo_hourly",
        "schedule": crontab(minute=0),
    },
}
