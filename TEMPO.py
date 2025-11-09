import datetime as dt
import getpass
import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from cartopy.mpl.gridliner import LONGITUDE_FORMATTER, LATITUDE_FORMATTER
import xarray as xr
from harmony import BBox, Client, Collection, Request
from xarray.plot.utils import label_from_attrs
from scipy import ndimage

# ============== AUTHENTICATION ==============
print("="*80)
print("TEMPO POLLUTION DETECTION & ALERT SYSTEM")
print("Madre Wildfire Region - New Cuyama, California")
print("="*80)
print("\nPlease provide your Earthdata Login credentials to allow data access")
print("Your credentials will only be passed to Earthdata and will not be exposed")
username = input("Username: ")
harmony_client = Client(auth=(username, getpass.getpass()))

# ============== CONFIGURATION ==============
# Pollutant thresholds (in molecules/cm²) - adjusted for wildfire scenarios
POLLUTION_THRESHOLDS = {
    'NO2': {
        'moderate': 5.0e15,      # Moderate pollution
        'unhealthy': 1.0e16,     # Unhealthy for sensitive groups
        'very_unhealthy': 2.0e16, # Very unhealthy
        'hazardous': 3.0e16      # Hazardous - wildfire levels
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

# Time period (UTC) - Day after fire start
TIME_CONFIG = {
    'start': dt.datetime(2025, 7, 3, 20, 0, 0),
    'stop': dt.datetime(2025, 7, 3, 20, 15, 0)
}

print(f"\n📅 Time Period: {TIME_CONFIG['start']} UTC to {TIME_CONFIG['stop']} UTC")
print("   (Approximately 1:00 PM Pacific time during the Madre wildfire)")
print(f"\n📍 Region: Madre wildfire area, New Cuyama, California")
print(f"   Longitude: {SPATIAL_BOUNDS['lon_min']}° to {SPATIAL_BOUNDS['lon_max']}°")
print(f"   Latitude: {SPATIAL_BOUNDS['lat_min']}° to {SPATIAL_BOUNDS['lat_max']}°")

# ============== DATA RETRIEVAL ==============
def fetch_tempo_data():
    """Fetch TEMPO NO2 Level-3 data using Harmony for Madre wildfire region"""
    
    request = Request(
        # Level-3, V03, "Nitrogen Dioxide tropospheric and stratospheric columns" collection
        collection=Collection(id="C2930763263-LARC_CLOUD"),
        temporal={
            "start": TIME_CONFIG['start'],
            "stop": TIME_CONFIG['stop'],
        },
        spatial=BBox(
            SPATIAL_BOUNDS['lon_min'], 
            SPATIAL_BOUNDS['lat_min'],
            SPATIAL_BOUNDS['lon_max'], 
            SPATIAL_BOUNDS['lat_max']
        ),
    )
    
    print("\n📋 Request Validation:")
    print(f"   ✓ Valid request: {request.is_valid()}")
    print(f"   ✓ Time period: {request.temporal['start']} to {request.temporal['stop']}")
    print(f"   ✓ Spatial bounds: {request.spatial}")
    
    if not request.is_valid():
        raise ValueError("Invalid Harmony request")
    
    job_id = harmony_client.submit(request)
    print(f"\n📡 Harmony Job ID: {job_id}")
    print("⏳ Waiting for processing...")
    
    harmony_client.wait_for_processing(job_id, show_progress=True)
    
    # Create download directory in current directory
    download_dir = os.path.join(os.getcwd(), "TempData")
    os.makedirs(download_dir, exist_ok=True)
    
    results = harmony_client.download_all(job_id, directory=download_dir)
    all_results = [f.result() for f in results]
    
    print(f"\n✓ Data downloaded successfully!")
    print(f"✓ Files saved to: {download_dir}")
    print(f"✓ Number of files: {len(all_results)}")
    
    return all_results[0] if all_results else None

# ============== POLLUTION DETECTION ==============
def classify_pollution_level(value, thresholds):
    """Classify pollution level based on concentration value"""
    if np.isnan(value):
        return 'no_data', 0
    elif value >= thresholds['hazardous']:
        return 'hazardous', 4
    elif value >= thresholds['very_unhealthy']:
        return 'very_unhealthy', 3
    elif value >= thresholds['unhealthy']:
        return 'unhealthy', 2
    elif value >= thresholds['moderate']:
        return 'moderate', 1
    else:
        return 'good', 0

def detect_pollution_hotspots(data, lats, lons, thresholds, min_cluster_size=3):
    """
    Detect regions with high pollution concentrations
    
    Parameters:
    - data: 2D array of pollution values (already filtered by quality flag)
    - lats, lons: 1D or 2D arrays of latitude and longitude
    - thresholds: dictionary of threshold values
    - min_cluster_size: minimum number of connected pixels to consider a hotspot
    
    Returns:
    - hotspots: list of dictionaries containing hotspot information
    """
    hotspots = []
    
    # Handle 1D coordinate arrays (Level-3 gridded data)
    if lats.ndim == 1 and lons.ndim == 1:
        # Create 2D meshgrid from 1D arrays
        lon_grid, lat_grid = np.meshgrid(lons, lats)
    else:
        # Already 2D arrays (Level-2 data)
        lat_grid = lats
        lon_grid = lons
    
    # Process each threshold level from highest to lowest
    for level_name, threshold in [('hazardous', thresholds['hazardous']),
                                   ('very_unhealthy', thresholds['very_unhealthy']),
                                   ('unhealthy', thresholds['unhealthy']),
                                   ('moderate', thresholds['moderate'])]:
        
        mask = data >= threshold
        
        # Label connected regions
        labeled_array, num_features = ndimage.label(mask)
        
        # Find clusters larger than minimum size
        for region_id in range(1, num_features + 1):
            region_mask = labeled_array == region_id
            region_size = np.sum(region_mask)
            
            if region_size >= min_cluster_size:
                # Get region statistics
                region_values = data[region_mask]
                region_lats = lat_grid[region_mask]
                region_lons = lon_grid[region_mask]
                
                hotspot_info = {
                    'level': level_name,
                    'size_pixels': region_size,
                    'max_value': np.nanmax(region_values),
                    'mean_value': np.nanmean(region_values),
                    'center_lat': np.mean(region_lats),
                    'center_lon': np.mean(region_lons),
                    'lat_range': (np.min(region_lats), np.max(region_lats)),
                    'lon_range': (np.min(region_lons), np.max(region_lons)),
                    'area_km2': region_size * 2.1 * 4.4,  # TEMPO L3 resolution
                    'mask': region_mask
                }
                hotspots.append(hotspot_info)
    
    # Sort by severity and size
    hotspots.sort(key=lambda x: (
        {'hazardous': 4, 'very_unhealthy': 3, 'unhealthy': 2, 'moderate': 1}[x['level']],
        x['max_value']
    ), reverse=True)
    
    return hotspots

def check_regional_alerts(data, lats, lons, regions, thresholds):
    """Check if monitored regions exceed pollution thresholds"""
    alerts = []
    
    # Handle 1D coordinate arrays (Level-3 gridded data)
    if lats.ndim == 1 and lons.ndim == 1:
        # Create 2D meshgrid from 1D arrays
        lon_grid, lat_grid = np.meshgrid(lons, lats)
    else:
        # Already 2D arrays (Level-2 data)
        lat_grid = lats
        lon_grid = lons
    
    for region_name, region_info in regions.items():
        # Find data points within radius of region
        lat_mask = np.abs(lat_grid - region_info['lat']) <= region_info['radius']
        lon_mask = np.abs(lon_grid - region_info['lon']) <= region_info['radius']
        region_mask = lat_mask & lon_mask
        
        if np.sum(region_mask) > 0:
            region_values = data[region_mask]
            region_values = region_values[~np.isnan(region_values)]
            
            if len(region_values) > 0:
                max_value = np.max(region_values)
                mean_value = np.mean(region_values)
                
                level, severity = classify_pollution_level(max_value, thresholds)
                
                if severity > 0:  # Alert if above 'good' level
                    alerts.append({
                        'region': region_name,
                        'lat': region_info['lat'],
                        'lon': region_info['lon'],
                        'level': level,
                        'severity': severity,
                        'max_value': max_value,
                        'mean_value': mean_value,
                        'num_pixels': len(region_values)
                    })
    
    return sorted(alerts, key=lambda x: x['severity'], reverse=True)

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

def visualize_pollution_with_alerts(datatree, hotspots, regional_alerts, thresholds):
    """Create comprehensive pollution map with hotspots and alerts"""
    
    data_proj = ccrs.PlateCarree()
    product_variable_name = "product/vertical_column_troposphere"
    da = datatree[product_variable_name]
    
    # Get coordinates - handle both 1D and 2D arrays
    lons_raw = datatree["geolocation/longitude"].values
    lats_raw = datatree["geolocation/latitude"].values
    
    # Create 2D grids if coordinates are 1D (Level-3 data)
    if lons_raw.ndim == 1 and lats_raw.ndim == 1:
        lons, lats = np.meshgrid(lons_raw, lats_raw)
    else:
        lons = lons_raw
        lats = lats_raw
    
    quality_flag = datatree["product/main_data_quality_flag"].values
    
    # Filter by quality flag
    good_data = da.where(quality_flag == 0).squeeze()
    
    print(f"\n📊 Data Statistics:")
    print(f"   Data size in memory: {good_data.nbytes / 1e6:.1f} MB")
    print(f"   Data shape: {good_data.shape}")
    print(f"   Coordinate shapes: lons={lons.shape}, lats={lats.shape}")
    print(f"   Data range: {good_data.min().values:.2e} to {good_data.max().values:.2e} {da.attrs.get('units', '')}")
    print(f"   Mean value: {good_data.mean().values:.2e}")
    print(f"\n   Reference values:")
    print(f"   - Typical moderate to heavily polluted urban: >5×10¹⁵ molecules/cm²")
    print(f"   - Typical rural areas: <5×10¹⁵ molecules/cm²")
    print(f"   - Wildfire-affected areas: May show elevated NO₂ from combustion")
    
    # Create figure with three subplots
    fig = plt.figure(figsize=(24, 8))
    
    # Left plot: Standard pollution concentration map
    ax1 = fig.add_subplot(131, projection=data_proj)
    make_nice_map(ax1)
    
    contour1 = ax1.contourf(
        lons, lats, good_data,
        levels=30,
        vmin=0,
        vmax=float(good_data.max()),
        alpha=0.7,
        cmap='YlOrRd',
        zorder=2
    )
    
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
    
    cb1 = plt.colorbar(contour1, ax=ax1, fraction=0.046, pad=0.04)
    cb1.set_label(label_from_attrs(da), fontsize=10)
    ax1.set_title("NO₂ Tropospheric Column Concentration\nMadre Wildfire Region", 
                  fontsize=12, weight='bold', pad=10)
    
    # Middle plot: Hotspot detection map
    ax2 = fig.add_subplot(132, projection=data_proj)
    make_nice_map(ax2)
    
    contour2 = ax2.contourf(
        lons, lats, good_data,
        levels=30,
        vmin=0,
        vmax=float(good_data.max()),
        alpha=0.6,
        cmap='inferno',
        zorder=2
    )
    
    # Draw hotspot boundaries
    colors = {'hazardous': 'purple', 'very_unhealthy': 'red', 
              'unhealthy': 'orange', 'moderate': 'yellow'}
    for i, hotspot in enumerate(hotspots[:15]):  # Show top 15 hotspots
        lon_min, lon_max = hotspot['lon_range']
        lat_min, lat_max = hotspot['lat_range']
        rect = Rectangle((lon_min, lat_min), lon_max - lon_min, 
                         lat_max - lat_min, linewidth=2.5, 
                         edgecolor=colors.get(hotspot['level'], 'yellow'),
                         facecolor='none', transform=data_proj, zorder=3)
        ax2.add_patch(rect)
        
        # Label hotspot number for top 5
        if i < 5:
            ax2.text(hotspot['center_lon'], hotspot['center_lat'], str(i+1),
                    fontsize=10, ha='center', va='center', weight='bold',
                    color='white', transform=data_proj, zorder=4,
                    bbox=dict(boxstyle='circle', facecolor=colors.get(hotspot['level'], 'yellow'),
                             edgecolor='black', linewidth=1.5))
    
    cb2 = plt.colorbar(contour2, ax=ax2, fraction=0.046, pad=0.04)
    cb2.set_label(label_from_attrs(da), fontsize=10)
    ax2.set_title(f"Detected Pollution Hotspots\n({len(hotspots)} hotspots identified)", 
                  fontsize=12, weight='bold', pad=10)
    
    # Right plot: Alert level map
    ax3 = fig.add_subplot(133, projection=data_proj)
    make_nice_map(ax3)
    
    # Create categorical alert map
    alert_levels = np.zeros_like(good_data.values)
    for i in range(good_data.shape[0]):
        for j in range(good_data.shape[1]):
            if not np.isnan(good_data.values[i, j]):
                _, severity = classify_pollution_level(good_data.values[i, j], thresholds)
                alert_levels[i, j] = severity
            else:
                alert_levels[i, j] = np.nan
    
    alert_colors = ['green', 'yellow', 'orange', 'red', 'purple']
    contour3 = ax3.contourf(lons, lats, alert_levels, 
                            levels=[-0.5, 0.5, 1.5, 2.5, 3.5, 4.5],
                            colors=alert_colors, alpha=0.7, zorder=2)
    
    # Mark alerted regions with circles
    for alert in regional_alerts:
        marker_colors = {'moderate': 'yellow', 'unhealthy': 'orange',
                        'very_unhealthy': 'red', 'hazardous': 'purple'}
        
        circle = Circle((alert['lon'], alert['lat']), 0.15,
                       edgecolor='black', facecolor=marker_colors.get(alert['level'], 'red'),
                       linewidth=2.5, alpha=0.8, transform=data_proj, zorder=4)
        ax3.add_patch(circle)
        
        ax3.text(alert['lon'], alert['lat'] - 0.25, alert['region'],
                fontsize=8, ha='center', weight='bold', transform=data_proj,
                zorder=4, bbox=dict(boxstyle='round', facecolor='white', 
                                   alpha=0.95, edgecolor='black', linewidth=1.5))
    
    cb3 = plt.colorbar(contour3, ax=ax3, fraction=0.046, pad=0.04,
                      ticks=[0, 1, 2, 3, 4])
    cb3.set_ticklabels(['Good', 'Moderate', 'Unhealthy', 'Very\nUnhealthy', 'Hazardous'])
    cb3.set_label('Air Quality Level', fontsize=10)
    ax3.set_title(f"Regional Alert Map\n({len(regional_alerts)} regions alerted)", 
                  fontsize=12, weight='bold', pad=10)
    
    plt.suptitle(f"TEMPO NO₂ Analysis - {TIME_CONFIG['start'].strftime('%Y-%m-%d %H:%M UTC')}\n"
                 f"Madre Wildfire Region, New Cuyama, California",
                 fontsize=14, weight='bold', y=0.98)
    
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    return fig

def print_alerts(hotspots, regional_alerts):
    """Print formatted alert messages"""
    print("\n" + "="*80)
    print("🔥 POLLUTION ALERT REPORT - MADRE WILDFIRE REGION 🔥")
    print("="*80)
    
    if regional_alerts:
        print(f"\n🚨 REGIONAL ALERTS: {len(regional_alerts)} REGION(S) AFFECTED")
        print("-" * 80)
        for i, alert in enumerate(regional_alerts, 1):
            emoji = {'moderate': '🟡', 'unhealthy': '🟠', 
                    'very_unhealthy': '🔴', 'hazardous': '🟣'}
            print(f"\n{emoji.get(alert['level'], '⚠️')} ALERT #{i}: {alert['region'].upper()} - {alert['level'].upper().replace('_', ' ')}")
            print(f"   📍 Location: {alert['lat']:.4f}°N, {abs(alert['lon']):.4f}°W")
            print(f"   📈 Max NO₂: {alert['max_value']:.2e} molecules/cm²")
            print(f"   📊 Mean NO₂: {alert['mean_value']:.2e} molecules/cm²")
            print(f"   🗺️  Coverage: {alert['num_pixels']} data points")
            
            if alert['level'] in ['hazardous', 'very_unhealthy']:
                print(f"   ⚠️  ACTION: STAY INDOORS! Air quality is dangerous for all groups.")
            elif alert['level'] == 'unhealthy':
                print(f"   ⚠️  ACTION: Limit outdoor activities, especially for sensitive groups.")
            else:
                print(f"   ⚠️  ACTION: Sensitive groups should reduce outdoor activities.")
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
            print(f"   📏 Area: ~{hotspot['area_km2']:.1f} km²  ({hotspot['size_pixels']} pixels)")
            print(f"   📈 Max NO₂: {hotspot['max_value']:.2e} molecules/cm²")
            print(f"   📊 Mean NO₂: {hotspot['mean_value']:.2e} molecules/cm²")
            print(f"   🗺️  Coverage: Lat {hotspot['lat_range'][0]:.3f}° to {hotspot['lat_range'][1]:.3f}°")
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
    print("   🟠 UNHEALTHY: Sensitive groups should reduce prolonged or heavy outdoor exertion")
    print("   🔴 VERY UNHEALTHY: Everyone should reduce prolonged or heavy outdoor exertion")
    print("   🟣 HAZARDOUS: Everyone should avoid all outdoor physical activity")
    print("="*80)

# ============== MAIN EXECUTION ==============
if __name__ == "__main__":
    try:
        print("\n🌍 Starting TEMPO Pollution Detection System...")
        
        # Fetch data
        print("\n📡 Fetching TEMPO Level-3 NO₂ data...")
        data_file = fetch_tempo_data()
        
        if data_file:
            # Load data
            print(f"\n📂 Loading data from: {data_file}")
            datatree = xr.open_datatree(data_file)
            
            product_variable_name = "product/vertical_column_troposphere"
            da = datatree[product_variable_name]
            lons = datatree["geolocation/longitude"].values
            lats = datatree["geolocation/latitude"].values
            quality_flag = datatree["product/main_data_quality_flag"].values
            
            # Filter by quality flag
            good_data = da.where(quality_flag == 0).squeeze()
            
            # Detect hotspots
            print("\n🔍 Detecting pollution hotspots...")
            hotspots = detect_pollution_hotspots(
                good_data.values, lats, lons,
                POLLUTION_THRESHOLDS['NO2'], min_cluster_size=3
            )
            
            # Check regional alerts
            print("🏙️  Checking monitored regions...")
            regional_alerts = check_regional_alerts(
                good_data.values, lats, lons,
                MONITORED_REGIONS, POLLUTION_THRESHOLDS['NO2']
            )
            
            # Print alerts
            print_alerts(hotspots, regional_alerts)
            
            # Visualize
            print("\n📈 Creating comprehensive visualization...")
            fig = visualize_pollution_with_alerts(
                datatree, hotspots, regional_alerts, 
                POLLUTION_THRESHOLDS['NO2']
            )
            
            # Save figure
            output_file = 'madre_wildfire_pollution_analysis.png'
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            print(f"\n✅ Map saved as '{output_file}'")
            
            plt.show()
            
            print("\n✨ Analysis complete!")
            print("="*80)
            
        else:
            print("\n❌ Failed to fetch data")
            
    except Exception as e:
        print(f"\n❌ Error occurred: {str(e)}")
        import traceback
        traceback.print_exc()