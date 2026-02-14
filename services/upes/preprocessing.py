"""
UPES preprocessing: gas normalization (0-1) and temporal alignment to hourly.
"""
from datetime import datetime, timezone
from typing import Optional, Tuple, Union

import numpy as np


def hour_slot_utc(ts: datetime) -> datetime:
    """Truncate timestamp to hour in UTC for temporal alignment (hourly resolution)."""
    if hasattr(ts, "utcoffset") and ts.utcoffset() is not None:
        ts = ts.astimezone(timezone.utc)
    return ts.replace(minute=0, second=0, microsecond=0)


def normalize_gas(
    gas_array: Union[float, np.ndarray],
    min_val: float,
    max_val: float,
) -> Union[float, np.ndarray]:
    """
    Normalize gas values to [0, 1]: (value - min_val) / (max_val - min_val), then clip.
    NaN-safe: NaNs remain NaN.
    """
    if max_val <= min_val:
        return np.zeros_like(gas_array) if isinstance(gas_array, np.ndarray) else 0.0
    arr = np.asarray(gas_array, dtype=float)
    norm = (arr - min_val) / (max_val - min_val)
    norm = np.clip(norm, 0.0, 1.0)
    if np.isscalar(gas_array):
        return float(norm.flat[0]) if norm.size else 0.0
    return norm


def percentile_bounds(
    arr: np.ndarray,
    low_percentile: float = 5.0,
    high_percentile: float = 95.0,
) -> Tuple[float, float]:
    """
    Compute min/max from percentiles of a array (ignoring NaN).
    Returns (min_g, max_g) for use in normalize_gas.
    """
    flat = np.nan_to_num(arr.ravel(), nan=np.nan)
    valid = flat[~np.isnan(flat)]
    if valid.size == 0:
        return 0.0, 1.0
    min_g = float(np.nanpercentile(valid, low_percentile))
    max_g = float(np.nanpercentile(valid, high_percentile))
    if max_g <= min_g:
        max_g = min_g + 1.0
    return min_g, max_g


def normalize_gas_with_bounds(
    gas_array: np.ndarray,
    min_val: Optional[float] = None,
    max_val: Optional[float] = None,
    use_percentiles: bool = True,
    low_p: float = 5.0,
    high_p: float = 95.0,
) -> np.ndarray:
    """
    Normalize gas array to [0,1]. If min_val/max_val are None and use_percentiles,
    use percentile_bounds; otherwise require min_val and max_val.
    """
    if min_val is None or max_val is None:
        if use_percentiles:
            min_val, max_val = percentile_bounds(gas_array, low_p, high_p)
        else:
            min_val = float(np.nanmin(gas_array))
            max_val = float(np.nanmax(gas_array))
            if max_val <= min_val:
                max_val = min_val + 1.0
    return normalize_gas(gas_array, min_val, max_val)
