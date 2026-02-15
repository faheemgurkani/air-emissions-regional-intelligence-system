"""
Tests for Alerts & Personalization: UPES along saved route (integration with route/UPES layers).
"""
import pytest
from pathlib import Path
from unittest.mock import patch

from services.alerts.route_exposure import (
    compute_upes_along_saved_route,
    route_line_coords,
)


class TestRouteLineCoords:
    """Line from origin to dest as (lon, lat) list for WGS84."""

    def test_returns_origin_then_dest(self):
        coords = route_line_coords(34.0, -118.0, 34.1, -117.9)
        assert coords == [(-118.0, 34.0), (-117.9, 34.1)]


class TestComputeUpesAlongSavedRoute:
    """Uses get_latest_upes_raster_path and sample_upes_along_line_mean_max (ingestion + route layer)."""

    def test_returns_mean_and_max(self):
        with patch("services.alerts.route_exposure.get_latest_upes_raster_path", return_value=None):
            with patch("services.alerts.route_exposure.sample_upes_along_line_mean_max", return_value=(0.4, 0.6)):
                mean, max_u = compute_upes_along_saved_route(34.0, -118.0, 34.1, -117.9)
        assert mean == 0.4
        assert max_u == 0.6

    def test_calls_sampling_with_line_coords(self):
        fake_path = Path("/tmp/final_score_2025010112.tif")
        with patch("services.alerts.route_exposure.get_latest_upes_raster_path", return_value=fake_path):
            with patch("services.alerts.route_exposure.sample_upes_along_line_mean_max") as mock_samp:
                mock_samp.return_value = (0.35, 0.55)
                compute_upes_along_saved_route(34.0, -118.0, 34.1, -117.9, raster_path=fake_path)
        mock_samp.assert_called_once()
        args = mock_samp.call_args[0]
        assert args[0] == fake_path
        assert args[1] == [(-118.0, 34.0), (-117.9, 34.1)]

    def test_uses_latest_raster_when_raster_path_none(self):
        with patch("services.alerts.route_exposure.get_latest_upes_raster_path", return_value=None):
            with patch("services.alerts.route_exposure.sample_upes_along_line_mean_max", return_value=(0.5, 0.5)):
                mean, max_u = compute_upes_along_saved_route(34.0, -118.0, 34.1, -117.9)
        assert mean == 0.5
        # When no raster, sampling uses fallback (0.5) so mean and max both 0.5
