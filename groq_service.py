"""
GROQ API service for generating intelligent interpretations of weather and air quality data.
Focuses on air quality and commute optimization recommendations.
"""

import os
import requests
import re
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    print("⚠️ Warning: Missing GROQ API Key. AI interpretations will be disabled.")
    print("Please set GROQ_API_KEY in your .env file to enable AI-powered insights.")

GROQ_BASE_URL = "https://api.groq.com/openai/v1/chat/completions"

def clean_markdown_formatting(text: str) -> str:
    """
    Clean up any markdown formatting that might slip through.
    Convert markdown to plain text for better HTML rendering.
    """
    if not text:
        return text
    
    # Remove markdown bold formatting
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    
    # Remove markdown italic formatting
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    
    # Remove markdown headers
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
    
    # Remove markdown list formatting
    text = re.sub(r'^\s*[-*+]\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s*', '', text, flags=re.MULTILINE)
    
    # Clean up extra whitespace
    text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
    
    return text.strip()

def generate_weather_interpretation(weather_data: Dict[str, Any], location_name: str) -> Optional[str]:
    """
    Generate intelligent interpretation of weather data focused on air quality and commute optimization.
    """
    if not GROQ_API_KEY:
        return None
    
    try:
        # Extract key weather information safely
        current = weather_data.get('current', {})
        air_quality = weather_data.get('air_quality', {})
        
        # Safely extract condition text
        condition_text = 'N/A'
        if isinstance(current.get('condition'), dict):
            condition_text = current.get('condition', {}).get('text', 'N/A')
        elif isinstance(current.get('condition'), str):
            condition_text = current.get('condition', 'N/A')
        
        # Prepare context for GROQ
        weather_context = f"""
        Location: {location_name}
        Temperature: {current.get('temp_c', 'N/A')}°C
        Humidity: {current.get('humidity', 'N/A')}%
        Wind Speed: {current.get('wind_kph', 'N/A')} km/h
        Wind Direction: {current.get('wind_dir', 'N/A')}
        Condition: {condition_text}
        Visibility: {current.get('vis_km', 'N/A')} km
        """
        
        if air_quality and isinstance(air_quality, dict):
            weather_context += f"""
        Air Quality:
        - CO: {air_quality.get('co', 'N/A')} μg/m³
        - NO2: {air_quality.get('no2', 'N/A')} μg/m³
        - O3: {air_quality.get('o3', 'N/A')} μg/m³
        - PM2.5: {air_quality.get('pm2_5', 'N/A')} μg/m³
        - PM10: {air_quality.get('pm10', 'N/A')} μg/m³
        - US EPA Index: {air_quality.get('us-epa-index', 'N/A')}/5
        """
        
        prompt = f"""
        Air Quality & Commute advice for {location_name}:

        {weather_context}

        Answer in 2-3 sentences max:
        1. Air Quality: [Status]
        2. Best time: [Time or N/A]
        3. Key precaution: [1 sentence]

        Be extremely concise. No explanations.
        """
        
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "llama-3.1-8b-instant",
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert Air Quality & Commute Optimizer. Provide concise, actionable advice for healthier commuting. Keep responses brief and focused."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 100,
            "temperature": 0.7
        }
        
        response = requests.post(GROQ_BASE_URL, headers=headers, json=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content'].strip()
            return clean_markdown_formatting(content)
        else:
            print(f"GROQ API error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"Error generating weather interpretation: {e}")
        return None

def generate_prediction_interpretation(pollutant_predictions: list, location_name: str) -> Optional[str]:
    """
    Generate intelligent interpretation of pollutant movement predictions focused on commute optimization.
    """
    if not GROQ_API_KEY or not pollutant_predictions:
        return None
    
    try:
        # Prepare prediction context
        prediction_context = f"""
        Location: {location_name}
        Pollutant Movement Predictions (Next 3 Hours):
        """
        
        for i, pred in enumerate(pollutant_predictions[:3]):  # Limit to first 3 predictions
            prediction_context += f"""
        Hour {i+1} ({pred.get('time', 'N/A')}):
        - Wind: {pred.get('wind_kph', 'N/A')} km/h from {pred.get('wind_dir_deg', 'N/A')}°
        - Movement: {pred.get('displacement_km', {}).get('dx', 'N/A')} km E/W, {pred.get('displacement_km', {}).get('dy', 'N/A')} km N/S
        - Predicted Air Quality: {', '.join([f"{k}: {v:.1f}" for k, v in pred.get('predicted_air_quality', {}).items()])}
        """
        
        prompt = f"""
        Air Quality predictions for {location_name}:

        {prediction_context}

        Answer in 2-3 sentences max:
        1. Trend: [Improving/Stable/Worsening]
        2. Best time: [Time or N/A]
        3. Risk: [1 sentence]

        Be extremely concise. No explanations.
        """
        
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "llama-3.1-8b-instant",
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert Air Quality & Commute Optimizer. Analyze pollutant movement predictions to provide concise advice for healthier commuting. Keep responses brief and focused."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 100,
            "temperature": 0.7
        }
        
        response = requests.post(GROQ_BASE_URL, headers=headers, json=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content'].strip()
            return clean_markdown_formatting(content)
        else:
            print(f"GROQ API error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"Error generating prediction interpretation: {e}")
        return None
