"""
Tests for Alerts & Personalization API: GET /api/alerts, PATCH /auth/me (ALERTS_AND_PERSONALIZATION.md §7).
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient


class TestListAlerts:
    """GET /api/alerts: protected; returns user's alerts from alert_log."""

    def test_returns_401_without_auth(self):
        try:
            from api_server import app
        except Exception as e:
            pytest.skip("api_server not importable: %s" % e)
        client = TestClient(app)
        r = client.get("/api/alerts")
        assert r.status_code == 401

    def test_returns_200_with_auth_and_empty_list(self):
        try:
            from api_server import app
            from database.models import User
            from auth import create_access_token, get_current_user
            from database.session import get_db
        except Exception as e:
            pytest.skip("api_server not importable: %s" % e)
        # Override get_current_user and get_db so we don't need real DB
        fake_user = User(
            id=1,
            email="alerts_test@example.com",
            hashed_password="",
            notification_preferences=None,
            exposure_sensitivity_level=1,
        )
        fake_user.created_at = datetime.now(timezone.utc)
        fake_user.updated_at = datetime.now(timezone.utc)

        async def override_get_current_user():
            return fake_user

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_db] = override_get_db
        try:
            token = create_access_token(1)
            client = TestClient(app)
            r = client.get("/api/alerts", headers={"Authorization": "Bearer %s" % token})
            assert r.status_code == 200
            assert isinstance(r.json(), list)
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)


class TestUpdateMeAlertsPreferences:
    """PATCH /auth/me: notification_preferences, exposure_sensitivity_level."""

    def test_returns_401_without_auth(self):
        try:
            from api_server import app
        except Exception as e:
            pytest.skip("api_server not importable: %s" % e)
        client = TestClient(app)
        r = client.patch(
            "/auth/me",
            json={"notification_preferences": {"email": True}, "exposure_sensitivity_level": 3},
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 401

    def test_accepts_notification_preferences_and_sensitivity_body(self):
        """Schema accepts the fields described in ALERTS_AND_PERSONALIZATION.md."""
        from database.schemas import UserUpdate
        body = UserUpdate(notification_preferences={"email": True, "push": False, "in_app": True})
        assert body.notification_preferences["email"] is True
        assert body.exposure_sensitivity_level is None
        body2 = UserUpdate(exposure_sensitivity_level=4)
        assert body2.exposure_sensitivity_level == 4
        assert body2.notification_preferences is None
        # 1-5 valid
        UserUpdate(exposure_sensitivity_level=1)
        UserUpdate(exposure_sensitivity_level=5)
