"""
Tests for raster normalizer (DATA INGESTION): GeoTIFF → pollution_grid row format.
Validates required fields, WKT geometry, and severity from pollution_utils.
"""
import os
import tempfile
from datetime import datetime, timezone

import numpy as np
import pytest
import rasterio
from rasterio.crs import CRS
from rasterio.transform import from_bounds

from services.raster_normalizer import (
    DEFAULT_CHUNK_SIZE,
    DEFAULT_MAX_CELLS,
    _cell_to_wkt,
    _pixel_bounds,
    geotiff_to_grid_rows,
)


def _make_geotiff(path: str, width: int = 10, height: int = 10, fill: float = 1.0) -> None:
    """Write a minimal GeoTIFF (WGS84) for testing."""
    west, south, east, north = -118.0, 34.0, -117.0, 35.0
    transform = from_bounds(west, south, east, north, width, height)
    data = np.full((height, width), fill, dtype=np.float64)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype=data.dtype,
        crs=CRS.from_epsg(4326),
        transform=transform,
    ) as dst:
        dst.write(data, 1)


class TestPixelBoundsAndWkt:
    def test_cell_to_wkt_closed_ring(self):
        wkt = _cell_to_wkt(-118.0, 34.0, -117.9, 34.1)
        assert "POLYGON((" in wkt
        assert wkt.strip().endswith("))")
        assert "-118.0 34.0" in wkt
        assert "-117.9 34.1" in wkt

    def test_pixel_bounds_returns_four_values(self):
        transform = from_bounds(-118, 34, -117, 35, 10, 10)
        lon_min, lat_min, lon_max, lat_max = _pixel_bounds(transform, 0, 0)
        assert lon_min < lon_max
        assert lat_min < lat_max


class TestGeotiffToGridRows:
    """Required row keys: timestamp, gas_type, geom_wkt, pollution_value, severity_level."""

    def test_row_keys_required(self):
        with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as f:
            _make_geotiff(f.name, width=4, height=4, fill=1.0)
            try:
                ts = datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
                chunks = list(geotiff_to_grid_rows(f.name, "NO2", ts, max_cells=100))
                assert len(chunks) >= 1
                for chunk in chunks:
                    for row in chunk:
                        assert "timestamp" in row
                        assert "gas_type" in row
                        assert "geom_wkt" in row
                        assert "pollution_value" in row
                        assert "severity_level" in row
                        assert row["gas_type"] == "NO2"
                        assert row["timestamp"] == ts
            finally:
                os.unlink(f.name)

    def test_geom_wkt_is_polygon(self):
        with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as f:
            _make_geotiff(f.name, width=2, height=2, fill=0.5)
            try:
                ts = datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
                chunks = list(geotiff_to_grid_rows(f.name, "O3", ts, max_cells=10))
                assert len(chunks) >= 1
                row = chunks[0][0]
                assert row["geom_wkt"].startswith("POLYGON((")
                assert " " in row["geom_wkt"]
            finally:
                os.unlink(f.name)

    def test_severity_level_in_range(self):
        with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as f:
            _make_geotiff(f.name, width=2, height=2, fill=0.0)
            try:
                ts = datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
                chunks = list(geotiff_to_grid_rows(f.name, "NO2", ts, max_cells=10))
                for chunk in chunks:
                    for row in chunk:
                        assert 0 <= row["severity_level"] <= 4
            finally:
                os.unlink(f.name)

    def test_respects_max_cells(self):
        with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as f:
            _make_geotiff(f.name, width=100, height=100, fill=1.0)
            try:
                ts = datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
                total = 0
                for chunk in geotiff_to_grid_rows(f.name, "NO2", ts, max_cells=50, chunk_size=20):
                    total += len(chunk)
                assert total <= 50
            finally:
                os.unlink(f.name)

    def test_chunk_size(self):
        with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as f:
            _make_geotiff(f.name, width=20, height=20, fill=1.0)
            try:
                ts = datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
                for chunk in geotiff_to_grid_rows(f.name, "NO2", ts, max_cells=100, chunk_size=5):
                    assert len(chunk) <= 5
            finally:
                os.unlink(f.name)

    def test_nan_skipped(self):
        with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as f:
            west, south, east, north = -118.0, 34.0, -117.0, 35.0
            transform = from_bounds(west, south, east, north, 3, 3)
            data = np.array([[np.nan, 1.0, np.nan], [1.0, np.nan, 1.0], [np.nan, 1.0, np.nan]], dtype=np.float64)
            with rasterio.open(
                f.name, "w", driver="GTiff", height=3, width=3, count=1,
                dtype=data.dtype, crs=CRS.from_epsg(4326), transform=transform,
            ) as dst:
                dst.write(data, 1)
            try:
                ts = datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
                chunks = list(geotiff_to_grid_rows(f.name, "NO2", ts, max_cells=20))
                total = sum(len(c) for c in chunks)
                assert total == 4
            finally:
                os.unlink(f.name)

    def test_fill_value_skipped(self):
        """Values >= FILL_VALUE_MAX for gas are skipped (not emitted as grid rows)."""
        with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as f:
            west, south, east, north = -118.0, 34.0, -117.0, 35.0
            transform = from_bounds(west, south, east, north, 2, 2)
            # One fill (1e20 > NO2 FILL_VALUE_MAX 1e18), three real
            data = np.array([[1e15, 1e20], [1e15, 1e15]], dtype=np.float64)
            with rasterio.open(
                f.name, "w", driver="GTiff", height=2, width=2, count=1,
                dtype=data.dtype, crs=CRS.from_epsg(4326), transform=transform,
            ) as dst:
                dst.write(data, 1)
            try:
                ts = datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
                chunks = list(geotiff_to_grid_rows(f.name, "NO2", ts, max_cells=10))
                total = sum(len(c) for c in chunks)
                assert total == 3
            finally:
                os.unlink(f.name)

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            list(geotiff_to_grid_rows("/nonexistent/path.tif", "NO2", datetime.now(timezone.utc)))
