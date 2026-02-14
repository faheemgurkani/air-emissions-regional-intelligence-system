"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { analyzeFull, type AnalyzeParams } from "@/lib/api";

export default function AnalyzeForm() {
  const router = useRouter();
  const [location, setLocation] = useState("");
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [radius, setRadius] = useState("0.3");
  const [gases, setGases] = useState("NO2");
  const [useAllGases, setUseAllGases] = useState(false);
  const [includeWeather, setIncludeWeather] = useState(true);
  const [includePrediction, setIncludePrediction] = useState(true);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    const params: AnalyzeParams = {
      location: location || undefined,
      latitude: latitude || undefined,
      longitude: longitude || undefined,
      radius: parseFloat(radius) || 0.3,
      gases: useAllGases ? "NO2, CH2O, AI, PM, O3" : gases,
      include_weather: includeWeather,
      include_pollutant_prediction: includePrediction,
    };
    try {
      await analyzeFull(params);
      const query = new URLSearchParams({
        location: params.location || "",
        lat: String(params.latitude ?? ""),
        lon: String(params.longitude ?? ""),
        radius: String(params.radius),
        gases: params.gases ?? "NO2",
        include_weather: String(includeWeather),
        include_pollutant_prediction: String(includePrediction),
      });
      router.push(`/results?${query}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="panel max-w-[980px] space-y-4"
    >
      <h2 className="text-xl font-semibold border-b border-[#333] pb-2">
        TEMPO Pollution Viewer and Weather Based Dispersion Modelling
      </h2>
      {error && <div className="error">{error}</div>}

      <div>
        <label htmlFor="location" className="block font-semibold mb-1">
          Location Name (Optional)
        </label>
        <input
          type="text"
          id="location"
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          placeholder="e.g., New York City"
          className="rounded"
        />
        <p className="text-xs text-[#888] mt-1">
          If provided, we will geocode to coordinates using geopy.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label htmlFor="latitude" className="block font-semibold mb-1">
            Latitude (Optional)
          </label>
          <input
            type="text"
            id="latitude"
            value={latitude}
            onChange={(e) => setLatitude(e.target.value)}
            placeholder="e.g., 40.7128"
            className="rounded"
          />
        </div>
        <div>
          <label htmlFor="longitude" className="block font-semibold mb-1">
            Longitude (Optional)
          </label>
          <input
            type="text"
            id="longitude"
            value={longitude}
            onChange={(e) => setLongitude(e.target.value)}
            placeholder="e.g., -74.0060"
            className="rounded"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label htmlFor="radius" className="block font-semibold mb-1">
            Radius (Degrees)
          </label>
          <input
            type="number"
            id="radius"
            step="0.01"
            value={radius}
            onChange={(e) => setRadius(e.target.value)}
            className="rounded"
          />
        </div>
        <div>
          <label htmlFor="gases" className="block font-semibold mb-1">
            Gases (Comma-separated)
          </label>
          <input
            type="text"
            id="gases"
            value={gases}
            onChange={(e) => setGases(e.target.value)}
            disabled={useAllGases}
            className="rounded disabled:opacity-60"
          />
          <label className="inline-flex items-center gap-2 mt-2 text-sm">
            <input
              type="checkbox"
              checked={useAllGases}
              onChange={(e) => {
                setUseAllGases(e.target.checked);
                if (e.target.checked) setGases("NO2, CH2O, AI, PM, O3");
              }}
              className="rounded"
            />
            Use all (NO2, CH2O, AI, PM, O3)
          </label>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="flex items-center gap-2 font-semibold">
            <input
              type="checkbox"
              checked={includeWeather}
              onChange={(e) => setIncludeWeather(e.target.checked)}
              className="rounded"
            />
            Include Weather Data
          </label>
          <p className="text-xs text-[#888] mt-1">
            Get real-time weather conditions and forecasts
          </p>
        </div>
        <div>
          <label className="flex items-center gap-2 font-semibold">
            <input
              type="checkbox"
              checked={includePrediction}
              onChange={(e) => setIncludePrediction(e.target.checked)}
              className="rounded"
            />
            Include Pollutant Movement Prediction
          </label>
          <p className="text-xs text-[#888] mt-1">
            Predict pollutant dispersion for next 3 hours
          </p>
        </div>
      </div>

      <button type="submit" disabled={loading} className="rounded">
        {loading ? "Analyzing…" : "Analyze Modelling"}
      </button>
    </form>
  );
}
