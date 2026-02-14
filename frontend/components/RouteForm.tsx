"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { routeAnalyze, type RouteAnalyzeParams } from "@/lib/api";

export default function RouteForm() {
  const router = useRouter();
  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");
  const [gases, setGases] = useState("NO2");
  const [gridStepKm, setGridStepKm] = useState("20");
  const [useOptimized, setUseOptimized] = useState(false);
  const [routeMode, setRouteMode] = useState("commute");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    const params: RouteAnalyzeParams = {
      origin: origin.trim(),
      destination: destination.trim(),
      gases,
      grid_step_km: parseInt(gridStepKm, 10) || 20,
      use_optimized: useOptimized,
      route_mode: routeMode,
    };
    try {
      const result = await routeAnalyze(params);
      router.push(
        `/route?${new URLSearchParams({
          origin: params.origin,
          destination: params.destination,
          gases: params.gases ?? "NO2",
          grid_step_km: String(params.grid_step_km),
          use_optimized: String(useOptimized),
          route_mode: routeMode,
        })}`
      );
      sessionStorage.setItem("routeResult", JSON.stringify(result));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Route analysis failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="panel max-w-[980px] mt-8 space-y-4"
    >
      <h2 className="text-xl font-semibold border-b border-[#333] pb-2">
        Route Air Safety (Beta)
      </h2>
      {error && <div className="error">{error}</div>}

      <div>
        <label htmlFor="origin" className="block font-semibold mb-1">
          Origin (Location)
        </label>
        <input
          type="text"
          id="origin"
          value={origin}
          onChange={(e) => setOrigin(e.target.value)}
          placeholder="e.g., San Francisco, CA OR 34.9000, -119.7000"
          required
          className="rounded"
        />
        <p className="text-xs text-[#888] mt-1">
          You can enter a place name or coordinates as &quot;lat, lon&quot;.
        </p>
      </div>

      <div>
        <label htmlFor="destination" className="block font-semibold mb-1">
          Destination (Location)
        </label>
        <input
          type="text"
          id="destination"
          value={destination}
          onChange={(e) => setDestination(e.target.value)}
          placeholder="e.g., Los Angeles, CA OR 34.9000, -119.7000"
          required
          className="rounded"
        />
        <p className="text-xs text-[#888] mt-1">
          Tip: For wildfire areas, coordinates work best.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label htmlFor="route_gases" className="block font-semibold mb-1">
            Gases (Comma-separated)
          </label>
          <input
            type="text"
            id="route_gases"
            value={gases}
            onChange={(e) => setGases(e.target.value)}
            className="rounded"
          />
          <p className="text-xs text-[#888] mt-1">
            Used to score air quality along the path.
          </p>
        </div>
        <div>
          <label htmlFor="grid_step_km" className="block font-semibold mb-1">
            Grid-step (km)
          </label>
          <input
            type="number"
            id="grid_step_km"
            step={1}
            value={gridStepKm}
            onChange={(e) => setGridStepKm(e.target.value)}
            className="rounded"
          />
          <p className="text-xs text-[#888] mt-1">
            Smaller = slower, more precise.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="flex items-center gap-2 font-semibold">
            <input
              type="checkbox"
              checked={useOptimized}
              onChange={(e) => setUseOptimized(e.target.checked)}
              className="rounded"
            />
            Use pollution-optimized route (UPES + OSM)
          </label>
          <p className="text-xs text-[#888] mt-1">
            Fetches OSM road network and minimizes exposure.
          </p>
        </div>
        <div>
          <label htmlFor="route_mode" className="block font-semibold mb-1">
            Mode
          </label>
          <select
            id="route_mode"
            value={routeMode}
            onChange={(e) => setRouteMode(e.target.value)}
            className="rounded bg-[#1a1a1a] text-[#fafafa] border border-[#333]"
          >
            <option value="commute">Commute</option>
            <option value="jogger">Jogger</option>
            <option value="cyclist">Cyclist</option>
          </select>
          <p className="text-xs text-[#888] mt-1">
            Affects road preferences (e.g. cycleways for cyclist).
          </p>
        </div>
      </div>

      <button type="submit" disabled={loading} className="rounded">
        {loading ? "Analyzing route…" : "Analyze Route"}
      </button>
    </form>
  );
}
