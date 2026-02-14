#!/usr/bin/env python3
"""
Thoroughly analyze fetched TEMPO/Harmony data to ensure it is the required,
accurate, and real product: raster metadata, value plausibility, and grid row schema/consistency.

Usage (from project root):
  python scripts/analyze_fetched_data.py --geotiff /path/to/file.tif --gas NO2
  python scripts/analyze_fetched_data.py --live --gas NO2
  python scripts/analyze_fetched_data.py --live --gas NO2 --find-granules   # use CMR to find valid time/bbox

Expects .env with BEARER_TOKEN or EARTHDATA_* for --live.
"""
import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Plausible value ranges per gas (TEMPO/science; used to flag suspicious data)
# NO2/CH2O: column in molecules/cm²; AI: aerosol index; PM: optical; O3: DU
PLAUSIBLE_RANGES = {
    "NO2": (0.0, 1e18),
    "CH2O": (0.0, 1e18),
    "AI": (0.0, 10.0),
    "PM": (0.0, 10.0),
    "O3": (0.0, 1000.0),
}
# Values above this (per gas) are likely fill/no-data; TEMPO often uses ~9.97e36
FILL_VALUE_THRESHOLD = {
    "NO2": 1e18,
    "CH2O": 1e18,
    "AI": 1e10,
    "PM": 1e10,
    "O3": 1e10,
}

REQUIRED_ROW_KEYS = {"timestamp", "gas_type", "geom_wkt", "pollution_value", "severity_level"}


def analyze_raster(geotiff_path: str, gas: str) -> dict:
    """Analyze GeoTIFF: metadata, band stats, plausibility. Returns report dict and list of errors."""
    import numpy as np
    import rasterio
    from rasterio.crs import CRS

    report = {"path": str(geotiff_path), "gas": gas, "errors": [], "warnings": []}
    path = Path(geotiff_path)
    if not path.exists():
        report["errors"].append(f"File not found: {geotiff_path}")
        return report

    with rasterio.open(path) as src:
        report["width"] = src.width
        report["height"] = src.height
        report["count"] = src.count
        report["dtype"] = str(src.dtypes[0])
        report["crs"] = str(src.crs) if src.crs else "None"
        report["bounds"] = list(src.bounds)
        band = src.read(1)
        transform = src.transform

    arr = band.astype(float)
    nan_mask = np.isnan(arr)
    valid = arr[~nan_mask]
    report["valid_pixel_count"] = int(np.sum(~nan_mask))
    report["nan_pixel_count"] = int(np.sum(nan_mask))
    report["total_pixels"] = arr.size

    if valid.size == 0:
        report["errors"].append("No non-NaN pixels in band 1")
        report["min"] = report["max"] = report["mean"] = None
        return report

    report["min"] = float(np.nanmin(valid))
    report["max"] = float(np.nanmax(valid))
    report["mean"] = float(np.nanmean(valid))

    low, high = PLAUSIBLE_RANGES.get(gas, (0.0, 1e20))
    if report["min"] < low or report["max"] > high:
        report["warnings"].append(
            f"Values [{report['min']:.4g}, {report['max']:.4g}] outside plausible range [{low:.4g}, {high:.4g}] for {gas}"
        )
    fill_thresh = FILL_VALUE_THRESHOLD.get(gas, 1e30)
    if report["max"] > fill_thresh:
        report["warnings"].append(
            f"Max value {report['max']:.4g} exceeds fill threshold {fill_thresh:.4g}; consider filtering as no-data in ingestion"
        )
    if report["valid_pixel_count"] < 10:
        report["warnings"].append("Very few valid pixels; product may be mostly fill/no-data")

    return report


def analyze_grid_rows(geotiff_path: str, gas: str, timestamp: datetime, max_cells: int = 2000) -> dict:
    """Run geotiff_to_grid_rows and validate every row: schema, WKT, severity, consistency with classify."""
    from pollution_utils import classify_pollution_level
    from services.raster_normalizer import geotiff_to_grid_rows

    report = {"row_count": 0, "errors": [], "warnings": [], "severity_counts": {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}}
    path = Path(geotiff_path)
    if not path.exists():
        report["errors"].append(f"File not found: {geotiff_path}")
        return report

    for chunk in geotiff_to_grid_rows(path, gas, timestamp, max_cells=max_cells):
        for row in chunk:
            report["row_count"] += 1
            if not REQUIRED_ROW_KEYS.issubset(row.keys()):
                report["errors"].append(f"Row missing keys: {REQUIRED_ROW_KEYS - row.keys()}")
            if not row.get("geom_wkt", "").startswith("POLYGON(("):
                report["errors"].append(f"Invalid geom_wkt: {str(row.get('geom_wkt', ''))[:80]}")
            sev = row.get("severity_level")
            if sev not in (0, 1, 2, 3, 4):
                report["errors"].append(f"severity_level {sev} not in 0-4")
            else:
                report["severity_counts"][sev] = report["severity_counts"].get(sev, 0) + 1
            # Consistency: classify_pollution_level(value, gas) should match row severity
            val = row.get("pollution_value")
            _, expected_sev = classify_pollution_level(float(val) if val is not None else float("nan"), gas)
            if expected_sev != sev:
                report["errors"].append(
                    f"Severity mismatch: value={val} -> expected severity {expected_sev}, got {sev}"
                )
            if report["row_count"] >= max_cells:
                break
        if report["row_count"] >= max_cells:
            break

    if report["row_count"] == 0:
        report["errors"].append("No grid rows produced (all NaN or empty)")
    return report


def find_valid_granule_window(collection_id: str, gas: str):
    # Returns (start_time, end_time) or None
    """Try CMR granule search for the last 7 days to find a window with granules; return (start, end) or None."""
    from services.harmony_service import search_cmr_granules

    # CONUS-style bbox; try recent then older windows (TEMPO may have processing delay)
    west, south, east, north = -125.0, 24.0, -66.0, 50.0
    base = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    # Try last 14 days, then 30–60 days ago
    for days_ago in list(range(0, 14)) + list(range(30, 61, 5)):
        end_time = base - timedelta(days=days_ago)
        start_time = end_time - timedelta(hours=1)
        granules = search_cmr_granules(collection_id, start_time, end_time, west, south, east, north, page_size=1)
        if granules:
            return (start_time, end_time)
    # Known-good window where CMR has TEMPO NO2 granules (e.g. 2024-06-01)
    fallback_end = datetime(2024, 6, 1, 1, 0, 0, tzinfo=timezone.utc)
    fallback_start = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    g = search_cmr_granules(collection_id, fallback_start, fallback_end, west, south, east, north, page_size=1)
    if g:
        return (fallback_start, fallback_end)
    return None


def main():
    parser = argparse.ArgumentParser(description="Analyze fetched TEMPO data for correctness and accuracy")
    parser.add_argument("--geotiff", help="Path to existing GeoTIFF (skip live fetch)")
    parser.add_argument("--live", action="store_true", help="Fetch live from Harmony (NO2 small bbox)")
    parser.add_argument("--find-granules", action="store_true", help="With --live: use CMR to find a time with granules")
    parser.add_argument("--gas", default="NO2", choices=["NO2", "CH2O", "AI", "PM", "O3"], help="Gas type")
    parser.add_argument("--max-cells", type=int, default=2000, help="Max grid rows to validate")
    args = parser.parse_args()

    geotiff_path = args.geotiff
    gas = args.gas

    if args.live:
        from services.harmony_service import (
            TEMPO_COLLECTION_IDS,
            fetch_tempo_geotiff,
            get_bearer_token,
        )

        if not get_bearer_token():
            print("FAIL: No bearer token; set BEARER_TOKEN or EARTHDATA_* in .env")
            return 1

        collection_id = TEMPO_COLLECTION_IDS.get(gas)
        if not collection_id:
            print(f"FAIL: No collection ID for gas {gas}")
            return 1

        start_time = None
        end_time = None
        if args.find_granules:
            window = find_valid_granule_window(collection_id, gas)
            if window:
                start_time, end_time = window
                print(f"CMR found granules for {start_time.isoformat()} to {end_time.isoformat()}")
            # If CMR fails or finds nothing, fall through to default window
        if start_time is None:
            end_time = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
            start_time = end_time - timedelta(hours=1)
            # Try 7 days ago if first attempt fails
            for attempt in range(2):
                geotiff_path = fetch_tempo_geotiff(
                    gas,
                    west=-118.5, south=33.5, east=-117.5, north=34.5,
                    start_time=start_time, end_time=end_time,
                )
                if geotiff_path:
                    break
                start_time = start_time - timedelta(days=7)
                end_time = end_time - timedelta(days=7)
        else:
            geotiff_path = fetch_tempo_geotiff(
                gas,
                west=-118.5, south=33.5, east=-117.5, north=34.5,
                start_time=start_time, end_time=end_time,
            )

        if not geotiff_path:
            print("FAIL: Live fetch returned no GeoTIFF (no matching granules or error).")
            return 1
        print(f"Fetched: {geotiff_path}")
        # Use start_time for grid row timestamp
        if start_time is None:
            start_time = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    else:
        if not geotiff_path:
            print("Provide --geotiff PATH or --live")
            return 1
        start_time = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

    print()
    print("=" * 60)
    print("AERIS Fetched Data Analysis")
    print("=" * 60)
    print(f"GeoTIFF: {geotiff_path}")
    print(f"Gas:     {gas}")
    print()

    # 1. Raster analysis
    raster_report = analyze_raster(geotiff_path, gas)
    print("--- Raster (GeoTIFF) ---")
    if raster_report["errors"]:
        for e in raster_report["errors"]:
            print(f"  ERROR: {e}")
    if raster_report["warnings"]:
        for w in raster_report["warnings"]:
            print(f"  WARN:  {w}")
    print(f"  size:     {raster_report.get('width')} x {raster_report.get('height')} x {raster_report.get('count')}")
    print(f"  dtype:    {raster_report.get('dtype')}")
    print(f"  CRS:      {raster_report.get('crs')}")
    print(f"  bounds:   {raster_report.get('bounds')}")
    print(f"  valid:    {raster_report.get('valid_pixel_count')}  NaN: {raster_report.get('nan_pixel_count')}")
    if raster_report.get("min") is not None:
        print(f"  min/max/mean: {raster_report['min']:.6g} / {raster_report['max']:.6g} / {raster_report['mean']:.6g}")
    print()

    # 2. Grid row analysis
    row_report = analyze_grid_rows(geotiff_path, gas, start_time, max_cells=args.max_cells)
    print("--- Grid rows (required schema + severity consistency) ---")
    if row_report["errors"]:
        for e in row_report["errors"][:15]:
            print(f"  ERROR: {e}")
        if len(row_report["errors"]) > 15:
            print(f"  ... and {len(row_report['errors']) - 15} more errors")
    print(f"  row_count: {row_report['row_count']}")
    print(f"  severity_dist: {row_report.get('severity_counts', {})}")
    print()

    # 3. Summary
    all_errors = raster_report["errors"] + row_report["errors"]
    if all_errors:
        print("RESULT: FAIL — fix errors above.")
        if args.live and geotiff_path and os.path.exists(geotiff_path):
            try:
                os.unlink(geotiff_path)
            except Exception:
                pass
        return 1
    print("RESULT: PASS — data is in required format, values plausible, severity consistent.")
    if args.live and geotiff_path and os.path.exists(geotiff_path):
        try:
            os.unlink(geotiff_path)
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
