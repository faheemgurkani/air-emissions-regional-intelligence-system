# AERIS - Air Emissions Regional Intelligence System

AERIS is a comprehensive web application that processes NASA TEMPO (Tropospheric Emissions: Monitoring of Pollution) satellite data to provide real-time air quality analysis and intelligence. The system combines satellite data processing, weather integration, and interactive visualization to deliver actionable air quality insights for environmental monitoring and public health protection.

## Overview

Originally developed for monitoring the Madre Wildfire Region in New Cuyama, California, AERIS can be adapted to monitor any geographic area and time window. The system integrates NASA Harmony API, scientific data processing, and interactive web visualization to provide real-time regional air quality intelligence.

This project came to life as a result of our participation in the **NASA Space App Challenge (2025)**, where the team did their very best to deliver a viable prototype, of our attempt at the challenge we selected.

### Team Members:
- [Muhammad Faheem](faheemgurkani@gmail.com)
- Muhammad Zeeshan

## Key Features

### Core Capabilities

- **Multi-Gas Analysis**: Support for NO₂, CH₂O, AI (Aerosol Index), PM, and O₃ pollutants
- **Hotspot Detection**: Automated identification and classification of pollution clusters using spatial clustering algorithms
- **Real-time Weather Integration**: Current weather conditions and pollutant movement prediction
- **Interactive Mapping**: Live hotspot visualization with Leaflet.js
- **Route Safety Analysis**: Air quality assessment for travel routes with pollution avoidance recommendations
- **AI-Powered Interpretations**: Concise, actionable insights using GROQ API

### Data Processing

- NetCDF data parsing and analysis using xarray
- Pollution threshold classification (Good, Moderate, Unhealthy, Very Unhealthy, Hazardous)
- Spatial clustering with SciPy for hotspot detection
- Geographic coordinate handling and reverse geocoding
- Automated report generation with AI interpretations

### Visualization

- Multi-gas concentration heatmaps
- Tripanel analysis figures per gas
- Interactive web maps with pollution overlays
- Real-time hotspot visualization
- Route safety analysis with pollution exposure scoring

## System Architecture

The AERIS system follows a modular architecture with clear separation of concerns:

| Layer                   | Components            | Description                                              |
| ----------------------- | --------------------- | -------------------------------------------------------- |
| **Web Server**          | FastAPI + Uvicorn     | Serves web dashboard and handles API requests            |
| **Frontend**            | Jinja2 templates, CSS | Displays results and user interface                      |
| **Computation**         | NumPy, SciPy, Xarray  | Handles NASA TEMPO data parsing and analysis             |
| **Visualization**       | Matplotlib, Cartopy   | Generates pollution heatmaps and geospatial overlays     |
| **AI Services**         | GROQ API              | Provides intelligent interpretations and recommendations |
| **Weather Integration** | WeatherAPI.com        | Real-time weather data and forecasts                     |
| **Storage**             | NetCDF files          | Cached TEMPO data for offline use                        |

## Project Structure

```
AERIS/
├── api_server.py              # Main FastAPI application
├── weather_service.py         # Weather data integration
├── groq_service.py           # AI interpretation service
├── pollutant_predictor.py    # Pollutant movement prediction
├── TEMPO.py                  # NASA TEMPO data processing
├── tempo_all.py              # Enhanced multi-gas analyzer
├── GroundSensorAnalysis.py   # Ground sensor integration
├── templates/                # Web interface templates
│   ├── index.html           # Main input interface
│   ├── result.html          # Analysis results display
│   └── route.html           # Route safety analysis
├── static/                  # Static assets
│   ├── style.css           # Web styling
│   └── outputs/            # Generated analysis images
├── TempData/               # Cached TEMPO data files
├── GroundData/             # Ground sensor data
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## Installation

### Prerequisites

- Python 3.8 or higher
- NASA Earthdata account (for TEMPO data access)
- WeatherAPI.com API key (optional, for weather features)
- GROQ API key (optional, for AI interpretations)

### Setup

1. **Clone the repository**

   ```bash
   git clone https://github.com/Xeeshan85/air-emissions-regional-intelligence-system.git
   cd air-emissions-regional-intelligence-system
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**

   Create a `.env` file with your API keys:

   ```bash
   WEATHER_API_KEY=your_weather_api_key
   GROQ_API_KEY=your_groq_api_key
   ```

4. **Prepare data directories**
   ```bash
   mkdir -p TempData GroundData static/outputs
   ```

## Usage

### Starting the Application

1. **Start the FastAPI server**

   ```bash
   uvicorn api_server:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Access the application**

   Open your browser and navigate to `http://localhost:8000`

### Web Interface

#### Main Analysis (`/`)

- Enter location coordinates or place names to analyze air quality
- Select gases to analyze (NO₂, CH₂O, AI, PM, O₃)
- Configure analysis radius and parameters
- Enable weather integration and pollutant movement prediction

#### Route Analysis (`/route`)

- Assess air quality along travel routes
- Get pollution exposure scores for different route options
- View interactive maps with pollution hotspots
- Receive safety recommendations for travel

### API Endpoints

The system provides RESTful API endpoints for programmatic access:

- `GET /api/weather` - Current weather data
- `GET /api/pollutant_movement` - Pollutant dispersion prediction
- `GET /api/combined_analysis` - Integrated satellite and weather analysis
- `GET /api/hotspots` - Pollution hotspot data in GeoJSON format
- `POST /api/analyze` - Custom air quality analysis

## Configuration

### Analysis Parameters

- **Radius**: Analysis area radius in degrees (default: 0.3°)
- **Gases**: Comma-separated list of pollutants to analyze
- **Weather Integration**: Enable/disable real-time weather data
- **Prediction**: Enable/disable pollutant movement forecasting

### Pollution Thresholds

Thresholds are defined in `api_server.py` and can be customized for different pollutants:

- **NO₂**: 5.0e15 - 3.0e16 molecules/cm²
- **CH₂O**: 8.0e15 - 6.4e16 molecules/cm²
- **AI**: 1.0 - 7.0 index
- **PM**: 0.2 - 2.0 dimensionless
- **O₃**: 220 - 500 Dobson Units

## Data Sources

- **NASA TEMPO**: Tropospheric pollution measurements
- **WeatherAPI.com**: Real-time weather conditions
- **OpenStreetMap**: Base mapping data
- **OSRM**: Route optimization services
- **EPA AirNow**: Ground sensor data (via GroundSensorAnalysis.py)

## Dependencies

Key packages include:

- **FastAPI and Uvicorn**: Web framework
- **xarray and netCDF4**: Satellite data processing
- **matplotlib and cartopy**: Visualization
- **scipy and numpy**: Scientific computing
- **geopy**: Geocoding services
- **requests**: HTTP client for API calls

See `requirements.txt` for complete dependency list.

## How It Works

1. **User Request**: User accesses AERIS dashboard via web interface
2. **Data Retrieval**: App authenticates with NASA Earthdata (Harmony API) and retrieves or loads existing TEMPO datasets
3. **Data Processing**: Converts NetCDF data to xarray Dataset, normalizes values, and detects spatial clusters
4. **Alert Generation**: Computes mean and max values per region, assigns severity classification, and generates health advisory text
5. **Visualization**: Renders geospatial maps using Cartopy, annotates hotspots and region boundaries, displays results interactively
6. **AI Interpretation**: Generates concise, actionable insights using GROQ API for weather and prediction data

## Example Output

```
Dataset: NASA TEMPO (NO₂ Level-3)
Date Range: 2025-09-15 → 2025-09-20
Region: Madre Wildfire, New Cuyama, CA

ALERT: BAKERSFIELD - HAZARDOUS
Location: 35.3733°N, 119.0187°W
NO₂: 3.02e+16 molecules/cm²
ACTION: STAY INDOORS! Dangerous air quality detected.
```

## Customization

| Parameter        | Location        | Description                               |
| ---------------- | --------------- | ----------------------------------------- |
| `SPATIAL_BOUNDS` | `TEMPO.py`      | Defines lat/lon range for analysis        |
| `TIME_CONFIG`    | `TEMPO.py`      | Start & end date for TEMPO data retrieval |
| `thresholds`     | `api_server.py` | Adjusts severity levels for pollutants    |
| `TEMPLATES`      | `templates/`    | Modify HTML layout for web UI             |

## Future Enhancements

- Integration with real-time wildfire APIs (NASA FIRMS)
- Enhanced multi-pollutant support
- Database logging (PostgreSQL + GeoJSON export)
- Advanced machine learning models for prediction
- Mobile application support
- Real-time alert notifications

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature-name`)
3. Add changes and tests
4. Submit a pull request

Follow PEP8 style guidelines and ensure your code is documented.

## License

MIT License

Developed as part of a research initiative to enhance environmental intelligence and wildfire response using open NASA data.

## Acknowledgments

- **NASA TEMPO** — Tropospheric Emissions: Monitoring of Pollution
- **NASA Harmony API** — Data Access and Retrieval
- **Cartopy & Xarray** — Geospatial and scientific computing libraries
- **FastAPI** — High-performance web framework
- **WeatherAPI.com** — Weather data services
- **Open source geospatial community** — Mapping and visualization tools

---

_"Turning satellite data into environmental intelligence — one map at a time."_
