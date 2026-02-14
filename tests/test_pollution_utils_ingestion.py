"""
Tests for pollution_utils used by ingestion (DATA INGESTION): thresholds and classify_pollution_level.
"""
import numpy as np
import pytest

from pollution_utils import POLLUTION_THRESHOLDS, classify_pollution_level


class TestPollutionThresholds:
    """All five gases must have moderate, unhealthy, very_unhealthy, hazardous."""

    def test_all_gases_defined(self):
        required = {"NO2", "CH2O", "AI", "PM", "O3"}
        assert set(POLLUTION_THRESHOLDS.keys()) == required

    def test_each_gas_has_four_levels(self):
        for gas, levels in POLLUTION_THRESHOLDS.items():
            assert "moderate" in levels
            assert "unhealthy" in levels
            assert "very_unhealthy" in levels
            assert "hazardous" in levels


class TestClassifyPollutionLevel:
    """Severity 0–4; level names match doc."""

    def test_good_returns_zero(self):
        name, sev = classify_pollution_level(0.0, "NO2")
        assert name == "good"
        assert sev == 0

    def test_moderate_returns_one(self):
        # NO2 moderate >= 5e15
        name, sev = classify_pollution_level(6e15, "NO2")
        assert name == "moderate"
        assert sev == 1

    def test_hazardous_returns_four(self):
        name, sev = classify_pollution_level(4e16, "NO2")
        assert name == "hazardous"
        assert sev == 4

    def test_nan_returns_no_data_zero(self):
        name, sev = classify_pollution_level(float("nan"), "NO2")
        assert name == "no_data"
        assert sev == 0

    def test_unknown_gas_returns_no_data_zero(self):
        name, sev = classify_pollution_level(1.0, "UNKNOWN")
        assert name == "no_data"
        assert sev == 0
