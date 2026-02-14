"""
Alert detection: route deterioration, hazard, wind shift, time-based.
"""
import math
from typing import Any, Dict, List, Optional

from config import settings
from services.alerts.constants import get_sensitivity_scale


def check_route_deterioration(
    prev_score: float,
    curr_score: float,
    user_sensitivity_level: Optional[int],
    base_pct: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """
    Trigger when (curr - prev) / prev >= effective_threshold_pct.
    effective_threshold = base_pct * get_sensitivity_scale(level).
    Returns alert dict if triggered, else None.
    """
    if prev_score is None or prev_score <= 0:
        return None
    base = base_pct if base_pct is not None else getattr(settings, "alerts_deterioration_base_pct", 0.15)
    scale = get_sensitivity_scale(user_sensitivity_level)
    effective_pct = base * scale
    delta_pct = (curr_score - prev_score) / prev_score
    if delta_pct >= effective_pct:
        return {
            "type": "route_deterioration",
            "score_before": prev_score,
            "score_after": curr_score,
            "threshold": effective_pct,
            "metadata": {"delta_pct": round(delta_pct, 4)},
        }
    return None


def check_hazard_alert(
    max_upes_along_route: float,
    critical_threshold: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """
    Trigger when max UPES along route >= critical_threshold.
    """
    thresh = critical_threshold if critical_threshold is not None else getattr(settings, "alerts_hazard_threshold", 0.85)
    if max_upes_along_route >= thresh:
        return {
            "type": "hazard",
            "score_before": None,
            "score_after": max_upes_along_route,
            "threshold": thresh,
            "metadata": {},
        }
    return None


def _angle_diff_deg(a1: float, a2: float) -> float:
    """Difference between two angles in [0, 360), in degrees, in [0, 180]."""
    d = abs(a1 - a2) % 360.0
    return min(d, 360.0 - d)


def _bearing_deg(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Bearing from point 1 to point 2 in degrees [0, 360)."""
    lat1, lat2, lon1, lon2 = map(math.radians, [lat1, lat2, lon1, lon2])
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    b = math.degrees(math.atan2(x, y))
    return (b + 360.0) % 360.0


def check_wind_shift_alert(
    wind_kph: float,
    wind_degree: float,
    route_mid_lat: float,
    route_mid_lon: float,
    source_lat: float,
    source_lon: float,
    min_speed_kph: Optional[float] = None,
    max_angle_deg: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """
    Wind is blowing from wind_degree (direction wind comes FROM).
    Vector from source (e.g. hotspot) to route midpoint: bearing source -> route.
    If wind is blowing toward the route, wind_degree should be roughly opposite to (source->route).
    Wind FROM source toward route: bearing from source to route = where wind would push pollution.
    So we want: bearing(source -> route) ≈ wind_degree (wind blows from that direction toward route).
    Actually: wind_degree is "where wind is coming from". So wind vector direction (where it's going) = (wind_degree + 180) % 360.
    Pollution moves WITH wind, so from source toward route we need (wind_degree + 180) roughly equal to bearing(source, route).
    So bearing(source, route) should be within max_angle_deg of (wind_degree + 180).
    If angle_diff(bearing(source->route), wind_degree + 180) < max_angle_deg and wind_kph >= min_speed -> trigger.
    """
    min_speed = min_speed_kph if min_speed_kph is not None else getattr(settings, "alerts_wind_speed_min_kph", 5.0)
    max_angle = max_angle_deg if max_angle_deg is not None else getattr(settings, "alerts_wind_angle_deg", 45.0)
    if wind_kph < min_speed:
        return None
    # Bearing from source to route (direction from hotspot toward route)
    bearing_to_route = _bearing_deg(source_lon, source_lat, route_mid_lon, route_mid_lat)
    # Wind direction "where wind is going" (meteorological convention: from = wind_degree)
    wind_toward = (wind_degree + 180.0) % 360.0
    diff = _angle_diff_deg(bearing_to_route, wind_toward)
    if diff <= max_angle:
        return {
            "type": "wind_shift",
            "score_before": None,
            "score_after": None,
            "threshold": None,
            "metadata": {
                "wind_kph": wind_kph,
                "wind_degree": wind_degree,
                "bearing_source_to_route": round(bearing_to_route, 2),
            },
        }
    return None


def check_time_based_alert(
    current_upes_score: float,
    recent_min_score: Optional[float],
    margin: float = 0.15,
) -> Optional[Dict[str, Any]]:
    """
    Minimal time-based: if we have a recent minimum and current is worse by margin, suggest.
    """
    if recent_min_score is None:
        return None
    if current_upes_score >= recent_min_score + margin:
        return {
            "type": "time_based",
            "score_before": recent_min_score,
            "score_after": current_upes_score,
            "threshold": margin,
            "metadata": {"best_recent_score": recent_min_score},
        }
    return None


def run_detection(
    user_id: int,
    route_id: int,
    current_upes: float,
    max_upes: float,
    prev_upes: Optional[float],
    recent_min_upes: Optional[float],
    user_sensitivity_level: Optional[int],
    wind_kph: Optional[float] = None,
    wind_degree: Optional[float] = None,
    route_mid_lat: Optional[float] = None,
    route_mid_lon: Optional[float] = None,
    source_lat: Optional[float] = None,
    source_lon: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Run all checks and return list of alert dicts. Each dict includes type, score_before, score_after,
    threshold, metadata; caller adds user_id and route_id when persisting.
    """
    alerts: List[Dict[str, Any]] = []
    # Deterioration
    if prev_upes is not None:
        a = check_route_deterioration(prev_upes, current_upes, user_sensitivity_level)
        if a:
            a["user_id"] = user_id
            a["route_id"] = route_id
            alerts.append(a)
    # Hazard
    a = check_hazard_alert(max_upes)
    if a:
        a["user_id"] = user_id
        a["route_id"] = route_id
        alerts.append(a)
    # Wind shift (only if we have wind and route/source coords)
    if (
        wind_kph is not None
        and wind_degree is not None
        and route_mid_lat is not None
        and route_mid_lon is not None
        and source_lat is not None
        and source_lon is not None
    ):
        a = check_wind_shift_alert(
            wind_kph, wind_degree, route_mid_lat, route_mid_lon, source_lat, source_lon
        )
        if a:
            a["user_id"] = user_id
            a["route_id"] = route_id
            alerts.append(a)
    # Time-based
    a = check_time_based_alert(current_upes, recent_min_upes)
    if a:
        a["user_id"] = user_id
        a["route_id"] = route_id
        alerts.append(a)
    return alerts
