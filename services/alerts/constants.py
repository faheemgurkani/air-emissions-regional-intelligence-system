"""
Sensitivity mapping for alert thresholds: exposure_sensitivity_level (1-5) -> scale and label.
"""
from typing import Optional

# 1,2 -> Normal (1.0), 3,4 -> Sensitive (0.7), 5 -> Asthmatic (0.5)
SENSITIVITY_SCALE: dict[int, float] = {
    1: 1.0,
    2: 1.0,
    3: 0.7,
    4: 0.7,
    5: 0.5,
}

SENSITIVITY_LABEL: dict[int, str] = {
    1: "Normal",
    2: "Normal",
    3: "Sensitive",
    4: "Sensitive",
    5: "Asthmatic",
}


def get_sensitivity_scale(level: Optional[int]) -> float:
    """Return scaling factor for threshold (lower = stricter). Default 1.0 if level is None or unknown."""
    if level is None:
        return 1.0
    return SENSITIVITY_SCALE.get(level, 1.0)


def get_sensitivity_label(level: Optional[int]) -> str:
    """Return human-readable label for sensitivity level. Default 'Normal' if unknown."""
    if level is None:
        return "Normal"
    return SENSITIVITY_LABEL.get(level, "Normal")
