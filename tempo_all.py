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
from typing import Dict, List, Tuple, Optional, Any
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import warnings
warnings.filterwarnings('ignore')

class TempoMultiGasAnalyzer:
    """Enhanced TEMPO analyzer supporting multiple gases and dynamic coordinates"""
    
    def __init__(self, username: str = None, password: str = None):
        """Initialize the analyzer with Earthdata credentials"""
        if username and password:
            self.harmony_client = Client(auth=(username, password))
        else:
            # Interactive login for development
            print("Please provide your Earthdata Login credentials:")
            username = input("Username: ")
            self.harmony_client = Client(auth=(username, getpass.getpass()))
        
        # TEMPO Collection IDs for different data products
        self.COLLECTIONS = {
            'NO2': "C2930763263-LARC_CLOUD",  # NO2 Level-3
            'CH2O': "C2930763264-LARC_CLOUD", # Formaldehyde Level-3 
            'AI': "C2930763265-LARC_CLOUD",   # Aerosol Index Level-3
            'PM': "C2930763266-LARC_CLOUD",   # Particulate Matter Level-3
            'O3': "C2930763267-LARC_CLOUD"    # Ozone Level-3
        }
        
        # Variable names for each gas in TEMPO data
        self.VARIABLE_NAMES = {
            'NO2': "product/vertical_column_troposphere",
            'CH2O': "product/vertical_column_troposphere", 
            'AI': "product/aerosol_index_354_388",
            'PM': "product/aerosol_optical_depth_550",
            'O3': "product/ozone_total_column"
        }
        
        # Units for each gas
        self.UNITS = {
            'NO2': "molecules/cm²",
            'CH2O': "molecules/cm²",
            'AI': "index",
            'PM': "dimensionless",
            'O3': "Dobson Units"
        }
        
        # Pollution thresholds for each gas
        self.POLLUTION_THRESHOLDS = {
            'NO2': {
                'moderate': 5.0e15,
                'unhealthy': 1.0e16,
                'very_unhealthy': 2.0e16,
                'hazardous': 3.0e16
            },
            'CH2O': {
                'moderate': 8.0e15,
                'unhealthy': 1.6e16,
                'very_unhealthy': 3.2e16,
                'hazardous': 6.4e16
            },
            'AI': {
                'moderate': 1.0,
                'unhealthy': 2.0,
                'very_unhealthy': 4.0,
                'hazardous': 7.0
            },
            'PM': {
                'moderate': 0.2,
                'unhealthy': 0.5,
                'very_unhealthy': 1.0,
                'hazardous': 2.0
            },
            'O3': {
                'moderate': 220,
                'unhealthy': 280,
                'very_unhealthy': 400,
                'hazardous': 500
            }
        }
        
        self.geolocator = Nominatim(user_agent="tempo_pollution_analyzer")
    
    def geocode_location(self, location_name: str) -> Optional[Tuple[float, float]]:
        """Convert location name to coordinates"""
        try:
            location = self.geolocator.geocode(location_name, timeout=10)
            if location:
                return (location.latitude, location.longitude)
            else:
                print(f"Could not geocode location: {location_name}")
                return None
        except GeocoderTimedOut:
            print(f"Geocoding timeout for location: {location_name}")
            return None
        except Exception as e:
            print(f"Geocoding error: {str(e)}")
            return None
    
    def get_spatial_bounds(self, lat: float, lon: float, radius: float) -> Dict[str, float]:
        """Calculate spatial bounds based on center coordinates and radius"""
        return {
            'lon_min': lon - radius,
            'lon_max': lon + radius,
            'lat_min': lat - radius,
            'lat_max': lat + radius
        }
    
    def fetch_tempo_data(self, gas: str, spatial_bounds: Dict[str, float], 
                        start_time: dt.datetime, end_time: dt.datetime) -> Optional[str]:
        """Fetch TEMPO data for a specific gas and region"""
        
        if gas not in self.COLLECTIONS:
            raise ValueError(f"Unsupported gas: {gas}. Supported: {list(self.COLLECTIONS.keys())}")
        
        collection_id = self.COLLECTIONS[gas]
        
        request = Request(
            collection=Collection(id=collection_id),
            temporal={
                "start": start_time,
                "stop": end_time,
            },
            spatial=BBox(
                spatial_bounds['lon_min'], 
                spatial_bounds['lat_min'],
                spatial_bounds['lon_max'], 
                spatial_bounds['lat_max']
            ),
        )
        
        print(f"📡 Fetching {gas} data...")
        print(f"   Collection: {collection_id}")
        print(f"   Time: {start_time} to {end_time}")
        print(f"   Bounds: {spatial_bounds}")
        
        if not request.is_valid():
            print(f"❌ Invalid request for {gas}")
            return None
        
        try:
            job_id = self.harmony_client.submit(request)
            print(f"   Job ID: {job_id}")
            
            self.harmony_client.wait_for_processing(job_id, show_progress=True)
            
            download_dir = os.path.join(os.getcwd(), "TempData", gas)
            os.makedirs(download_dir, exist_ok=True)
            
            results = self.harmony_client.download_all(job_id, directory=download_dir)
            all_results = [f.result() for f in results]
            
            if all_results:
                print(f"   ✓ {gas} data downloaded: {all_results[0]}")
                return all_results[0]
            else:
                print(f"   ❌ No data available for {gas}")
                return None
                
        except Exception as e:
            print(f"   ❌ Error fetching {gas} data: {str(e)}")
            return None
    
    def classify_pollution_level(self, value: float, gas: str) -> Tuple[str, int]:
        """Classify pollution level based on concentration value"""
        if np.isnan(value) or gas not in self.POLLUTION_THRESHOLDS:
            return 'no_data', 0
        
        thresholds = self.POLLUTION_THRESHOLDS[gas]
        
        if value >= thresholds['hazardous']:
            return 'hazardous', 4
        elif value >= thresholds['very_unhealthy']:
            return 'very_unhealthy', 3
        elif value >= thresholds['unhealthy']:
            return 'unhealthy', 2
        elif value >= thresholds['moderate']:
            return 'moderate', 1
        else:
            return 'good', 0
    
    def detect_hotspots(self, data: np.ndarray, lats: np.ndarray, lons: np.ndarray, 
                       gas: str, min_cluster_size: int = 3) -> List[Dict]:
        """Detect pollution hotspots for a specific gas"""
        hotspots = []
        
        if gas not in self.POLLUTION_THRESHOLDS:
            return hotspots
        
        # Handle 1D coordinate arrays (Level-3 gridded data)
        if lats.ndim == 1 and lons.ndim == 1:
            lon_grid, lat_grid = np.meshgrid(lons, lats)
        else:
            lat_grid = lats
            lon_grid = lons
        
        thresholds = self.POLLUTION_THRESHOLDS[gas]
        
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
                        'gas': gas,
                        'level': level_name,
                        'size_pixels': region_size,
                        'max_value': float(np.nanmax(region_values)),
                        'mean_value': float(np.nanmean(region_values)),
                        'center_lat': float(np.mean(region_lats)),
                        'center_lon': float(np.mean(region_lons)),
                        'lat_range': (float(np.min(region_lats)), float(np.max(region_lats))),
                        'lon_range': (float(np.min(region_lons)), float(np.max(region_lons))),
                        'area_km2': float(region_size * 2.1 * 4.4),  # TEMPO L3 resolution
                        'mask': region_mask
                    }
                    hotspots.append(hotspot_info)
        
        # Sort by severity and size
        hotspots.sort(key=lambda x: (
            {'hazardous': 4, 'very_unhealthy': 3, 'unhealthy': 2, 'moderate': 1}[x['level']],
            x['max_value']
        ), reverse=True)
        
        return hotspots
    
    def check_regional_alerts(self, data: np.ndarray, lats: np.ndarray, lons: np.ndarray,
                            center_lat: float, center_lon: float, radius: float, 
                            gas: str, location_name: str) -> List[Dict]:
        """Check if the specified region exceeds pollution thresholds"""
        alerts = []
        
        if gas not in self.POLLUTION_THRESHOLDS:
            return alerts
        
        # Handle 1D coordinate arrays (Level-3 gridded data)
        if lats.ndim == 1 and lons.ndim == 1:
            lon_grid, lat_grid = np.meshgrid(lons, lats)
        else:
            lat_grid = lats
            lon_grid = lons
        
        # Find data points within radius of region
        lat_mask = np.abs(lat_grid - center_lat) <= radius
        lon_mask = np.abs(lon_grid - center_lon) <= radius
        region_mask = lat_mask & lon_mask
        
        if np.sum(region_mask) > 0:
            region_values = data[region_mask]
            region_values = region_values[~np.isnan(region_values)]
            
            if len(region_values) > 0:
                max_value = float(np.max(region_values))
                mean_value = float(np.mean(region_values))
                
                level, severity = self.classify_pollution_level(max_value, gas)
                
                if severity > 0:  # Alert if above 'good' level
                    alerts.append({
                        'region': location_name,
                        'gas': gas,
                        'lat': center_lat,
                        'lon': center_lon,
                        'level': level,
                        'severity': severity,
                        'max_value': max_value,
                        'mean_value': mean_value,
                        'num_pixels': len(region_values)
                    })
        
        return alerts
    
    def create_visualization(self, gas_data: Dict[str, Any], location_name: str,
                           center_lat: float, center_lon: float, radius: float) -> str:
        """Create comprehensive pollution visualization for all gases"""
        
        # Determine number of gases with data
        available_gases = [gas for gas, data in gas_data.items() if data['datatree'] is not None]
        
        if not available_gases:
            print("No data available for visualization")
            return None
        
        # Create figure based on number of gases
        num_gases = len(available_gases)
        if num_gases == 1:
            fig, axes = plt.subplots(1, 1, figsize=(12, 8), 
                                   subplot_kw={'projection': ccrs.PlateCarree()})
            axes = [axes]
        elif num_gases <= 2:
            fig, axes = plt.subplots(1, 2, figsize=(20, 8), 
                                   subplot_kw={'projection': ccrs.PlateCarree()})
        elif num_gases <= 4:
            fig, axes = plt.subplots(2, 2, figsize=(20, 16), 
                                   subplot_kw={'projection': ccrs.PlateCarree()})
            axes = axes.flatten()
        else:
            fig, axes = plt.subplots(2, 3, figsize=(24, 16), 
                                   subplot_kw={'projection': ccrs.PlateCarree()})
            axes = axes.flatten()
        
        data_proj = ccrs.PlateCarree()
        
        # Set spatial extent
        extent = [center_lon - radius - 0.5, center_lon + radius + 0.5,
                 center_lat - radius - 0.5, center_lat + radius + 0.5]
        
        for idx, gas in enumerate(available_gases):
            if idx >= len(axes):
                break
                
            ax = axes[idx]
            gas_info = gas_data[gas]
            
            if gas_info['datatree'] is None:
                continue
            
            # Set up map
            ax.set_extent(extent, crs=data_proj)
            ax.add_feature(cfeature.OCEAN, color="lightblue", zorder=0)
            ax.add_feature(cfeature.LAND, color="wheat", zorder=0)
            ax.add_feature(cfeature.STATES, color="grey", linewidth=1, zorder=1)
            ax.coastlines(resolution="10m", color="gray", linewidth=1, zorder=1)
            
            # Add gridlines
            grid = ax.gridlines(draw_labels=["left", "bottom"], dms=True, linestyle=":")
            grid.xformatter = LONGITUDE_FORMATTER
            grid.yformatter = LATITUDE_FORMATTER
            
            # Get data
            datatree = gas_info['datatree']
            variable_name = self.VARIABLE_NAMES[gas]
            
            try:
                da = datatree[variable_name]
                lons_raw = datatree["geolocation/longitude"].values
                lats_raw = datatree["geolocation/latitude"].values
                quality_flag = datatree["product/main_data_quality_flag"].values
                
                # Create 2D grids if coordinates are 1D
                if lons_raw.ndim == 1 and lats_raw.ndim == 1:
                    lons, lats = np.meshgrid(lons_raw, lats_raw)
                else:
                    lons = lons_raw
                    lats = lats_raw
                
                # Filter by quality flag
                good_data = da.where(quality_flag == 0).squeeze()
                
                # Create contour plot
                if good_data.size > 0 and not np.all(np.isnan(good_data.values)):
                    contour = ax.contourf(
                        lons, lats, good_data,
                        levels=20,
                        vmin=0,
                        vmax=float(np.nanpercentile(good_data, 95)),
                        alpha=0.7,
                        cmap='YlOrRd',
                        zorder=2
                    )
                    
                    # Add colorbar
                    cb = plt.colorbar(contour, ax=ax, fraction=0.046, pad=0.04)
                    cb.set_label(f"{gas} ({self.UNITS[gas]})", fontsize=10)
                    
                    # Mark hotspots
                    hotspots = gas_info['hotspots']
                    colors = {'hazardous': 'purple', 'very_unhealthy': 'red', 
                             'unhealthy': 'orange', 'moderate': 'yellow'}
                    
                    for i, hotspot in enumerate(hotspots[:5]):  # Show top 5 hotspots
                        color = colors.get(hotspot['level'], 'yellow')
                        ax.plot(hotspot['center_lon'], hotspot['center_lat'], 'o',
                               color=color, markersize=8, markeredgecolor='black',
                               markeredgewidth=1, transform=data_proj, zorder=4)
                        
                        # Label hotspot
                        ax.text(hotspot['center_lon'], hotspot['center_lat'] + 0.05,
                               f"{i+1}", fontsize=8, ha='center', va='center',
                               weight='bold', color='white', transform=data_proj,
                               zorder=5, bbox=dict(boxstyle='circle', facecolor=color,
                                                  alpha=0.8, edgecolor='black'))\
                
                # Mark center location
                ax.plot(center_lon, center_lat, 'r*', markersize=15, 
                       transform=data_proj, zorder=4, markeredgecolor='black',
                       markeredgewidth=1)
                ax.text(center_lon, center_lat + 0.1, location_name,
                       fontsize=9, ha='center', weight='bold', color='red',
                       transform=data_proj, zorder=4,
                       bbox=dict(boxstyle='round', facecolor='white', 
                               alpha=0.9, edgecolor='red'))
                
                # Add circle showing search radius
                circle = Circle((center_lon, center_lat), radius,
                              edgecolor='red', facecolor='none', linewidth=2,
                              linestyle='--', alpha=0.7, transform=data_proj, zorder=3)
                ax.add_patch(circle)
                
            except Exception as e:
                print(f"Error visualizing {gas}: {str(e)}")
                ax.text(0.5, 0.5, f"Error loading {gas} data", 
                       transform=ax.transAxes, ha='center', va='center',
                       fontsize=12, color='red', weight='bold')
            
            ax.set_title(f"{gas} Concentration", fontsize=12, weight='bold', pad=10)
        
        # Hide unused subplots
        for idx in range(len(available_gases), len(axes)):
            axes[idx].set_visible(False)
        
        plt.suptitle(f"Multi-Gas Pollution Analysis - {location_name}\\n"
                    f"{dt.datetime.now().strftime('%Y-%m-%d %H:%M UTC')}",
                    fontsize=14, weight='bold', y=0.98)
        
        plt.tight_layout(rect=[0, 0, 1, 0.96])
        
        # Save figure
        timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f'pollution_analysis_{timestamp}.png'
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        return output_file
    
    def analyze_location(self, location_name: str, radius: float = 0.3, 
                        gases: List[str] = ['NO2'], 
                        start_time: Optional[dt.datetime] = None,
                        end_time: Optional[dt.datetime] = None) -> Dict[str, Any]:
        """Comprehensive multi-gas pollution analysis for a location"""
        
        # Geocode location (commented out for testing, using Madre Wildfire coordinates)
        # coordinates = self.geocode_location(location_name)
        # if not coordinates:
        #     raise ValueError(f"Could not find coordinates for location: {location_name}")
        # center_lat, center_lon = coordinates
        
        # FOR TESTING: Use Madre Wildfire Region coordinates
        center_lat, center_lon = 34.9, -119.7
        print(f"🧪 TESTING MODE: Using Madre Wildfire coordinates ({center_lat}, {center_lon})")
        
        # Set default time period if not provided
        if start_time is None:
            start_time = dt.datetime(2025, 7, 3, 20, 0, 0)
        if end_time is None:
            end_time = dt.datetime(2025, 7, 3, 20, 15, 0)
        
        # Calculate spatial bounds
        spatial_bounds = self.get_spatial_bounds(center_lat, center_lon, radius)
        
        print(f"\\n🔍 Analyzing location: {location_name}")
        print(f"📍 Coordinates: {center_lat:.4f}°N, {abs(center_lon):.4f}°W")
        print(f"📏 Radius: {radius}° (~{radius * 111:.1f} km)")
        print(f"🧪 Gases: {gases}")
        
        # Analyze each gas
        gas_data = {}
        all_hotspots = []
        all_regional_alerts = []
        data_availability = {}
        
        for gas in gases:
            print(f"\\n--- Analyzing {gas} ---")
            
            try:
                # Fetch data
                data_file = self.fetch_tempo_data(gas, spatial_bounds, start_time, end_time)
                
                if data_file and os.path.exists(data_file):
                    # Load and process data
                    datatree = xr.open_datatree(data_file)
                    variable_name = self.VARIABLE_NAMES[gas]
                    
                    da = datatree[variable_name]
                    lons = datatree["geolocation/longitude"].values
                    lats = datatree["geolocation/latitude"].values
                    quality_flag = datatree["product/main_data_quality_flag"].values
                    
                    # Filter by quality flag
                    good_data = da.where(quality_flag == 0).squeeze()
                    
                    # Detect hotspots
                    hotspots = self.detect_hotspots(good_data.values, lats, lons, gas)
                    all_hotspots.extend(hotspots)
                    
                    # Check regional alerts
                    regional_alerts = self.check_regional_alerts(
                        good_data.values, lats, lons, center_lat, center_lon, 
                        radius, gas, location_name
                    )
                    all_regional_alerts.extend(regional_alerts)
                    
                    gas_data[gas] = {
                        'datatree': datatree,
                        'data': good_data,
                        'hotspots': hotspots,
                        'alerts': regional_alerts
                    }
                    
                    data_availability[gas] = True
                    print(f"✅ {gas} analysis complete: {len(hotspots)} hotspots, {len(regional_alerts)} alerts")
                    
                else:
                    gas_data[gas] = {
                        'datatree': None,
                        'data': None,
                        'hotspots': [],
                        'alerts': []
                    }
                    data_availability[gas] = False
                    print(f"❌ No {gas} data available")
                    
            except Exception as e:
                print(f"❌ Error analyzing {gas}: {str(e)}")
                gas_data[gas] = {
                    'datatree': None,
                    'data': None,
                    'hotspots': [],
                    'alerts': []
                }
                data_availability[gas] = False
        
        # Create visualization
        map_image_path = None
        try:
            map_image_path = self.create_visualization(
                gas_data, location_name, center_lat, center_lon, radius
            )
            print(f"\\n📈 Visualization saved: {map_image_path}")
        except Exception as e:
            print(f"❌ Visualization error: {str(e)}")
        
        # Determine overall status
        max_severity = 0
        if all_regional_alerts:
            max_severity = max(alert['severity'] for alert in all_regional_alerts)
        
        severity_to_status = {
            0: 'Good',
            1: 'Moderate',
            2: 'Unhealthy for Sensitive Groups',
            3: 'Very Unhealthy',
            4: 'Hazardous'
        }
        overall_status = severity_to_status.get(max_severity, 'Good')
        
        # Generate health recommendations
        health_recommendations = self.generate_health_recommendations(max_severity)
        
        return {
            'location': location_name,
            'coordinates': {'latitude': center_lat, 'longitude': center_lon},
            'timestamp': dt.datetime.now(),
            'gases_analyzed': gases,
            'regional_alerts': all_regional_alerts,
            'hotspots': all_hotspots,
            'overall_status': overall_status,
            'health_recommendations': health_recommendations,
            'data_availability': data_availability,
            'map_image_path': map_image_path
        }
    
    def generate_health_recommendations(self, max_severity: int) -> List[str]:
        """Generate health recommendations based on pollution severity"""
        recommendations = {
            0: ["Air quality is satisfactory", "Outdoor activities are safe for all groups"],
            1: ["Unusually sensitive people should consider limiting prolonged outdoor exertion",
                "Most people can engage in outdoor activities normally"],
            2: ["Sensitive groups should reduce prolonged or heavy outdoor exertion",
                "Children, elderly, and people with respiratory conditions should be cautious"],
            3: ["Everyone should reduce prolonged or heavy outdoor exertion",
                "Sensitive groups should avoid outdoor activities",
                "Consider wearing masks when outside"],
            4: ["Everyone should avoid all outdoor physical activity",
                "Stay indoors with windows and doors closed",
                "Use air purifiers if available",
                "Seek medical attention if experiencing symptoms"]
        }
        
        return recommendations.get(max_severity, recommendations[0])


# For testing purposes - keeping the original functionality for Madre Wildfire
def test_madre_wildfire():
    """Test function using the original Madre Wildfire setup"""
    analyzer = TempoMultiGasAnalyzer()
    
    result = analyzer.analyze_location(
        location_name="Madre Wildfire Region - New Cuyama, California",
        radius=0.3,
        gases=['NO2'],  # Start with just NO2 for testing
        start_time=dt.datetime(2025, 7, 3, 20, 0, 0),
        end_time=dt.datetime(2025, 7, 3, 20, 15, 0)
    )
    
    print("\\n" + "="*80)
    print("🔥 MULTI-GAS POLLUTION ANALYSIS RESULTS 🔥")
    print("="*80)
    
    print(f"\\n📍 Location: {result['location']}")
    print(f"📊 Overall Status: {result['overall_status']}")
    print(f"🧪 Gases Analyzed: {result['gases_analyzed']}")
    print(f"📅 Analysis Time: {result['timestamp']}")
    
    print(f"\\n🚨 Regional Alerts: {len(result['regional_alerts'])}")
    for alert in result['regional_alerts']:
        print(f"   {alert['gas']}: {alert['level']} (Max: {alert['max_value']:.2e})")
    
    print(f"\\n🔥 Hotspots Detected: {len(result['hotspots'])}")
    for i, hotspot in enumerate(result['hotspots'][:5]):
        print(f"   #{i+1} {hotspot['gas']}: {hotspot['level']} "
              f"({hotspot['area_km2']:.1f} km²)")
    
    print(f"\\n💡 Health Recommendations:")
    for rec in result['health_recommendations']:
        print(f"   • {rec}")
    
    return result


if __name__ == "__main__":
    # Run test
    test_madre_wildfire()