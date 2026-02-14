"use client";

import Link from "next/link";
import { imageUrl } from "@/lib/api";
import type { AnalyzeResult } from "@/lib/api";

export default function ResultContent({ data }: { data: AnalyzeResult }) {
  const {
    location,
    coords,
    radius,
    gases,
    overall_status,
    alerts,
    hotspots,
    units,
    image_url,
    per_gas_images,
    weather_data,
    pollutant_predictions,
    weather_interpretation,
    prediction_interpretation,
  } = data;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold border-b border-[#333] pb-2">
        Results — TEMPO Pollution Viewer
      </h1>

      <div className="panel">
        <div><strong>Location:</strong> {location} <span className="text-sm text-[#888]">({coords.lat}, {coords.lon})</span></div>
        <div><strong>Radius:</strong> {radius}°</div>
        <div><strong>Gases:</strong> {gases.join(", ")}</div>
        <div><strong>Overall status:</strong> {overall_status}</div>
        {weather_data && (
          <div className="mt-2">
            <strong>Weather:</strong> {weather_data.current.temp_c}°C ({weather_data.current.temp_f}°F), {weather_data.current.condition.text}, Wind: {weather_data.current.wind_kph} km/h ({weather_data.current.wind_mph} mph) from {weather_data.current.wind_dir}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 panel">
          {image_url ? (
            <img
              src={imageUrl(image_url)}
              alt="Analysis plot"
              className="w-full border border-[#333]"
            />
          ) : (
            <div>No image available.</div>
          )}

          {per_gas_images && per_gas_images.length > 0 && (
            <div className="mt-4">
              <h3 className="font-semibold mb-2">Per-gas Tripanel Figures</h3>
              {per_gas_images.map((pg) => (
                <div key={pg.gas} className="mb-4 border border-[#333] p-2 rounded">
                  <div className="font-semibold">{pg.gas}</div>
                  <img
                    src={imageUrl(pg.url)}
                    alt={`${pg.gas} tripanel`}
                    className="w-full border border-[#333] mt-2"
                  />
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="panel space-y-4">
          <div>
            <h3 className="font-semibold mb-2">Regional Alerts</h3>
            {alerts && alerts.length > 0 ? (
              <table className="text-sm">
                <thead>
                  <tr>
                    <th>Gas</th>
                    <th>Level</th>
                    <th>Max</th>
                    <th>Mean</th>
                    <th>N</th>
                  </tr>
                </thead>
                <tbody>
                  {alerts.map((a, i) => (
                    <tr key={i}>
                      <td>{a.gas}</td>
                      <td>{a.level}</td>
                      <td>{typeof a.max_value === "number" ? a.max_value.toExponential(2) : a.max_value} {units[a.gas]}</td>
                      <td>{typeof a.mean_value === "number" ? a.mean_value.toExponential(2) : a.mean_value} {units[a.gas]}</td>
                      <td>{(a as { num_pixels?: number }).num_pixels ?? "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div>No alerts.</div>
            )}
          </div>

          <div>
            <h3 className="font-semibold mb-2">Top Hotspots</h3>
            {hotspots && hotspots.length > 0 ? (
              <table className="text-sm">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Gas</th>
                    <th>Level</th>
                    <th>Center</th>
                    <th>Area (km²)</th>
                    <th>Max</th>
                    <th>Place</th>
                  </tr>
                </thead>
                <tbody>
                  {hotspots.map((h, i) => (
                    <tr key={i}>
                      <td>{i + 1}</td>
                      <td>{h.gas}</td>
                      <td>{h.level}</td>
                      <td>{h.center_lat.toFixed(4)}, {h.center_lon.toFixed(4)}</td>
                      <td>{h.area_km2.toFixed(1)}</td>
                      <td>{typeof h.max_value === "number" ? h.max_value.toExponential(2) : h.max_value} {units[h.gas]}</td>
                      <td>{h.place ?? "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div>No hotspots detected.</div>
            )}
          </div>
        </div>
      </div>

      {weather_data && (
        <div className="panel">
          <h3 className="font-semibold mb-2">
            Current Weather Conditions for {weather_data.location.name}
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
            <div>
              <h4 className="font-medium mb-2">Current Conditions</h4>
              <table className="text-sm w-full">
                <tbody>
                  <tr><td className="font-medium">Temperature:</td><td>{weather_data.current.temp_c}°C ({weather_data.current.temp_f}°F)</td></tr>
                  <tr><td className="font-medium">Humidity:</td><td>{weather_data.current.humidity}%</td></tr>
                  <tr><td className="font-medium">Wind Speed:</td><td>{weather_data.current.wind_kph} km/h</td></tr>
                  <tr><td className="font-medium">Wind Direction:</td><td>{weather_data.current.wind_degree}° ({weather_data.current.wind_dir})</td></tr>
                  <tr><td className="font-medium">Condition:</td><td>{weather_data.current.condition.text}</td></tr>
                  <tr><td className="font-medium">Visibility:</td><td>{weather_data.current.vis_km} km</td></tr>
                </tbody>
              </table>
            </div>
            {weather_data.air_quality && (
              <div>
                <h4 className="font-medium mb-2">Air Quality Index</h4>
                <table className="text-sm w-full">
                  <tbody>
                    {Object.entries(weather_data.air_quality).map(([k, v]) => (
                      <tr key={k}><td className="font-medium">{k}:</td><td>{String(v)}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
          {weather_interpretation && (
            <div className="border-l-4 border-[#333] pl-4 py-2 bg-[#111]">
              <h4 className="font-medium mb-1">Current Weather and Air Quality Assessment</h4>
              <div className="whitespace-pre-line text-sm">{weather_interpretation}</div>
            </div>
          )}
        </div>
      )}

      {pollutant_predictions && pollutant_predictions.length > 0 && (
        <div className="panel">
          <h3 className="font-semibold mb-2">Pollutant Movement Prediction (Next 3 Hours)</h3>
          <div className="space-y-4">
            {pollutant_predictions.map((pred, i) => (
              <div key={i} className="border border-[#333] p-4 rounded bg-[#111]">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-2">
                  <div><strong>Time:</strong><br />{pred.time}</div>
                  <div><strong>Wind:</strong><br />{pred.wind_kph} km/h ({pred.wind_dir_deg}°)</div>
                  <div><strong>Movement:</strong><br />{pred.displacement_km.dx.toFixed(1)} km E/W, {pred.displacement_km.dy.toFixed(1)} km N/S</div>
                </div>
                <div>
                  <strong>Predicted Air Quality:</strong>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-2">
                    {Object.entries(pred.predicted_air_quality).map(([pollutant, value]) => (
                      <div key={pollutant} className="border border-[#333] p-2 text-center text-sm">
                        <strong>{pollutant}</strong><br />{typeof value === "number" ? value.toFixed(1) : value} μg/m³
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
          {prediction_interpretation && (
            <div className="border-l-4 border-[#333] pl-4 py-2 mt-4 bg-[#111]">
              <h4 className="font-medium mb-1">Pollutant Movement Prediction (Next 3 Hours)</h4>
              <div className="whitespace-pre-line text-sm">{prediction_interpretation}</div>
            </div>
          )}
        </div>
      )}

      <div className="flex gap-2">
        <Link href="/" className="button rounded inline-block">
          Back
        </Link>
      </div>
    </div>
  );
}
