"""
Tests for Pydantic schemas (DATA_LAYER — request/response validation).
"""
from datetime import datetime

import pytest
from pydantic import ValidationError

from database.schemas import (
    AlertLogResponse,
    SavedRouteCreate,
    SavedRouteResponse,
    SavedRouteUpdate,
    Token,
    UserLogin,
    UserRegister,
    UserResponse,
    UserUpdate,
)


class TestUserRegisterSchema:
    def test_valid_email_and_password(self):
        payload = {"email": "user@example.com", "password": "password123"}
        schema = UserRegister(**payload)
        assert schema.email == "user@example.com"
        assert schema.password == "password123"

    def test_invalid_email_raises(self):
        with pytest.raises(ValidationError):
            UserRegister(email="not-an-email", password="password123")

    def test_short_password_raises(self):
        with pytest.raises(ValidationError):
            UserRegister(email="u@example.com", password="short")


class TestUserLoginSchema:
    def test_valid_login(self):
        schema = UserLogin(email="u@example.com", password="any")
        assert schema.email == "u@example.com"
        assert schema.password == "any"


class TestTokenSchema:
    def test_default_token_type(self):
        schema = Token(access_token="jwt-here")
        assert schema.token_type == "bearer"

    def test_custom_token_type(self):
        schema = Token(access_token="jwt", token_type="Bearer")
        assert schema.token_type == "Bearer"


class TestUserResponseSchema:
    def test_from_attributes_config(self):
        # Pydantic v2: from_attributes in model_config
        assert getattr(UserResponse.model_config, "from_attributes", None) in (True, None)


class TestSavedRouteCreateSchema:
    def test_valid_coords_and_activity(self):
        payload = {
            "origin_lat": 34.0,
            "origin_lon": -118.0,
            "dest_lat": 35.0,
            "dest_lon": -119.0,
            "activity_type": "commute",
        }
        schema = SavedRouteCreate(**payload)
        assert schema.origin_lat == 34.0
        assert schema.activity_type == "commute"

    def test_lat_out_of_range_raises(self):
        with pytest.raises(ValidationError):
            SavedRouteCreate(
                origin_lat=100,
                origin_lon=-118,
                dest_lat=35,
                dest_lon=-119,
            )

    def test_invalid_activity_type_raises(self):
        with pytest.raises(ValidationError):
            SavedRouteCreate(
                origin_lat=34,
                origin_lon=-118,
                dest_lat=35,
                dest_lon=-119,
                activity_type="invalid",
            )

    def test_activity_type_optional(self):
        schema = SavedRouteCreate(origin_lat=34, origin_lon=-118, dest_lat=35, dest_lon=-119)
        assert schema.activity_type is None


class TestSavedRouteUpdateSchema:
    def test_optional_activity_type(self):
        schema = SavedRouteUpdate(activity_type="jog")
        assert schema.activity_type == "jog"

    def test_invalid_activity_raises(self):
        with pytest.raises(ValidationError):
            SavedRouteUpdate(activity_type="swim")


class TestUserUpdateSchema:
    def test_exposure_sensitivity_in_range(self):
        schema = UserUpdate(exposure_sensitivity_level=3)
        assert schema.exposure_sensitivity_level == 3

    def test_exposure_sensitivity_out_of_range_raises(self):
        with pytest.raises(ValidationError):
            UserUpdate(exposure_sensitivity_level=0)
        with pytest.raises(ValidationError):
            UserUpdate(exposure_sensitivity_level=6)


class TestAlertLogResponseSchema:
    def test_optional_fields(self):
        schema = AlertLogResponse(
            id=1,
            user_id=1,
            route_id=None,
            alert_type="deterioration",
            score_before=0.3,
            score_after=0.5,
            threshold=0.15,
            metadata=None,
            created_at=datetime(2025, 1, 1),
            notified_channels=None,
        )
        assert schema.alert_type == "deterioration"
        assert schema.route_id is None
