"""
Tests for UPES core (OVERALL_PLAN section 3: Unified Pollution Exposure Score).
Verifies: Score = sum(w_g * normalized(gas)), default weights, HDF/WTF/TF, FinalScore, EMA.
"""
import numpy as np
import pytest

from config import UPES_DEFAULT_WEIGHTS
from services.upes.core import (
    apply_ema,
    compute_final_score,
    compute_satellite_score,
    humidity_dispersion_factor,
    traffic_factor,
    wind_factor,
)
from services.upes.preprocessing import normalize_gas, normalize_gas_with_bounds


class TestUPESDefaultWeights:
    """Plan: NO2→0.3, PM→0.35, O3→0.2, CH2O→0.1, AI→0.05."""

    def test_weights_match_plan(self):
        assert UPES_DEFAULT_WEIGHTS["NO2"] == 0.3
        assert UPES_DEFAULT_WEIGHTS["PM"] == 0.35
        assert UPES_DEFAULT_WEIGHTS["O3"] == 0.2
        assert UPES_DEFAULT_WEIGHTS["CH2O"] == 0.1
        assert UPES_DEFAULT_WEIGHTS["AI"] == 0.05

    def test_weights_sum_to_one(self):
        assert abs(sum(UPES_DEFAULT_WEIGHTS.values()) - 1.0) < 1e-9


class TestNormalizedGasZeroToOne:
    """Plan: normalized(gas) = value scaled 0–1."""

    def test_normalize_gas_clips_to_zero_one(self):
        arr = np.array([-1.0, 0.0, 0.5, 1.0, 2.0])
        out = normalize_gas(arr, 0.0, 1.0)
        np.testing.assert_array_almost_equal(out, [0.0, 0.0, 0.5, 1.0, 1.0])

    def test_normalize_gas_with_bounds_produces_zero_one(self):
        arr = np.array([10.0, 20.0, 30.0, 40.0])
        out = normalize_gas_with_bounds(arr, use_percentiles=True)
        assert out.min() >= 0.0 and out.max() <= 1.0


class TestComputeSatelliteScore:
    """Plan: Score = sum_g w_g * normalized(gas)."""

    def test_single_gas(self):
        norm_no2 = np.array([0.0, 0.5, 1.0])
        score = compute_satellite_score({"NO2": norm_no2})
        expected = UPES_DEFAULT_WEIGHTS["NO2"] * norm_no2
        np.testing.assert_array_almost_equal(score, expected)

    def test_multiple_gases_sum_weights_times_normalized(self):
        a = np.array([1.0, 0.0])
        b = np.array([0.0, 1.0])
        score = compute_satellite_score({"NO2": a, "O3": b})
        np.testing.assert_array_almost_equal(score, 0.3 * a + 0.2 * b)


class TestHumidityDispersionFactor:
    """Plan: Add humidity dispersion factor."""

    def test_hdf_in_zero_one(self):
        assert 0 <= humidity_dispersion_factor(0) <= 1
        assert 0 <= humidity_dispersion_factor(50) <= 1
        assert 0 <= humidity_dispersion_factor(100) <= 1

    def test_high_humidity_lowers_factor(self):
        assert humidity_dispersion_factor(80) < humidity_dispersion_factor(20)


class TestWindFactor:
    """Plan: Add wind directional transport model."""

    def test_wtf_in_zero_one(self):
        assert 0 <= wind_factor(0, 0, 0) <= 1
        assert 0 <= wind_factor(25, 90, 0) <= 1


class TestTrafficFactor:
    """Plan: Add traffic factor."""

    def test_tf_default_one_when_zero_traffic(self):
        assert traffic_factor(0.0) == 1.0

    def test_tf_increases_with_density(self):
        assert traffic_factor(0.5) >= 1.0
        assert traffic_factor(1.0) >= traffic_factor(0.5)


class TestComputeFinalScore:
    """Plan: FinalScore = (SatelliteScore × WindFactor × TrafficFactor); doc also lists humidity."""

    def test_final_score_is_satellite_times_factors(self):
        sat = np.array([0.5, 1.0])
        out = compute_final_score(sat, hdf=1.0, wtf=0.8, tf=1.0)
        np.testing.assert_array_almost_equal(out, sat * 0.8)

    def test_ema_smoothing_when_previous_given(self):
        current = np.array([1.0, 0.0])
        previous = np.array([0.0, 1.0])
        out = apply_ema(current, previous, lam=0.5)
        np.testing.assert_array_almost_equal(out, [0.5, 0.5])
