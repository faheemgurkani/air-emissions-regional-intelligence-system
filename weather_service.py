import os
import requests
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")

if not WEATHER_API_KEY:
    print("⚠️ Warning: Missing WeatherAPI.com API Key. Weather features will be disabled.")
    print("Please set WEATHER_API_KEY in your .env file to enable weather functionality.")

BASE_URL = "http://api.weatherapi.com/v1"
CURRENT_ENDPOINT = f"{BASE_URL}/current.json"
FORECAST_ENDPOINT = f"{BASE_URL}/forecast.json"


def get_weather_data(lat: float, lon: float, days: int = 1) -> Dict[str, Any]:
    """
    Fetch current weather + forecast (for `days` ahead) via WeatherAPI.com.
    Optionally includes air quality if available.
    """
    if not WEATHER_API_KEY:
        return {"error": "Weather API key not configured"}
    
    location_query = f"{lat},{lon}"
    common_params = {
        "key": WEATHER_API_KEY,
        "q": location_query,
        "aqi": "yes",    # request air quality data
    }

    try:
        # Current weather
        resp_current = requests.get(CURRENT_ENDPOINT, params=common_params, timeout=10)
        if resp_current.status_code != 200:
            return {"error": f"Weather API error: {resp_current.status_code}"}
        current_data = resp_current.json()

        # Forecast weather
        forecast_params = common_params.copy()
        forecast_params["days"] = days  # number of forecast days
        resp_forecast = requests.get(FORECAST_ENDPOINT, params=forecast_params, timeout=10)
        if resp_forecast.status_code != 200:
            return {"error": f"Weather API error: {resp_forecast.status_code}"}
        forecast_data = resp_forecast.json()

        # Build a simplified result
        result = {
            "location": current_data.get("location"),
            "current": {
                "temp_c": current_data["current"]["temp_c"],
                "humidity": current_data["current"]["humidity"],
                "wind_kph": current_data["current"]["wind_kph"],
                "wind_degree": current_data["current"]["wind_degree"],
                "condition": current_data["current"]["condition"]["text"],
            },
            "air_quality": current_data["current"].get("air_quality"),  # may be None if plan doesn't support
            "forecast": {
                "forecastday": forecast_data.get("forecast", {}).get("forecastday")
            }
        }

        return result
    except requests.exceptions.RequestException as e:
        return {"error": f"Network error: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


def get_pollutant_movement_prediction(lat: float, lon: float) -> Dict[str, Any]:
    """
    Predict the movement and concentration changes of pollutants for next 3 hours.
    """
    weather_data = get_weather_data(lat=lat, lon=lon, days=1)
    
    if "error" in weather_data:
        return weather_data
    
    if not weather_data.get("forecast", {}).get("forecastday"):
        return {"error": "No forecast data available"}
    
    forecast_hours = weather_data["forecast"]["forecastday"][0]["hour"]
    
    from pollutant_predictor import predict_pollutant_movement
    prediction = predict_pollutant_movement(forecast_hours)

    return {
        "location": weather_data["location"],
        "predictions_next_3h": prediction
    }
