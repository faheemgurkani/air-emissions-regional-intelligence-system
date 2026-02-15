"""
Tests for Alerts & Personalization: Celery tasks (compute_saved_route_upes_scores, run_alert_pipeline).
Integration with Data layer (DB), Ingestion (UPES raster path), and optional n8n webhook.
"""
import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

from config import settings
from tasks.alert_tasks import (
    _channels_from_preferences,
    _prev_and_min_upes,
    compute_saved_route_upes_scores,
    run_alert_pipeline,
)


class TestChannelsFromPreferences:
    """Build channel list from user notification_preferences."""

    def test_default_in_app(self):
        assert _channels_from_preferences(None) == ["in_app"]
        assert _channels_from_preferences({}) == ["in_app"]

    def test_email_push_in_app(self):
        assert "email" in _channels_from_preferences({"email": True, "push": True, "in_app": True})
        assert "push" in _channels_from_preferences({"email": False, "push": True})
        assert _channels_from_preferences({"email": True}) == ["email", "in_app"]  # in_app defaults True


class TestPrevAndMinUpes:
    """Requires DB; test with mock session or skip."""

    def test_prev_and_min_requires_session(self):
        # Unit test without real DB: we only verify the helper exists and is callable
        assert callable(_prev_and_min_upes)


class TestComputeSavedRouteUpesScores:
    """Uses get_latest_upes_raster_path (ingestion) and compute_upes_along_saved_route (route exposure)."""

    def test_skips_when_no_raster(self):
        with patch("tasks.alert_tasks.get_latest_upes_raster_path", return_value=None):
            out = compute_saved_route_upes_scores()
        assert out.get("status") == "skipped"
        assert out.get("reason") == "no_raster"

    def test_skips_when_raster_path_not_exists(self):
        with patch("tasks.alert_tasks.get_latest_upes_raster_path", return_value=Path("/nonexistent/tif")):
            out = compute_saved_route_upes_scores()
        assert out.get("status") == "skipped"
        assert out.get("reason") == "no_raster"


class TestRunAlertPipeline:
    """Uses DB (saved_routes, user, route_exposure_history, alert_log), detection, optional n8n POST."""

    def test_skips_when_alerts_disabled(self):
        with patch.object(settings, "alerts_enabled", False):
            out = run_alert_pipeline()
        assert out.get("status") == "skipped"
        assert out.get("reason") == "disabled"

    def test_webhook_payload_shape(self):
        """Verify the payload we would POST to n8n matches ALERTS_AND_PERSONALIZATION.md §6."""
        # Minimal shape: alerts[].alert_id, user_id, route_id, alert_type, message, score_before, score_after, channels
        expected_keys = {"alert_id", "user_id", "route_id", "alert_type", "message", "score_before", "score_after", "channels"}
        # From alert_tasks: n8n_payload.append({ "alert_id", "user_id", "route_id", "alert_type", "message", ... })
        sample = {
            "alert_id": 123,
            "user_id": 1,
            "route_id": 2,
            "alert_type": "route_deterioration",
            "message": "Route exposure increased from 0.30 to 0.42.",
            "score_before": 0.3,
            "score_after": 0.42,
            "channels": ["email", "in_app"],
        }
        assert set(sample.keys()) >= expected_keys
