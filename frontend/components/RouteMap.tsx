"use client";

import { useEffect, useRef, useState } from "react";
import type { RouteResult } from "@/lib/api";

const severityToColor = (sev: number): string => {
  switch (sev) {
    case 0: return "#2ECC71";
    case 1: return "#F1C40F";
    case 2: return "#E67E22";
    case 3: return "#E74C3C";
    case 4: return "#8E44AD";
    default: return "#95A5A6";
  }
};

const colorMapHS: Record<string, string> = {
  moderate: "#F1C40F",
  unhealthy: "#E67E22",
  very_unhealthy: "#E74C3C",
  hazardous: "#8E44AD",
};

interface RouteMapProps {
  data: RouteResult;
}

export default function RouteMap({ data }: RouteMapProps) {
  const { origin, dest, routes, hotspots_geojson } = data;
  const containerRef = useRef<HTMLDivElement>(null);
  const cleanupRef = useRef<(() => void) | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || !containerRef.current) return;
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted || !containerRef.current || typeof window === "undefined") return;

    const loadLeaflet = async () => {
      const L = (await import("leaflet")).default;
      await import("leaflet/dist/leaflet.css");

      if (!containerRef.current) return;

      const originLatLng: [number, number] = [origin.lat, origin.lon];
      const destLatLng: [number, number] = [dest.lat, dest.lon];

      const map = L.map(containerRef.current).setView(originLatLng, 6);
      L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
        maxZoom: 18,
        attribution: "&copy; OpenStreetMap contributors &copy; CARTO",
      }).addTo(map);

      L.marker(originLatLng).addTo(map).bindPopup("Origin");
      L.marker(destLatLng).addTo(map).bindPopup("Destination");

      const boundsPoints: [number, number][] = [originLatLng, destLatLng];

      if (routes && routes.length > 0) {
        routes.forEach((r) => {
          const coords = r.coords || [];
          const sev = r.severity || [];
          for (let i = 1; i < coords.length; i++) {
            const a = coords[i - 1];
            const b = coords[i];
            const s = Math.max(0, Math.min(4, sev[i - 1] ?? 0));
            const color = severityToColor(s);
            const weight = r.safest ? 6 : 4;
            L.polyline([a as [number, number], b as [number, number]], {
              color,
              weight,
              opacity: 0.95,
            }).addTo(map);
          }
          boundsPoints.push(...coords);
        });
        map.fitBounds(L.latLngBounds(boundsPoints as L.LatLngExpression[]));
      } else {
        map.fitBounds(L.latLngBounds([originLatLng, destLatLng]));
      }

      const hs = hotspots_geojson;
      if (hs?.features) {
        (hs.features as Array<{ geometry?: { type: string; coordinates: number[] }; properties?: { level?: string; gas?: string; radius_km?: number; place?: string } }>).forEach((f) => {
          if (!f?.geometry || f.geometry.type !== "Point") return;
          const p = f.properties || {};
          const color = colorMapHS[p.level || ""] || "#F1C40F";
          const lat = f.geometry.coordinates[1];
          const lon = f.geometry.coordinates[0];
          const rMeters = (p.radius_km || 5) * 1000;
          L.circle([lat, lon], {
            radius: rMeters,
            color,
            fillColor: color,
            fillOpacity: 0.25,
            weight: 1,
          })
            .addTo(map)
            .bindPopup(
              `${p.gas} hotspot (${p.level})${p.place ? "<br><em>" + p.place + "</em>" : ""}`
            );
        });
      }

      cleanupRef.current = () => {
        map.remove();
      };
    };

    loadLeaflet();
    return () => {
      if (cleanupRef.current) {
        cleanupRef.current();
        cleanupRef.current = null;
      }
    };
  }, [mounted, origin.lat, origin.lon, dest.lat, dest.lon, routes, hotspots_geojson]);

  return (
    <div className="w-full h-[520px] border border-[#333] rounded mt-2" ref={containerRef} style={{ minHeight: 520 }} />
  );
}
