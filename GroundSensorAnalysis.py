import datetime as dt
import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from cartopy.mpl.gridliner import LONGITUDE_FORMATTER, LATITUDE_FORMATTER
from scipy.spatial.distance import cdist
from scipy import ndimage
import json
import os

# ============== AUTHENTICATION ==============
print("="*80)
print("GROUND SENSOR POLLUTION DETECTION & ALERT SYSTEM")
print("Madre Wildfire Region - New Cuyama, California")
print("="*80)
print("\nGround sensor data will be fetched from EPA AirNow API")
print("No authentication required for public AirNow data")

# ============== CONFIGURATION ==============
# Air Quality Index (AQI) thresholds - EPA standard
AQI_THRESHOLDS = {
    'PM2.5': {
        'good': 12.0,           # 0-12 μg/m³ (AQI 0-50)
        'moderate': 35.4,        # 12.1-35.4 μg/m³ (AQI 51-100)
        'unhealthy_sensitive': 55.4,  # 35.5-55.4 μg/m³ (AQI 101-150)
        'unhealthy': 150.4,      # 55.5-150.4 μg/m³ (AQI 151-200)
        'very_unhealthy': 250.4, # 150.5-250.4 μg/m³ (AQI 201-300)
        'hazardous': 500.4       # 250.5+ μg/m³ (AQI 301+)
    },
    'PM10': {
        'good': 54.0,           # 0-54 μg/m³ (AQI 0-50)
        'moderate': 154.0,      # 55-154 μg/m³ (AQI 51-100)
        'unhealthy_sensitive': 254.0,  # 155-254 μg/m³ (AQI 101-150)
        'unhealthy': 354.0,      # 255-354 μg/m³ (AQI 151-200)
        'very_unhealthy': 424.0, # 355-424 μg/m³ (AQI 201-300)
        'hazardous': 604.0      # 425+ μg/m³ (AQI 301+)
    },
    'O3': {
        'good': 54.0,           # 0-54 ppb (AQI 0-50)
        'moderate': 70.0,       # 55-70 ppb (AQI 51-100)
        'unhealthy_sensitive': 85.0,  # 71-85 ppb (AQI 101-150)
        'unhealthy': 105.0,     # 86-105 ppb (AQI 151-200)
        'very_unhealthy': 200.0, # 106-200 ppb (AQI 201-300)
        'hazardous': 300.0      # 201+ ppb (AQI 301+)
    }
}

# Regions to monitor in California (Madre wildfire area and nearby cities)
MONITORED_REGIONS = {
    'New Cuyama': {'lat': 34.9, 'lon': -119.7, 'radius': 0.3},
    'Santa Maria': {'lat': 34.9530, 'lon': -120.4357, 'radius': 0.3},
    'San Luis Obispo': {'lat': 35.2828, 'lon': -120.6596, 'radius': 0.3},
    'Bakersfield': {'lat': 35.3733, 'lon': -119.0187, 'radius': 0.3},
    'Santa Barbara': {'lat': 34.4208, 'lon': -119.6982, 'radius': 0.3},
    'Wildfire Center': {'lat': 35.0, 'lon': -119.7, 'radius': 0.2},  # Approximate fire location
}

# Spatial coverage for Madre wildfire area
SPATIAL_BOUNDS = {
    'lon_min': -121,
    'lon_max': -118,
    'lat_min': 33.5,
    'lat_max': 36.5
}

# Time period - Current day (you can modify this)
TIME_CONFIG = {
    'date': dt.datetime.now().strftime('%Y-%m-%d'),
    'hour': dt.datetime.now().hour
}

print(f"\n📅 Analysis Date: {TIME_CONFIG['date']}")
print(f"📍 Region: Madre wildfire area, New Cuyama, California")
print(f"   Longitude: {SPATIAL_BOUNDS['lon_min']}° to {SPATIAL_BOUNDS['lon_max']}°")
print(f"   Latitude: {SPATIAL_BOUNDS['lat_min']}° to {SPATIAL_BOUNDS['lat_max']}°")

# ============== DATA RETRIEVAL ==============
def fetch_airnow_data():
    """Fetch current air quality data from EPA AirNow API"""
    
    # AirNow API endpoint for current data
    base_url = "https://www.airnowapi.org/aq/observation/zipCode/current/"
    
    # Get data for California zip codes in the wildfire region
    california_zips = [
        '93454',  # New Cuyama
        '93458',  # Santa Maria
        '93401',  # San Luis Obispo
        '93301',  # Bakersfield
        '93101',  # Santa Barbara
        '93420',  # Buellton (nearby)
        '93436',  # Lompoc (nearby)
    ]
    
    all_data = []
    
    print("\n📡 Fetching AirNow data for California region...")
    
    for zip_code in california_zips:
        try:
            # AirNow API call (no API key needed for basic requests)
            url = f"{base_url}?format=application/json&zipCode={zip_code}&distance=25"
            
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            all_data.extend(data)
            
            print(f"   ✓ Retrieved data for ZIP {zip_code}: {len(data)} stations")
            
        except requests.exceptions.RequestException as e:
            print(f"   ⚠️  Failed to fetch data for ZIP {zip_code}: {e}")
            continue
    
    # Also try to get PurpleAir data (community sensors)
    purpleair_data = fetch_purpleair_data()
    all_data.extend(purpleair_data)
    
    print(f"\n✓ Total stations retrieved: {len(all_data)}")
    
    return all_data

def fetch_purpleair_data():
    """Fetch data from PurpleAir community sensors"""
    
    print("\n📡 Fetching PurpleAir community sensor data...")
    
    # PurpleAir API endpoint
    url = "https://api.purpleair.com/v1/sensors"
    
    # Parameters for California region
    params = {
        'fields': 'latitude,longitude,pm2.5_atm,pm2.5_cf_1,temperature,humidity,last_seen',
        'location_type': 0,  # Outdoor sensors only
        'max_age': 3600,     # Data within last hour
        'nwlng': SPATIAL_BOUNDS['lon_min'],
        'nwlat': SPATIAL_BOUNDS['lat_max'],
        'selng': SPATIAL_BOUNDS['lon_max'],
        'selat': SPATIAL_BOUNDS['lat_min']
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Convert PurpleAir format to AirNow-like format
        purpleair_formatted = []
        for sensor in data.get('data', []):
            if sensor[2] is not None:  # PM2.5 data exists
                formatted_sensor = {
                    'Latitude': sensor[0],
                    'Longitude': sensor[1],
                    'ParameterName': 'PM2.5',
                    'Concentration': sensor[2],
                    'UnitOfMeasure': 'UG/M3',
                    'DateObserved': dt.datetime.fromtimestamp(sensor[6]).strftime('%Y-%m-%d'),
                    'HourObserved': dt.datetime.fromtimestamp(sensor[6]).hour,
                    'Source': 'PurpleAir',
                    'SiteName': f'PurpleAir_{sensor[0]:.3f}_{sensor[1]:.3f}'
                }
                purpleair_formatted.append(formatted_sensor)
        
        print(f"   ✓ Retrieved {len(purpleair_formatted)} PurpleAir sensors")
        return purpleair_formatted
        
    except requests.exceptions.RequestException as e:
        print(f"   ⚠️  Failed to fetch PurpleAir data: {e}")
        return []

def process_sensor_data(raw_data):
    """Process and clean sensor data"""
    
    if not raw_data:
        return pd.DataFrame()
    
    # Convert to DataFrame
    df = pd.DataFrame(raw_data)
    
    # Filter for relevant parameters
    relevant_params = ['PM2.5', 'PM10', 'O3']
    df = df[df['ParameterName'].isin(relevant_params)]
    
    # Convert coordinates to numeric
    df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
    df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
    df['Concentration'] = pd.to_numeric(df['Concentration'], errors='coerce')
    
    # Filter by spatial bounds
    df = df[
        (df['Latitude'] >= SPATIAL_BOUNDS['lat_min']) &
        (df['Latitude'] <= SPATIAL_BOUNDS['lat_max']) &
        (df['Longitude'] >= SPATIAL_BOUNDS['lon_min']) &
        (df['Longitude'] <= SPATIAL_BOUNDS['lon_max'])
    ]
    
    # Remove invalid data
    df = df.dropna(subset=['Latitude', 'Longitude', 'Concentration'])
    df = df[df['Concentration'] >= 0]  # Remove negative concentrations
    
    print(f"\n📊 Processed sensor data:")
    print(f"   ✓ Total valid measurements: {len(df)}")
    print(f"   ✓ Parameters: {df['ParameterName'].unique()}")
    print(f"   ✓ Date range: {df['DateObserved'].min()} to {df['DateObserved'].max()}")
    
    return df

# ============== POLLUTION DETECTION ==============
def classify_aqi_level(value, parameter, thresholds):
    """Classify AQI level based on concentration value"""
    if pd.isna(value) or value < 0:
        return 'no_data', 0
    
    param_thresholds = thresholds.get(parameter, {})
    
    if value >= param_thresholds.get('hazardous', float('inf')):
        return 'hazardous', 5
    elif value >= param_thresholds.get('very_unhealthy', float('inf')):
        return 'very_unhealthy', 4
    elif value >= param_thresholds.get('unhealthy', float('inf')):
        return 'unhealthy', 3
    elif value >= param_thresholds.get('unhealthy_sensitive', float('inf')):
        return 'unhealthy_sensitive', 2
    elif value >= param_thresholds.get('moderate', float('inf')):
        return 'moderate', 1
    else:
        return 'good', 0

def detect_pollution_hotspots(df, min_sensors=2, max_distance=50):
    """
    Detect regions with high pollution concentrations using sensor clustering
    
    Parameters:
    - df: DataFrame with sensor data
    - min_sensors: minimum number of sensors in a cluster
    - max_distance: maximum distance (km) between sensors in a cluster
    
    Returns:
    - hotspots: list of dictionaries containing hotspot information
    """
    hotspots = []
    
    # Group by parameter
    for parameter in df['ParameterName'].unique():
        param_data = df[df['ParameterName'] == parameter].copy()
        
        if len(param_data) < min_sensors:
            continue
        
        # Get coordinates
        coords = param_data[['Latitude', 'Longitude']].values
        
        # Calculate distance matrix (in km, approximate)
        distances = cdist(coords, coords) * 111  # ~111 km per degree
        
        # Find clusters using simple clustering
        visited = set()
        clusters = []
        
        for i in range(len(coords)):
            if i in visited:
                continue
            
            cluster = [i]
            visited.add(i)
            
            # Find nearby sensors
            for j in range(len(coords)):
                if j not in visited and distances[i, j] <= max_distance:
                    cluster.append(j)
                    visited.add(j)
            
            if len(cluster) >= min_sensors:
                clusters.append(cluster)
        
        # Analyze each cluster
        thresholds = AQI_THRESHOLDS.get(parameter, {})
        
        for cluster in clusters:
            cluster_data = param_data.iloc[cluster]
            
            # Calculate cluster statistics
            max_value = cluster_data['Concentration'].max()
            mean_value = cluster_data['Concentration'].mean()
            
            level, severity = classify_aqi_level(max_value, parameter, AQI_THRESHOLDS)
            
            if severity >= 2:  # Only report moderate+ hotspots
                hotspot_info = {
                    'parameter': parameter,
                    'level': level,
                    'severity': severity,
                    'max_value': max_value,
                    'mean_value': mean_value,
                    'num_sensors': len(cluster),
                    'center_lat': cluster_data['Latitude'].mean(),
                    'center_lon': cluster_data['Longitude'].mean(),
                    'lat_range': (cluster_data['Latitude'].min(), cluster_data['Latitude'].max()),
                    'lon_range': (cluster_data['Longitude'].min(), cluster_data['Longitude'].max()),
                    'sensors': cluster_data[['Latitude', 'Longitude', 'Concentration', 'SiteName']].to_dict('records')
                }
                hotspots.append(hotspot_info)
    
    # Sort by severity and parameter importance
    param_priority = {'PM2.5': 3, 'PM10': 2, 'O3': 1}
    hotspots.sort(key=lambda x: (x['severity'], param_priority.get(x['parameter'], 0)), reverse=True)
    
    return hotspots

def check_regional_alerts(df, regions, thresholds):
    """Check if monitored regions exceed pollution thresholds"""
    alerts = []
    
    for region_name, region_info in regions.items():
        # Find sensors within radius of region
        region_sensors = df[
            (np.abs(df['Latitude'] - region_info['lat']) <= region_info['radius']) &
            (np.abs(df['Longitude'] - region_info['lon']) <= region_info['radius'])
        ]
        
        if len(region_sensors) > 0:
            # Check each parameter
            for parameter in region_sensors['ParameterName'].unique():
                param_sensors = region_sensors[region_sensors['ParameterName'] == parameter]
                
                if len(param_sensors) > 0:
                    max_value = param_sensors['Concentration'].max()
                    mean_value = param_sensors['Concentration'].mean()
                    
                    level, severity = classify_aqi_level(max_value, parameter, thresholds)
                    
                    if severity >= 1:  # Alert if moderate or worse
                        alerts.append({
                            'region': region_name,
                            'parameter': parameter,
                            'lat': region_info['lat'],
                            'lon': region_info['lon'],
                            'level': level,
                            'severity': severity,
                            'max_value': max_value,
                            'mean_value': mean_value,
                            'num_sensors': len(param_sensors)
                        })
    
    return sorted(alerts, key=lambda x: (x['severity'], x['parameter']), reverse=True)

# ============== VISUALIZATION ==============
def make_nice_map(axis):
    """Create a nice map for California region"""
    axis.set_extent([
        SPATIAL_BOUNDS['lon_min'] - 1, 
        SPATIAL_BOUNDS['lon_max'] + 1,
        SPATIAL_BOUNDS['lat_min'] - 0.5, 
        SPATIAL_BOUNDS['lat_max'] + 0.5
    ], crs=ccrs.PlateCarree())
    
    axis.add_feature(cfeature.OCEAN, color="lightblue", zorder=0)
    axis.add_feature(cfeature.LAND, color="wheat", zorder=0)
    axis.add_feature(cfeature.STATES, color="grey", linewidth=1.5, zorder=1)
    axis.coastlines(resolution="10m", color="gray", linewidth=1, zorder=1)
    
    grid = axis.gridlines(draw_labels=["left", "bottom"], dms=True, linestyle=":")
    grid.xformatter = LONGITUDE_FORMATTER
    grid.yformatter = LATITUDE_FORMATTER

def visualize_sensor_data(df, hotspots, regional_alerts):
    """Create comprehensive sensor data visualization"""
    
    data_proj = ccrs.PlateCarree()
    
    # Create figure with subplots
    fig = plt.figure(figsize=(20, 12))
    
    # Left plot: Sensor locations with concentrations
    ax1 = fig.add_subplot(221, projection=data_proj)
    make_nice_map(ax1)
    
    # Plot sensors by parameter
    colors = {'PM2.5': 'red', 'PM10': 'orange', 'O3': 'blue'}
    sizes = {'PM2.5': 80, 'PM10': 60, 'O3': 40}
    
    for parameter in df['ParameterName'].unique():
        param_data = df[df['ParameterName'] == parameter]
        
        # Color by concentration level
        scatter_colors = []
        for _, row in param_data.iterrows():
            _, severity = classify_aqi_level(row['Concentration'], parameter, AQI_THRESHOLDS)
            if severity >= 4:
                scatter_colors.append('purple')
            elif severity >= 3:
                scatter_colors.append('red')
            elif severity >= 2:
                scatter_colors.append('orange')
            elif severity >= 1:
                scatter_colors.append('yellow')
            else:
                scatter_colors.append('green')
        
        ax1.scatter(param_data['Longitude'], param_data['Latitude'], 
                   c=scatter_colors, s=sizes[parameter], alpha=0.7, 
                   edgecolors='black', linewidth=0.5, transform=data_proj, zorder=3,
                   label=f'{parameter} ({len(param_data)} sensors)')
    
    # Mark monitored regions
    for region_name, region_info in MONITORED_REGIONS.items():
        if 'Wildfire' in region_name:
            ax1.plot(region_info['lon'], region_info['lat'], 'r*', 
                    markersize=15, transform=data_proj, zorder=4,
                    markeredgecolor='black', markeredgewidth=1)
            ax1.text(region_info['lon'], region_info['lat'] + 0.15, region_name,
                    fontsize=9, ha='center', weight='bold', color='red',
                    transform=data_proj, zorder=4,
                    bbox=dict(boxstyle='round', facecolor='white', alpha=0.9, edgecolor='red'))
        else:
            ax1.plot(region_info['lon'], region_info['lat'], 'bo', 
                    markersize=6, transform=data_proj, zorder=4)
            ax1.text(region_info['lon'], region_info['lat'] + 0.1, region_name,
                    fontsize=7, ha='center', transform=data_proj, zorder=4,
                    bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    ax1.legend(loc='upper right', fontsize=8)
    ax1.set_title("Ground Sensor Network\nAir Quality Measurements", 
                  fontsize=12, weight='bold', pad=10)
    
    # Right plot: Hotspot detection
    ax2 = fig.add_subplot(222, projection=data_proj)
    make_nice_map(ax2)
    
    # Plot all sensors
    ax2.scatter(df['Longitude'], df['Latitude'], c='lightgray', s=30, 
               alpha=0.5, transform=data_proj, zorder=2)
    
    # Highlight hotspots
    hotspot_colors = {'hazardous': 'purple', 'very_unhealthy': 'red', 
                     'unhealthy': 'orange', 'unhealthy_sensitive': 'yellow', 
                     'moderate': 'lightyellow'}
    
    for i, hotspot in enumerate(hotspots[:10]):  # Show top 10 hotspots
        color = hotspot_colors.get(hotspot['level'], 'yellow')
        
        # Draw hotspot area
        circle = Circle((hotspot['center_lon'], hotspot['center_lat']), 0.1,
                      edgecolor=color, facecolor=color, alpha=0.3, 
                      linewidth=2, transform=data_proj, zorder=3)
        ax2.add_patch(circle)
        
        # Label hotspot
        ax2.text(hotspot['center_lon'], hotspot['center_lat'], str(i+1),
                fontsize=10, ha='center', va='center', weight='bold',
                color='black', transform=data_proj, zorder=4,
                bbox=dict(boxstyle='circle', facecolor='white', alpha=0.9))
    
    ax2.set_title(f"Detected Pollution Hotspots\n({len(hotspots)} hotspots identified)", 
                  fontsize=12, weight='bold', pad=10)
    
    # Bottom left: Regional alerts
    ax3 = fig.add_subplot(223, projection=data_proj)
    make_nice_map(ax3)
    
    # Plot sensors
    ax3.scatter(df['Longitude'], df['Latitude'], c='lightgray', s=20, 
               alpha=0.3, transform=data_proj, zorder=2)
    
    # Mark alerted regions
    for alert in regional_alerts:
        marker_colors = {'moderate': 'yellow', 'unhealthy_sensitive': 'orange',
                        'unhealthy': 'red', 'very_unhealthy': 'red', 
                        'hazardous': 'purple'}
        
        circle = Circle((alert['lon'], alert['lat']), 0.15,
                      edgecolor='black', facecolor=marker_colors.get(alert['level'], 'red'),
                      linewidth=2, alpha=0.8, transform=data_proj, zorder=4)
        ax3.add_patch(circle)
        
        ax3.text(alert['lon'], alert['lat'] - 0.25, f"{alert['region']}\n{alert['parameter']}",
                fontsize=8, ha='center', weight='bold', transform=data_proj,
                zorder=4, bbox=dict(boxstyle='round', facecolor='white', 
                                   alpha=0.95, edgecolor='black', linewidth=1))
    
    ax3.set_title(f"Regional Alert Map\n({len(regional_alerts)} regions alerted)", 
                  fontsize=12, weight='bold', pad=10)
    
    # Bottom right: Data summary
    ax4 = fig.add_subplot(224)
    ax4.axis('off')
    
    # Create summary text
    summary_text = f"""
GROUND SENSOR DATA SUMMARY
==========================

Total Sensors: {len(df)}
Parameters: {', '.join(df['ParameterName'].unique())}
Date: {df['DateObserved'].iloc[0] if len(df) > 0 else 'N/A'}

POLLUTION LEVELS DETECTED:
"""
    
    for parameter in df['ParameterName'].unique():
        param_data = df[df['ParameterName'] == parameter]
        levels = []
        for _, row in param_data.iterrows():
            level, _ = classify_aqi_level(row['Concentration'], parameter, AQI_THRESHOLDS)
            levels.append(level)
        
        level_counts = pd.Series(levels).value_counts()
        summary_text += f"\n{parameter}:\n"
        for level, count in level_counts.items():
            summary_text += f"  {level}: {count} sensors\n"
    
    summary_text += f"\nHOTSPOTS: {len(hotspots)} detected\n"
    summary_text += f"REGIONAL ALERTS: {len(regional_alerts)} regions\n"
    
    ax4.text(0.05, 0.95, summary_text, transform=ax4.transAxes, fontsize=10,
             verticalalignment='top', fontfamily='monospace',
             bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.8))
    
    plt.suptitle(f"Ground Sensor Air Quality Analysis - {TIME_CONFIG['date']}\n"
                 f"Madre Wildfire Region, New Cuyama, California",
                 fontsize=14, weight='bold', y=0.98)
    
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    return fig

def print_alerts(hotspots, regional_alerts):
    """Print formatted alert messages"""
    print("\n" + "="*80)
    print("🔥 GROUND SENSOR POLLUTION ALERT REPORT - MADRE WILDFIRE REGION 🔥")
    print("="*80)
    
    if regional_alerts:
        print(f"\n🚨 REGIONAL ALERTS: {len(regional_alerts)} REGION(S) AFFECTED")
        print("-" * 80)
        for i, alert in enumerate(regional_alerts, 1):
            emoji = {'moderate': '🟡', 'unhealthy_sensitive': '🟠', 
                    'unhealthy': '🔴', 'very_unhealthy': '🔴', 'hazardous': '🟣'}
            print(f"\n{emoji.get(alert['level'], '⚠️')} ALERT #{i}: {alert['region'].upper()} - {alert['parameter']} - {alert['level'].upper().replace('_', ' ')}")
            print(f"   📍 Location: {alert['lat']:.4f}°N, {abs(alert['lon']):.4f}°W")
            print(f"   📈 Max {alert['parameter']}: {alert['max_value']:.1f} μg/m³")
            print(f"   📊 Mean {alert['parameter']}: {alert['mean_value']:.1f} μg/m³")
            print(f"   🗺️  Coverage: {alert['num_sensors']} sensors")
            
            if alert['level'] in ['hazardous', 'very_unhealthy']:
                print(f"   ⚠️  ACTION: STAY INDOORS! Air quality is dangerous for all groups.")
            elif alert['level'] == 'unhealthy':
                print(f"   ⚠️  ACTION: Limit outdoor activities, especially for sensitive groups.")
            elif alert['level'] == 'unhealthy_sensitive':
                print(f"   ⚠️  ACTION: Sensitive groups should reduce outdoor activities.")
            else:
                print(f"   ⚠️  ACTION: Sensitive groups should consider limiting prolonged outdoor exertion.")
    else:
        print("\n✅ NO REGIONAL ALERTS - All monitored regions have acceptable air quality")
    
    print("\n" + "-"*80)
    print(f"\n🔥 DETECTED POLLUTION HOTSPOTS: {len(hotspots)} IDENTIFIED")
    print("-" * 80)
    
    if hotspots:
        # Show top 10 most severe hotspots
        for i, hotspot in enumerate(hotspots[:10], 1):
            print(f"\n🔥 HOTSPOT #{i}")
            print(f"   📍 Center: {hotspot['center_lat']:.4f}°N, {abs(hotspot['center_lon']):.4f}°W")
            print(f"   🚨 Level: {hotspot['level'].upper().replace('_', ' ')}")
            print(f"   📊 Parameter: {hotspot['parameter']}")
            print(f"   📈 Max {hotspot['parameter']}: {hotspot['max_value']:.1f} μg/m³")
            print(f"   📊 Mean {hotspot['parameter']}: {hotspot['mean_value']:.1f} μg/m³")
            print(f"   🗺️  Coverage: {hotspot['num_sensors']} sensors")
            print(f"   🗺️  Area: Lat {hotspot['lat_range'][0]:.3f}° to {hotspot['lat_range'][1]:.3f}°")
            print(f"              Lon {hotspot['lon_range'][0]:.3f}° to {hotspot['lon_range'][1]:.3f}°")
            
            # Distance from wildfire center
            fire_lat, fire_lon = 35.0, -119.7
            dist = np.sqrt((hotspot['center_lat'] - fire_lat)**2 + 
                          (hotspot['center_lon'] - fire_lon)**2) * 111  # ~111 km per degree
            print(f"   📏 Distance from fire center: ~{dist:.1f} km")
    
    print("\n" + "="*80)
    print("💡 HEALTH RECOMMENDATIONS:")
    print("-" * 80)
    print("   🟢 GOOD: Air quality is satisfactory, outdoor activities are safe")
    print("   🟡 MODERATE: Unusually sensitive people should consider limiting prolonged outdoor exertion")
    print("   🟠 UNHEALTHY FOR SENSITIVE GROUPS: Sensitive groups should reduce prolonged or heavy outdoor exertion")
    print("   🔴 UNHEALTHY: Everyone should reduce prolonged or heavy outdoor exertion")
    print("   🔴 VERY UNHEALTHY: Everyone should avoid prolonged or heavy outdoor exertion")
    print("   🟣 HAZARDOUS: Everyone should avoid all outdoor physical activity")
    print("="*80)

# ============== MAIN EXECUTION ==============
if __name__ == "__main__":
    try:
        print("\n🌍 Starting Ground Sensor Pollution Detection System...")
        
        # Fetch data
        print("\n📡 Fetching ground sensor data...")
        raw_data = fetch_airnow_data()
        
        if raw_data:
            # Process data
            print("\n📂 Processing sensor data...")
            df = process_sensor_data(raw_data)
            
            if len(df) > 0:
                # Detect hotspots
                print("\n🔍 Detecting pollution hotspots...")
                hotspots = detect_pollution_hotspots(df, min_sensors=2, max_distance=50)
                
                # Check regional alerts
                print("🏙️  Checking monitored regions...")
                regional_alerts = check_regional_alerts(df, MONITORED_REGIONS, AQI_THRESHOLDS)
                
                # Print alerts
                print_alerts(hotspots, regional_alerts)
                
                # Visualize
                print("\n📈 Creating comprehensive visualization...")
                fig = visualize_sensor_data(df, hotspots, regional_alerts)
                
                # Save figure
                output_file = 'ground_sensor_pollution_analysis.png'
                plt.savefig(output_file, dpi=300, bbox_inches='tight')
                print(f"\n✅ Map saved as '{output_file}'")
                
                plt.show()
                
                print("\n✨ Analysis complete!")
                print("="*80)
                
            else:
                print("\n❌ No valid sensor data found")
                
        else:
            print("\n❌ Failed to fetch sensor data")
            
    except Exception as e:
        print(f"\n❌ Error occurred: {str(e)}")
        import traceback
        traceback.print_exc()
