"""
Shared pollution thresholds and classification for api_server and ingestion (raster normalizer, Celery).
"""
from typing import Dict, Tuple

import numpy as np

POLLUTION_THRESHOLDS: Dict[str, Dict[str, float]] = {
    "NO2": {
        "moderate": 5.0e15,
        "unhealthy": 1.0e16,
        "very_unhealthy": 2.0e16,
        "hazardous": 3.0e16,
    },
    "CH2O": {
        "moderate": 8.0e15,
        "unhealthy": 1.6e16,
        "very_unhealthy": 3.2e16,
        "hazardous": 6.4e16,
    },
    "AI": {
        "moderate": 1.0,
        "unhealthy": 2.0,
        "very_unhealthy": 4.0,
        "hazardous": 7.0,
    },
    "PM": {
        "moderate": 0.2,
        "unhealthy": 0.5,
        "very_unhealthy": 1.0,
        "hazardous": 2.0,
    },
    "O3": {
        "moderate": 220,
        "unhealthy": 280,
        "very_unhealthy": 400,
        "hazardous": 500,
    },
}


def classify_pollution_level(value: float, gas: str) -> Tuple[str, int]:
    if np.isnan(value) or gas not in POLLUTION_THRESHOLDS:
        return "no_data", 0
    thresholds = POLLUTION_THRESHOLDS[gas]
    if value >= thresholds["hazardous"]:
        return "hazardous", 4
    elif value >= thresholds["very_unhealthy"]:
        return "very_unhealthy", 3
    elif value >= thresholds["unhealthy"]:
        return "unhealthy", 2
    elif value >= thresholds["moderate"]:
        return "moderate", 1
    else:
        return "good", 0
