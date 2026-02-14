"use client";

import { useEffect, useRef, useState } from "react";
import { getHotspots } from "@/lib/api";

interface ResultMapProps {
  center: [number, number];
  radius: number;
  gases: string;
  location: string;
}

function colorForLevel(level: string): string {
  switch (level) {
    case "hazardous": return "#8E44AD";
    case "very_unhealthy": return "#E74C3C";
    case "unhealthy": return "#E67E22";
    case "moderate": return "#F1C40F";
    default: return "#2ECC71";
  }
}

export default function ResultMap({ center, radius, gases, location }: ResultMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<{ map: L.Map; layer: L.GeoJSON; circle: L.Circle; marker: L.Marker } | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || !containerRef.current) return;
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted || !containerRef.current || typeof window === "undefined") return;

    let intervalId: ReturnType<typeof setInterval> | null = null;
    let cancelled = false;

    const loadLeaflet = async () => {
      const L = (await import("leaflet")).default;
      await import("leaflet/dist/leaflet.css");

      if (cancelled || !containerRef.current) return;
      const map = L.map(containerRef.current).setView(center, 9);
      L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
        maxZoom: 18,
        attribution: "&copy; OpenStreetMap contributors &copy; CARTO",
      }).addTo(map);

      const hotspotLayer = L.geoJSON(undefined as unknown as GeoJSON.GeoJsonObject, {
        pointToLayer(feature, latlng) {
          const p = (feature.properties || {}) as { level?: string; radius_km?: number };
          const color = colorForLevel(p.level || "");
          const radiusMeters = (p.radius_km || 5) * 1000;
          return L.circle(latlng, {
            radius: radiusMeters,
            color,
            fillColor: color,
            fillOpacity: 0.25,
            weight: 1,
          });
        },
        onEachFeature(feature, layer) {
          const p = (feature.properties || {}) as { gas?: string; level?: string; max_value?: number; mean_value?: number; area_km2?: number };
          const maxv = p.max_value != null ? Number(p.max_value).toExponential(2) : "n/a";
          const meanv = p.mean_value != null ? Number(p.mean_value).toExponential(2) : "n/a";
          layer.bindPopup(
            `<b>${p.gas}</b><br>Level: ${p.level}<br>Max: ${maxv}<br>Mean: ${meanv}<br>Area: ${p.area_km2?.toFixed(1) ?? ""} km²`
          );
        },
      }).addTo(map);

      L.marker(center).addTo(map).bindPopup(`Center: ${location}`);
      L.circle(center, {
        radius: radius * 111000,
        color: "#fff",
        fill: false,
        weight: 1,
        dashArray: "5,5",
      }).addTo(map);

      mapRef.current = { map, layer: hotspotLayer, circle: null as unknown as L.Circle, marker: null as unknown as L.Marker };

      const refresh = async () => {
        try {
          const geojson = await getHotspots({
            location: location || undefined,
            latitude: center[0],
            longitude: center[1],
            radius,
            gases,
          });
          if (mapRef.current) {
            mapRef.current.layer.clearLayers();
            mapRef.current.layer.addData(geojson as GeoJSON.GeoJsonObject);
          }
        } catch {
          // ignore
        }
      };
      refresh();
      if (!cancelled) intervalId = setInterval(refresh, 10000);
    };

    loadLeaflet();

    return () => {
      cancelled = true;
      if (intervalId) clearInterval(intervalId);
      if (mapRef.current) {
        mapRef.current.map.remove();
        mapRef.current = null;
      }
    };
  }, [mounted, center[0], center[1], radius, gases, location]);

  return (
    <div className="panel mt-4">
      <h3 className="font-semibold mb-2">Realtime Hotspots Map</h3>
      <div
        ref={containerRef}
        className="w-full h-[420px] border border-[#333] rounded"
        style={{ minHeight: 420 }}
      />
    </div>
  );
}
