"""
Tests for SQLAlchemy + GeoAlchemy2 models (DATA_LAYER — PostgreSQL + PostGIS).
Covers User, SavedRoute, PollutionGrid, RouteExposureHistory, AlertLog, NetcdfFile.
"""
import pytest
from sqlalchemy import CheckConstraint, inspect

from database.models import (
    AlertLog,
    Base,
    NetcdfFile,
    PollutionGrid,
    RouteExposureHistory,
    SavedRoute,
    User,
)


class TestUserModel:
    """User table: email, password_hash, notification_preferences, preferred_activity, exposure_sensitivity_level."""

    def test_user_table_name(self):
        assert User.__tablename__ == "users"

    def test_user_columns_exist(self):
        mapper = inspect(User)
        col_names = {c.key for c in mapper.columns}
        assert "id" in col_names
        assert "email" in col_names
        assert "password_hash" in col_names
        assert "notification_preferences" in col_names
        assert "preferred_activity" in col_names
        assert "exposure_sensitivity_level" in col_names
        assert "created_at" in col_names
        assert "updated_at" in col_names

    def test_user_preferred_activity_check_constraint_exists(self):
        checks = [c for c in User.__table_args__ if isinstance(c, CheckConstraint)]
        activity_check = next((c for c in checks if "preferred_activity" in (c.name or "")), None)
        assert activity_check is not None

    def test_user_exposure_sensitivity_check_exists(self):
        checks = [c for c in User.__table_args__ if isinstance(c, CheckConstraint)]
        sens_check = next((c for c in checks if "exposure_sensitivity_level" in (c.name or "")), None)
        assert sens_check is not None


class TestSavedRouteModel:
    """SavedRoute: user_id, origin/dest lat/lon, activity_type, last_computed_score, last_upes_*."""

    def test_saved_route_table_name(self):
        assert SavedRoute.__tablename__ == "saved_routes"

    def test_saved_route_columns_exist(self):
        mapper = inspect(SavedRoute)
        col_names = {c.key for c in mapper.columns}
        assert "user_id" in col_names
        assert "origin_lat" in col_names
        assert "origin_lon" in col_names
        assert "dest_lat" in col_names
        assert "dest_lon" in col_names
        assert "activity_type" in col_names
        assert "last_computed_score" in col_names
        assert "last_updated_at" in col_names
        assert "last_upes_score" in col_names
        assert "last_upes_updated_at" in col_names

    def test_saved_route_activity_type_check_exists(self):
        checks = [c for c in SavedRoute.__table_args__ if isinstance(c, CheckConstraint)]
        assert any("activity_type" in (c.name or "") for c in checks)


class TestPollutionGridModel:
    """PollutionGrid: timestamp, gas_type, geom (PostGIS POLYGON SRID 4326), pollution_value, severity_level."""

    def test_pollution_grid_table_name(self):
        assert PollutionGrid.__tablename__ == "pollution_grid"

    def test_pollution_grid_columns_exist(self):
        mapper = inspect(PollutionGrid)
        col_names = {c.key for c in mapper.columns}
        assert "timestamp" in col_names
        assert "gas_type" in col_names
        assert "geom" in col_names
        assert "pollution_value" in col_names
        assert "severity_level" in col_names

    def test_pollution_grid_severity_check_exists(self):
        checks = [c for c in PollutionGrid.__table_args__ if isinstance(c, CheckConstraint)]
        assert any("severity_level" in (c.name or "") for c in checks)


class TestRouteExposureHistoryModel:
    """RouteExposureHistory: route_id, timestamp, upes_score, max_upes_along_route, score_source."""

    def test_route_exposure_history_table_name(self):
        assert RouteExposureHistory.__tablename__ == "route_exposure_history"

    def test_route_exposure_history_columns_exist(self):
        mapper = inspect(RouteExposureHistory)
        col_names = {c.key for c in mapper.columns}
        assert "route_id" in col_names
        assert "timestamp" in col_names
        assert "upes_score" in col_names
        assert "score_source" in col_names


class TestAlertLogModel:
    """AlertLog: user_id, route_id, alert_type, score_before/after, threshold, alert_metadata (DB: metadata), notified_channels."""

    def test_alert_log_table_name(self):
        assert AlertLog.__tablename__ == "alert_log"

    def test_alert_log_columns_exist(self):
        mapper = inspect(AlertLog)
        col_names = {c.key for c in mapper.columns}
        assert "user_id" in col_names
        assert "route_id" in col_names
        assert "alert_type" in col_names
        assert "score_before" in col_names
        assert "score_after" in col_names
        # DB column "metadata" mapped as alert_metadata (SQLAlchemy may expose key as "metadata" or "alert_metadata")
        assert "metadata" in col_names or "alert_metadata" in col_names
        assert "created_at" in col_names



class TestNetcdfFileModel:
    """NetcdfFile: file_name, bucket_path, timestamp, gas_type."""

    def test_netcdf_files_table_name(self):
        assert NetcdfFile.__tablename__ == "netcdf_files"

    def test_netcdf_file_columns_exist(self):
        mapper = inspect(NetcdfFile)
        col_names = {c.key for c in mapper.columns}
        assert "file_name" in col_names
        assert "bucket_path" in col_names
        assert "timestamp" in col_names
        assert "gas_type" in col_names


class TestBaseMetadata:
    """Ensure all DATA_LAYER tables are present in Base.metadata."""

    def test_all_tables_registered(self):
        tables = set(Base.metadata.tables.keys())
        assert "users" in tables
        assert "saved_routes" in tables
        assert "pollution_grid" in tables
        assert "route_exposure_history" in tables
        assert "alert_log" in tables
        assert "netcdf_files" in tables
