"""
UPES core: satellite score, environmental modifiers (HDF, WTF, TF), EMA, final score.
"""
from typing import Dict, Optional

import numpy as np

from config import UPES_DEFAULT_WEIGHTS, settings


def compute_satellite_score(
    normalized_gases: Dict[str, np.ndarray],
    weights: Optional[Dict[str, float]] = None,
) -> np.ndarray:
    """
    SatelliteScore = sum(weights[g] * normalized(g)) over gases present.
    Missing gases are skipped. Output shape = shape of first array; cells with no data stay NaN.
    """
    weights = weights or getattr(settings, "upes_weights", None) or UPES_DEFAULT_WEIGHTS
    out: Optional[np.ndarray] = None
    for gas, arr in normalized_gases.items():
        w = weights.get(gas, 0.0)
        if w <= 0:
            continue
        if out is None:
            out = w * np.asarray(arr, dtype=float).copy()
        else:
            out = out + w * np.asarray(arr, dtype=float)
    if out is None:
        return np.array(0.0)
    return out


def humidity_dispersion_factor(humidity_pct: float) -> float:
    """HDF = 1 - humidity/100. High humidity -> lower factor (pollutants disperse less)."""
    return float(np.clip(1.0 - humidity_pct / 100.0, 0.0, 1.0))


def wind_factor(
    speed_kph: float,
    direction_deg: float,
    target_dir_deg: float,
    max_speed_kph: float = 50.0,
) -> float:
    """
    WTF: alignment of wind with target direction, scaled by speed.
    alignment = cos(direction - target); WTF = clip(speed_norm * alignment, 0, 1).
    """
    alignment = np.cos(np.radians(direction_deg - target_dir_deg))
    speed_norm = min(speed_kph / max_speed_kph, 1.0) if max_speed_kph > 0 else 0.0
    return float(np.clip(speed_norm * alignment, 0.0, 1.0))


def traffic_factor(traffic_density: float, alpha: Optional[float] = None) -> float:
    """TF = 1 + alpha * traffic_density. traffic_density in [0,1]. When no data, use 1.0."""
    if alpha is None:
        alpha = getattr(settings, "upes_traffic_alpha", 0.1)
    return 1.0 + alpha * float(np.clip(traffic_density, 0.0, 1.0))


def apply_ema(
    current_score: np.ndarray,
    previous_score: Optional[np.ndarray],
    lam: float,
) -> np.ndarray:
    """
    FinalScore_t = lam * Score_t + (1 - lam) * FinalScore_{t-1}.
    If previous_score is None or shape mismatch, return current_score.
    """
    if previous_score is None or previous_score.shape != current_score.shape:
        return np.asarray(current_score, dtype=float).copy()
    return lam * np.asarray(current_score, dtype=float) + (1.0 - lam) * np.asarray(previous_score, dtype=float)


def compute_final_score(
    satellite_score: np.ndarray,
    hdf: float,
    wtf: float,
    tf: float = 1.0,
    previous_final: Optional[np.ndarray] = None,
    ema_lambda: Optional[float] = None,
) -> np.ndarray:
    """
    FinalScore = SatelliteScore * HDF * WTF * TF, then optionally apply EMA.
    """
    if ema_lambda is None:
        ema_lambda = getattr(settings, "upes_ema_lambda", None)
    raw = satellite_score * hdf * wtf * tf
    raw = np.asarray(raw, dtype=float)
    if ema_lambda is not None and 0 < ema_lambda <= 1:
        return apply_ema(raw, previous_final, ema_lambda)
    return raw
