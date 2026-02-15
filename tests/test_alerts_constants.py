"""
Tests for Alerts & Personalization: sensitivity mapping (ALERTS_AND_PERSONALIZATION.md §4).
"""
import pytest

from services.alerts.constants import (
    SENSITIVITY_LABEL,
    SENSITIVITY_SCALE,
    get_sensitivity_label,
    get_sensitivity_scale,
)


class TestSensitivityScale:
    """1,2 -> 1.0 (Normal); 3,4 -> 0.7 (Sensitive); 5 -> 0.5 (Asthmatic)."""

    def test_level_1_2_normal_scale_one(self):
        assert get_sensitivity_scale(1) == 1.0
        assert get_sensitivity_scale(2) == 1.0

    def test_level_3_4_sensitive_scale_seven(self):
        assert get_sensitivity_scale(3) == 0.7
        assert get_sensitivity_scale(4) == 0.7

    def test_level_5_asthmatic_scale_five(self):
        assert get_sensitivity_scale(5) == 0.5

    def test_none_or_unknown_default_one(self):
        assert get_sensitivity_scale(None) == 1.0
        assert get_sensitivity_scale(0) == 1.0
        assert get_sensitivity_scale(99) == 1.0


class TestSensitivityLabel:
    def test_labels_match_plan(self):
        assert get_sensitivity_label(1) == "Normal"
        assert get_sensitivity_label(2) == "Normal"
        assert get_sensitivity_label(3) == "Sensitive"
        assert get_sensitivity_label(4) == "Sensitive"
        assert get_sensitivity_label(5) == "Asthmatic"

    def test_none_unknown_default_normal(self):
        assert get_sensitivity_label(None) == "Normal"
        assert get_sensitivity_label(0) == "Normal"
