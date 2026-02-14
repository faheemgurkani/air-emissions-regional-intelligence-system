"""
Aggregate pollution_grid (PostGIS) by bbox and time window into a regular grid per gas.
"""
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Tuple

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass
class GridSpec:
    west: float
    south: float
    east: float
    north: float
    resolution_deg: float
    nx: int
    ny: int

    @classmethod
    def from_bbox(
        cls,
        west: float,
        south: float,
        east: float,
        north: float,
        resolution_deg: float,
    ) -> "GridSpec":
        nx = max(1, int((east - west) / resolution_deg))
        ny = max(1, int((north - south) / resolution_deg))
        return cls(
            west=west,
            south=south,
            east=east,
            north=north,
            resolution_deg=resolution_deg,
            nx=nx,
            ny=ny,
        )

    def cell_index(self, lon: float, lat: float) -> Tuple[int, int]:
        """Return (row, col) for a point; row=0 at south, col=0 at west."""
        j = int((lon - self.west) / self.resolution_deg)
        i = int((lat - self.south) / self.resolution_deg)
        j = max(0, min(j, self.nx - 1))
        i = max(0, min(i, self.ny - 1))
        return i, j

    def to_affine(self) -> Tuple[float, float, float, float, float, float]:
        """Rasterio-style affine: (c, a, b, f, d, e) for pixel (col, row) -> (x, y)."""
        # x = west + col * res, y = north - row * res (y flip for raster)
        a = self.resolution_deg
        b = 0.0
        c = self.west
        d = 0.0
        e = -self.resolution_deg
        f = self.north
        return (c, a, b, f, d, e)


def aggregate_pollution_grid_to_regular(
    session: Session,
    ts_start: datetime,
    ts_end: datetime,
    west: float,
    south: float,
    east: float,
    north: float,
    resolution_deg: float,
) -> Tuple[GridSpec, Dict[str, np.ndarray]]:
    """
    Query pollution_grid for rows in [ts_start, ts_end] and bbox; aggregate by gas
    into a regular grid (average pollution_value per cell). Returns (GridSpec, {gas: array}).
    Arrays are (ny, nx); NaN where no data.
    """
    spec = GridSpec.from_bbox(west, south, east, north, resolution_deg)
    # Fetch (gas_type, lon, lat, pollution_value) using centroid of geom
    rows = session.execute(
        text("""
            SELECT gas_type,
                   ST_X(ST_Centroid(geom)) AS lon,
                   ST_Y(ST_Centroid(geom)) AS lat,
                   pollution_value
            FROM pollution_grid
            WHERE timestamp >= :ts_start AND timestamp <= :ts_end
              AND geom && ST_MakeEnvelope(:west, :south, :east, :north, 4326)
        """),
        {
            "ts_start": ts_start,
            "ts_end": ts_end,
            "west": west,
            "south": south,
            "east": east,
            "north": north,
        },
    ).fetchall()

    # (gas -> (sum, count) per (i, j))
    accum: Dict[str, Dict[Tuple[int, int], Tuple[float, int]]] = defaultdict(
        lambda: defaultdict(lambda: (0.0, 0))
    )
    for row in rows:
        gas = row[0]
        lon, lat, val = float(row[1]), float(row[2]), float(row[3])
        i, j = spec.cell_index(lon, lat)
        s, c = accum[gas][(i, j)]
        accum[gas][(i, j)] = (s + val, c + 1)

    out: Dict[str, np.ndarray] = {}
    for gas, cells in accum.items():
        arr = np.full((spec.ny, spec.nx), np.nan, dtype=float)
        for (i, j), (s, c) in cells.items():
            if c > 0:
                arr[i, j] = s / c
        out[gas] = arr
    return spec, out
