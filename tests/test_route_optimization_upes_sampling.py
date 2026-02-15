"""
Tests for UPES sampling along line (ROUTE_OPTIMIZATION_ENGINE).
"""
import os
import tempfile
from pathlib import Path

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")
from rasterio.crs import CRS
from rasterio.transform import from_bounds

from services.route_optimization.upes_sampling import (
    DEFAULT_UPES_FALLBACK,
    _resample_line,
    sample_upes_along_line,
    sample_upes_along_line_mean_max,
)


class TestResampleLine:
    def test_empty_returns_empty(self):
        assert _resample_line([], 50.0) == []

    def test_single_point_returns_same(self):
        assert _resample_line([(-118.0, 34.0)], 50.0) == [(-118.0, 34.0)]

    def test_two_points_short_segment(self):
        coords = [(-118.0, 34.0), (-117.99, 34.0)]
        out = _resample_line(coords, 50000.0)
        assert out[0] == coords[0]
        assert out[-1] == coords[-1]

    def test_step_zero_returns_original(self):
        coords = [(-118.0, 34.0), (-117.0, 35.0)]
        out = _resample_line(coords, 0)
        assert out == coords


class TestSampleUpesAlongLine:
    def test_empty_coords_returns_fallback(self):
        assert sample_upes_along_line(None, [], 50) == DEFAULT_UPES_FALLBACK
        assert sample_upes_along_line("/nonexistent.tif", [], 50) == DEFAULT_UPES_FALLBACK

    def test_none_raster_returns_fallback(self):
        coords = [(-118.0, 34.0), (-117.0, 34.0)]
        assert sample_upes_along_line(None, coords) == DEFAULT_UPES_FALLBACK

    def test_missing_file_returns_fallback(self):
        coords = [(-118.0, 34.0), (-117.0, 34.0)]
        assert sample_upes_along_line("/nonexistent.tif", coords) == DEFAULT_UPES_FALLBACK

    def test_valid_raster_returns_mean_in_0_1(self):
        with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as f:
            path = f.name
        try:
            west, south, east, north = -118.5, 33.5, -117.5, 34.5
            w, h = 10, 10
            transform = from_bounds(west, south, east, north, w, h)
            data = np.full((h, w), 0.3, dtype=np.float32)
            with rasterio.open(
                path, "w", driver="GTiff", height=h, width=w, count=1,
                dtype=data.dtype, crs=CRS.from_epsg(4326), transform=transform,
            ) as dst:
                dst.write(data, 1)
            coords = [(-118.0, 34.0), (-117.8, 34.0), (-117.5, 34.2)]
            mean = sample_upes_along_line(path, coords, step_m=50)
            assert 0 <= mean <= 1
            assert abs(mean - 0.3) < 0.2
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_custom_fallback(self):
        coords = [(-118.0, 34.0)]
        assert sample_upes_along_line(None, coords, fallback=0.7) == 0.7


class TestSampleUpesAlongLineMeanMax:
    def test_no_raster_returns_fallback_pair(self):
        coords = [(-118.0, 34.0)]
        mean, mx = sample_upes_along_line_mean_max(None, coords)
        assert mean == DEFAULT_UPES_FALLBACK and mx == DEFAULT_UPES_FALLBACK

    def test_valid_raster_returns_mean_and_max(self):
        with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as f:
            path = f.name
        try:
            west, south, east, north = -118.5, 33.5, -117.5, 34.5
            w, h = 10, 10
            transform = from_bounds(west, south, east, north, w, h)
            data = np.array([[0.2, 0.8], [0.5, 0.3]], dtype=np.float32)
            data = np.tile(data, (5, 5))
            with rasterio.open(
                path, "w", driver="GTiff", height=h, width=w, count=1,
                dtype=data.dtype, crs=CRS.from_epsg(4326), transform=transform,
            ) as dst:
                dst.write(data, 1)
            coords = [(-118.0, 34.0), (-117.5, 34.0)]
            mean, mx = sample_upes_along_line_mean_max(path, coords, step_m=50)
            assert 0 <= mean <= 1 and 0 <= mx <= 1
            assert mx >= mean
        finally:
            if os.path.exists(path):
                os.unlink(path)
