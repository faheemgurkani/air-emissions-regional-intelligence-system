"""
Multi-objective weights (alpha, beta, gamma) per mode and mode-specific edge modifiers.
"""
from typing import Any, Dict, Tuple

# (alpha=exposure, beta=distance, gamma=time); sum = 1.0
MODE_WEIGHTS: Dict[str, Tuple[float, float, float]] = {
    "commute": (0.2, 0.4, 0.4),
    "commuter": (0.2, 0.4, 0.4),
    "jogger": (0.7, 0.15, 0.15),
    "jog": (0.7, 0.15, 0.15),
    "cyclist": (0.4, 0.3, 0.3),
    "cycle": (0.4, 0.3, 0.3),
}


def get_weights(mode: str) -> Tuple[float, float, float]:
    """Return (alpha, beta, gamma) for mode. Default to commuter if unknown."""
    mode = (mode or "commute").lower().strip()
    return MODE_WEIGHTS.get(mode, MODE_WEIGHTS["commute"])


def mode_modifier(edge_data: Dict[str, Any], mode: str) -> float:
    """
    Return multiplier for edge cost based on OSM tags and mode.
    > 1 = penalty, < 1 = bonus, 1 = neutral.
    """
    mode = (mode or "commute").lower().strip()
    highway = (edge_data.get("highway") or "").lower()
    if isinstance(highway, list):
        highway = highway[0] if highway else ""
    leisure = (edge_data.get("leisure") or "").lower()
    cycleway = edge_data.get("cycleway") or edge_data.get("cycleway:left") or edge_data.get("cycleway:right")
    if cycleway:
        cycleway = str(cycleway).lower()
    score = 1.0

    if mode in ("jogger", "jog"):
        if highway in ("motorway", "trunk", "motorway_link", "trunk_link"):
            score *= 2.0
        if leisure == "park" or highway in ("path", "footway", "pedestrian"):
            score *= 0.5
    elif mode in ("cyclist", "cycle"):
        if cycleway:
            score *= 0.7
        if highway in ("motorway", "trunk", "motorway_link", "trunk_link"):
            score *= 1.5
    else:
        # commuter: slight penalty for footway-only (driving)
        if highway in ("footway", "path", "pedestrian") and not edge_data.get("access") == "yes":
            score *= 1.2
    return max(0.1, min(5.0, score))
