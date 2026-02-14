"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Suspense } from "react";
import Link from "next/link";
import { routeAnalyze } from "@/lib/api";
import type { RouteResult } from "@/lib/api";
import RouteMap from "@/components/RouteMap";
import RouteList from "@/components/RouteList";

function RouteInner() {
  const searchParams = useSearchParams();
  const [data, setData] = useState<RouteResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const stored = typeof window !== "undefined" ? sessionStorage.getItem("routeResult") : null;
    if (stored) {
      try {
        const parsed = JSON.parse(stored) as RouteResult;
        setData(parsed);
        setLoading(false);
        return;
      } catch {
        // fall through to fetch
      }
    }

    const origin = searchParams.get("origin") ?? "";
    const destination = searchParams.get("destination") ?? "";
    const gases = searchParams.get("gases") ?? "NO2,AI";
    const grid_step_km = searchParams.get("grid_step_km") ?? "20";
    const use_optimized = searchParams.get("use_optimized") === "true";
    const route_mode = searchParams.get("route_mode") ?? "commute";

    if (!origin || !destination) {
      setError("Missing origin or destination. Go back and submit a route.");
      setLoading(false);
      return;
    }

    routeAnalyze({
      origin,
      destination,
      gases,
      grid_step_km: parseInt(grid_step_km, 10) || 20,
      use_optimized,
      route_mode,
    })
      .then((result) => {
        setData(result);
        if (typeof window !== "undefined") {
          sessionStorage.setItem("routeResult", JSON.stringify(result));
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Route analysis failed"))
      .finally(() => setLoading(false));
  }, [searchParams]);

  if (loading) {
    return (
      <div className="panel text-center py-12">
        Loading route analysis…
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="space-y-4">
        <div className="error">{error || "No data"}</div>
        <Link href="/" className="button rounded inline-block">Back</Link>
      </div>
    );
  }

  const originName = encodeURIComponent(data.origin_name);
  const destName = encodeURIComponent(data.dest_name);
  const gasesParam = data.gases.join(",");
  const altUrl = `/route?origin=${originName}&destination=${destName}&gases=${encodeURIComponent(gasesParam)}&grid_step_km=${data.grid_step_km}`;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold border-b border-[#333] pb-2">
        Route Air Safety
      </h1>

      <div className="panel">
        <div><strong>Origin:</strong> {data.origin_name} ({data.origin.lat}, {data.origin.lon})</div>
        <div><strong>Destination:</strong> {data.dest_name} ({data.dest.lat}, {data.dest.lon})</div>
        <div><strong>Gases:</strong> {data.gases.join(", ")}</div>
        <div><strong>Route status:</strong> {data.status_text}</div>
      </div>

      <RouteMap data={data} />
      <RouteList data={data} />

      <div className="flex gap-2 mt-4">
        <Link href="/" className="button rounded inline-block">Back</Link>
        {data.alt_available && (
          <Link href={altUrl} className="button rounded inline-block">Find Alternate Route</Link>
        )}
      </div>
    </div>
  );
}

export default function RoutePage() {
  return (
    <Suspense fallback={<div className="panel text-center py-12">Loading…</div>}>
      <RouteInner />
    </Suspense>
  );
}
