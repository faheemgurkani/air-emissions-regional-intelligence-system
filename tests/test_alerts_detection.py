"""
Tests for Alerts & Personalization: detection logic (ALERTS_AND_PERSONALIZATION.md §3).
"""
import pytest
from unittest.mock import patch

from services.alerts.detection import (
    check_hazard_alert,
    check_route_deterioration,
    check_time_based_alert,
    check_wind_shift_alert,
    run_detection,
)


class TestCheckRouteDeterioration:
    """Trigger when (curr - prev) / prev >= effective_threshold_pct; effective = base_pct * scale(level)."""

    def test_no_trigger_when_delta_below_threshold(self):
        # 15% threshold (Normal): (0.35 - 0.30) / 0.30 = 16.7% -> trigger. (0.32-0.30)/0.30 = 6.7% -> no trigger
        assert check_route_deterioration(0.30, 0.32, 1, base_pct=0.15) is None

    def test_trigger_when_delta_above_threshold(self):
        a = check_route_deterioration(0.30, 0.42, 1, base_pct=0.15)
        assert a is not None
        assert a["type"] == "route_deterioration"
        assert a["score_before"] == 0.30
        assert a["score_after"] == 0.42
        assert a["threshold"] == 0.15

    def test_sensitive_lower_threshold(self):
        # Sensitive: 0.15 * 0.7 = 0.105. (0.35-0.30)/0.30 = 16.7% > 10.5% -> trigger
        a = check_route_deterioration(0.30, 0.35, 3, base_pct=0.15)
        assert a is not None
        assert a["threshold"] == pytest.approx(0.105)

    def test_prev_zero_or_none_returns_none(self):
        assert check_route_deterioration(0, 0.5, 1) is None
        assert check_route_deterioration(0.0, 0.5, 1) is None


class TestCheckHazardAlert:
    """Trigger when max_upes_along_route >= critical_threshold (default 0.85)."""

    def test_trigger_at_or_above_threshold(self):
        a = check_hazard_alert(0.85)
        assert a is not None
        assert a["type"] == "hazard"
        assert a["score_after"] == 0.85
        a2 = check_hazard_alert(0.90)
        assert a2 is not None

    def test_no_trigger_below_threshold(self):
        assert check_hazard_alert(0.84) is None
        assert check_hazard_alert(0.5) is None

    def test_custom_threshold(self):
        assert check_hazard_alert(0.7, critical_threshold=0.8) is None
        assert check_hazard_alert(0.8, critical_threshold=0.8) is not None


class TestCheckWindShiftAlert:
    """Wind toward route: bearing(source->route) ≈ (wind_degree+180); speed >= min_speed."""

    def test_low_speed_no_trigger(self):
        assert check_wind_shift_alert(2.0, 90, 34.0, -118.0, 33.9, -118.0, min_speed_kph=5.0) is None

    def test_angle_diff_logic(self):
        # source (33.9,-118) -> route mid (34,-118): bearing north. wind_toward = 90+180 = 270 (west). diff large -> no trigger
        a = check_wind_shift_alert(10.0, 90, 34.0, -118.0, 33.9, -118.0, min_speed_kph=5.0, max_angle_deg=45.0)
        # Bearing from (33.9,-118) to (34,-118) is 0 (north). wind_toward 270. diff=90 > 45 -> None
        assert a is None

    def test_trigger_when_wind_toward_route(self):
        # Wind from south (180) -> wind_toward = 0 (north). Source south of route: bearing source->route = 0. Match.
        a = check_wind_shift_alert(10.0, 180, 34.0, -118.0, 33.9, -118.0, min_speed_kph=5.0, max_angle_deg=45.0)
        assert a is not None
        assert a["type"] == "wind_shift"
        assert "wind_kph" in a["metadata"]


class TestCheckTimeBasedAlert:
    """Trigger when current >= recent_min + margin (default 0.15)."""

    def test_no_trigger_when_recent_min_none(self):
        assert check_time_based_alert(0.5, None) is None

    def test_trigger_when_current_above_min_plus_margin(self):
        a = check_time_based_alert(0.50, 0.30, margin=0.15)
        assert a is not None
        assert a["type"] == "time_based"
        assert a["score_before"] == 0.30
        assert a["score_after"] == 0.50
        assert a["threshold"] == 0.15

    def test_no_trigger_when_within_margin(self):
        assert check_time_based_alert(0.40, 0.30, margin=0.15) is None  # 0.40 < 0.30+0.15


class TestRunDetection:
    """Aggregates all checks; adds user_id and route_id to each alert."""

    def test_returns_list_with_user_and_route_id(self):
        alerts = run_detection(
            user_id=10,
            route_id=20,
            current_upes=0.5,
            max_upes=0.9,
            prev_upes=0.3,
            recent_min_upes=0.25,
            user_sensitivity_level=1,
        )
        # Hazard should trigger (0.9 >= 0.85); deterioration (0.5-0.3)/0.3 = 66% >= 15%; time_based 0.5 >= 0.25+0.15
        assert len(alerts) >= 1
        for a in alerts:
            assert a.get("user_id") == 10
            assert a.get("route_id") == 20
            assert "type" in a

    def test_deterioration_and_hazard_both_can_trigger(self):
        alerts = run_detection(
            user_id=1,
            route_id=2,
            current_upes=0.90,
            max_upes=0.90,
            prev_upes=0.30,
            recent_min_upes=None,
            user_sensitivity_level=1,
        )
        types = [a["type"] for a in alerts]
        assert "route_deterioration" in types
        assert "hazard" in types
