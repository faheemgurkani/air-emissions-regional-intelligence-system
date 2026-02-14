"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Suspense } from "react";
import { analyzeFull } from "@/lib/api";
import type { AnalyzeResult } from "@/lib/api";
import ResultContent from "@/components/ResultContent";
import ResultMap from "@/components/ResultMap";

function ResultsInner() {
  const searchParams = useSearchParams();
  const [data, setData] = useState<AnalyzeResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const location = searchParams.get("location") ?? "";
    const lat = searchParams.get("lat") ?? "";
    const lon = searchParams.get("lon") ?? "";
    const radius = searchParams.get("radius") ?? "0.3";
    const gases = searchParams.get("gases") ?? "NO2";
    const includeWeather = searchParams.get("include_weather") !== "false";
    const includePrediction = searchParams.get("include_pollutant_prediction") !== "false";

    if (!lat && !lon && !location) {
      setError("Missing location or coordinates. Go back and submit an analysis.");
      setLoading(false);
      return;
    }

    analyzeFull({
      location: location || undefined,
      latitude: lat || undefined,
      longitude: lon || undefined,
      radius: parseFloat(radius) || 0.3,
      gases,
      include_weather: includeWeather,
      include_pollutant_prediction: includePrediction,
    })
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "Analysis failed"))
      .finally(() => setLoading(false));
  }, [searchParams]);

  if (loading) {
    return (
      <div className="panel text-center py-12">
        Loading analysis…
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="space-y-4">
        <div className="error">{error || "No data"}</div>
        <a href="/" className="button rounded inline-block">Back</a>
      </div>
    );
  }

  return (
    <>
      <ResultContent data={data} />
      <ResultMap
        center={[data.coords.lat, data.coords.lon]}
        radius={data.radius}
        gases={data.gases.join(",")}
        location={data.location}
      />
    </>
  );
}

export default function ResultsPage() {
  return (
    <Suspense fallback={<div className="panel text-center py-12">Loading…</div>}>
      <ResultsInner />
    </Suspense>
  );
}
