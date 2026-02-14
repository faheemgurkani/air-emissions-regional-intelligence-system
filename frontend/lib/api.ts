const getBaseUrl = () =>
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface AnalyzeParams {
  location?: string;
  latitude?: string;
  longitude?: string;
  radius?: number;
  gases?: string;
  include_weather?: boolean;
  include_pollutant_prediction?: boolean;
}

export interface AnalyzeResult {
  location: string;
  coords: { lat: number; lon: number };
  radius: number;
  gases: string[];
  overall_status: string;
  alerts: Array<{
    gas: string;
    level: string;
    max_value: number;
    mean_value: number;
    num_pixels: number;
    severity: number;
  }>;
  hotspots: Array<{
    gas: string;
    level: string;
    center_lat: number;
    center_lon: number;
    area_km2: number;
    max_value: number;
    mean_value: number;
    place?: string;
  }>;
  units: Record<string, string>;
  image_url: string;
  per_gas_images: Array<{ gas: string; url: string }>;
  weather_data?: {
    location: { name: string };
    current: {
      temp_c: number;
      temp_f: number;
      condition: { text: string };
      wind_kph: number;
      wind_mph: number;
      wind_dir: string;
      wind_degree: number;
      humidity: number;
      vis_km: number;
    };
    air_quality?: Record<string, number | string>;
  };
  pollutant_predictions?: Array<{
    time: string;
    wind_kph: number;
    wind_dir_deg: number;
    displacement_km: { dx: number; dy: number };
    predicted_air_quality: Record<string, number>;
  }>;
  weather_interpretation?: string;
  prediction_interpretation?: string;
}

export interface RouteAnalyzeParams {
  origin: string;
  destination: string;
  gases?: string;
  grid_step_km?: number;
  use_optimized?: boolean;
  route_mode?: string;
}

export interface RouteResult {
  origin_name: string;
  dest_name: string;
  origin: { lat: number; lon: number };
  dest: { lat: number; lon: number };
  gases: string[];
  status_text: string;
  routes: Array<{
    name: string;
    coords: [number, number][];
    severity?: number[];
    score: number;
    distance_km: number;
    duration_min?: number;
    safest?: boolean;
    blocked?: boolean;
  }>;
  hotspots_geojson: { type: string; features: unknown[] };
  grid_step_km: number;
  alt_available: boolean;
}

export async function analyzeFull(
  params: AnalyzeParams
): Promise<AnalyzeResult> {
  const form = new FormData();
  if (params.location) form.set("location", params.location);
  if (params.latitude) form.set("latitude", params.latitude);
  if (params.longitude) form.set("longitude", params.longitude);
  form.set("radius", String(params.radius ?? 0.3));
  form.set("gases", params.gases ?? "NO2");
  form.set(
    "include_weather",
    params.include_weather !== false ? "true" : "false"
  );
  form.set(
    "include_pollutant_prediction",
    params.include_pollutant_prediction !== false ? "true" : "false"
  );

  const res = await fetch(`${getBaseUrl()}/api/analyze`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { error?: string }).error || res.statusText);
  }
  return res.json();
}

export async function routeAnalyze(
  params: RouteAnalyzeParams
): Promise<RouteResult> {
  const form = new FormData();
  form.set("origin", params.origin);
  form.set("destination", params.destination);
  form.set("gases", params.gases ?? "NO2,AI");
  form.set("grid_step_km", String(params.grid_step_km ?? 20));
  form.set("use_optimized", params.use_optimized ? "true" : "false");
  form.set("route_mode", params.route_mode ?? "commute");

  const res = await fetch(`${getBaseUrl()}/api/route/analyze`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { error?: string }).error || res.statusText);
  }
  return res.json();
}

export async function getHotspots(params: {
  location?: string;
  latitude?: number;
  longitude?: number;
  radius?: number;
  gases?: string;
}): Promise<{ type: string; features: unknown[] }> {
  const search = new URLSearchParams();
  if (params.location) search.set("location", params.location);
  if (params.latitude != null) search.set("latitude", String(params.latitude));
  if (params.longitude != null)
    search.set("longitude", String(params.longitude));
  search.set("radius", String(params.radius ?? 0.3));
  search.set("gases", params.gases ?? "NO2");

  const res = await fetch(`${getBaseUrl()}/api/hotspots?${search}`);
  if (!res.ok) return { type: "FeatureCollection", features: [] };
  return res.json();
}

export function imageUrl(path: string): string {
  if (!path) return "";
  if (path.startsWith("http")) return path;
  return `${getBaseUrl()}${path.startsWith("/") ? "" : "/"}${path}`;
}
