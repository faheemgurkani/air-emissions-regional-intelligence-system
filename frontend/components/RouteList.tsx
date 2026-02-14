"use client";

import type { RouteResult } from "@/lib/api";

export default function RouteList({ data }: { data: RouteResult }) {
  const { routes, status_text } = data;

  return (
    <div className="panel mt-4">
      <div className="font-semibold mb-2">Routes</div>
      <div className="text-sm space-y-1">
        {routes.map((r, i) => {
          const dist = r.distance_km != null ? `${r.distance_km.toFixed(1)} km` : "N/A";
          return (
            <div key={i}>
              {r.name}{r.safest ? " (safest)" : ""} — Score: {r.score.toFixed(0)} — Distance: {dist}
              {r.blocked ? " — near high pollution" : ""}
            </div>
          );
        })}
      </div>
      <div className="mt-2 text-sm text-[#888]">{status_text}</div>
    </div>
  );
}
