import math
from typing import Dict, Any, List


def predict_pollutant_movement(hourly_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Predict pollutant movement for the next 3 hours using a simplified model.

    Args:
        hourly_data: List of hourly weather + air quality data from WeatherAPI.com
    
    Returns:
        List of predictions for next 3 hours with estimated pollutant displacement and concentrations.
    """
    predictions = []

    for i in range(1, 4):  # next 3 hours
        if i >= len(hourly_data):
            break

        hour = hourly_data[i]
        airq = hour.get("air_quality", {})
        wind_speed = hour.get("wind_kph", 0)
        wind_dir_deg = hour.get("wind_degree", 0)

        # Compute displacement (km) based on wind vector
        # Assuming pollutant particles roughly move with wind
        dx = wind_speed * math.sin(math.radians(wind_dir_deg)) * 1  # per hour
        dy = wind_speed * math.cos(math.radians(wind_dir_deg)) * 1

        # Adjust concentration (simplified): dispersion with time & humidity
        humidity = hour.get("humidity", 50)
        dispersion_factor = 1 + (humidity / 100) * 0.2  # higher humidity → faster dispersion

        predicted_air_quality = {}
        for pollutant, value in airq.items():
            if isinstance(value, (int, float)):
                predicted_air_quality[pollutant] = value / dispersion_factor

        predictions.append({
            "time": hour["time"],
            "wind_kph": wind_speed,
            "wind_dir_deg": wind_dir_deg,
            "displacement_km": {"dx": round(dx, 2), "dy": round(dy, 2)},
            "predicted_air_quality": predicted_air_quality
        })

    return predictions
