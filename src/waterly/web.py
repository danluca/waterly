import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from .config import HTTP_HOST, HTTP_PORT, ZONES
from .storage import settings_store, trends_store
from .weather import WeatherService
from .pulses import PulseCounter

DASHBOARD_HTML = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Garden Watering</title>
  <style>
    body { font-family: sans-serif; max-width: 900px; margin: auto; padding: 20px; }
    h1 { margin-bottom: 0; }
    small { color: #666; }
    pre { background: #f7f7f7; padding: 10px; overflow: auto; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .card { border: 1px solid #ddd; border-radius: 6px; padding: 12px; }
    label { display: block; margin-top: 6px; }
    input[type="text"], input[type="number"] { width: 120px; }
    .footer { margin-top: 24px; color: #666; font-size: 12px; }
  </style>
</head>
<body>
  <h1>Lucas Garden Water Control System</h1>
  <small>Simple management UI</small>

  <div class="grid">
    <div class="card">
      <h3>Settings</h3>
      <form method="POST" action="/api/settings">
        <label>Humidity target (%): <input name="humidity_target_percent" type="number" step="0.1" required value="{humidity_target_percent}"></label>
        <label>Start time (HH:MM): <input name="watering_start_time" type="text" required value="{watering_start_time}"></label>
        <label>Max minutes / zone: <input name="watering_max_minutes_per_zone" type="number" min="1" required value="{watering_max_minutes_per_zone}"></label>
        <label>Rain cancel prob (0-1): <input name="rain_cancel_probability_threshold" type="number" min="0" max="1" step="0.01" required value="{rain_cancel_probability_threshold}"></label>
        <label>Units:
          <select name="units">
            <option value="metric" {metric_sel}>Metric (L)</option>
            <option value="imperial" {imperial_sel}>Imperial (gal)</option>
          </select>
        </label>
        <p><button type="submit">Save</button></p>
      </form>
    </div>

    <div class="card">
      <h3>Weather</h3>
      <p>Next 24h rain probability: <strong>{rain_prob_pct}%</strong></p>
      <form method="POST" action="/api/simulate_pulses">
        <label>Simulate pulses (dev only): <input name="pulses" type="number" min="0" value="0"></label>
        <button type="submit">Send</button>
      </form>
    </div>
  </div>

  <div class="card" style="margin-top:16px;">
    <h3>Latest Trends (most recent 20)</h3>
    <pre id="trends">{trends_json}</pre>
  </div>

  <div class="footer">Zones: {zones}</div>
</body>
</html>
"""

class RequestHandler(BaseHTTPRequestHandler):
    weather: WeatherService = None  # type: ignore
    pulses: PulseCounter = None  # type: ignore

    def _read_body(self):
        length = int(self.headers.get("Content-Length", "0"))
        return self.rfile.read(length) if length > 0 else b""

    def do_GET(self):
        if self.path.startswith("/api/trends"):
            self._json(trends_store.read())
            return
        if self.path.startswith("/api/settings"):
            self._json(settings_store.read())
            return
        if self.path.startswith("/"):
            s = settings_store.read()
            t = trends_store.read()
            rain_prob = self.weather.get_next_12h_rain_probability() if self.weather else 0.0
            html = DASHBOARD_HTML.format(
                humidity_target_percent=s.get("humidity_target_percent"),
                watering_start_time=s.get("watering_start_time"),
                watering_max_minutes_per_zone=s.get("watering_max_minutes_per_zone"),
                rain_cancel_probability_threshold=s.get("rain_cancel_probability_threshold"),
                metric_sel="selected" if s.get("units") == "metric" else "",
                imperial_sel="selected" if s.get("units") == "imperial" else "",
                rain_prob_pct=int(rain_prob * 100),
                trends_json=json.dumps({
                    "humidity": t.get("humidity", [])[-20:],
                    "temperature": t.get("temperature", [])[-20:],
                    "ph": t.get("ph", [])[-20:],
                    "ec": t.get("ec", [])[-20:],
                    "salinity": t.get("salinity", [])[-20:],
                    "tds": t.get("tds", [])[-20:],
                    "npk": t.get("npk", [])[-20:],
                    "water": t.get("water", [])[-20:],
                    "events": t.get("events", [])[-20:],
                }, indent=2),
                zones=", ".join([f"{z}:{ZONES[z]['name']}" for z in sorted(ZONES.keys())])
            )
            self._html(html)
            return
        self.send_error(404, "Not found")

    def do_POST(self):
        if self.path.startswith("/api/settings"):
            body = self._read_body().decode("utf-8")
            data = parse_qs(body)
            def _upd(s):
                s["humidity_target_percent"] = float(data.get("humidity_target_percent", [s["humidity_target_percent"]])[0])
                s["watering_start_time"] = data.get("watering_start_time", [s["watering_start_time"]])[0]
                s["watering_max_minutes_per_zone"] = int(data.get("watering_max_minutes_per_zone", [s["watering_max_minutes_per_zone"]])[0])
                s["rain_cancel_probability_threshold"] = float(data.get("rain_cancel_probability_threshold", [s["rain_cancel_probability_threshold"]])[0])
                s["units"] = data.get("units", [s["units"]])[0]
                return s
            settings_store.update(_upd)
            self._redirect("/")
            return
        if self.path.startswith("/api/simulate_pulses"):
            body = self._read_body().decode("utf-8")
            data = parse_qs(body)
            pulses = int(data.get("pulses", ["0"])[0])
            if self.pulses:
                self.pulses.simulate_pulses(pulses)
            self._redirect("/")
            return
        self.send_error(404, "Not found")

    def _json(self, obj):
        payload = json.dumps(obj).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _html(self, html: str):
        payload = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _redirect(self, where: str):
        self.send_response(303)
        self.send_header("Location", where)
        self.end_headers()

class WebServer:
    def __init__(self, weather: WeatherService, pulses: PulseCounter, host: str, port: int):
        self._server = HTTPServer((host, port), RequestHandler)
        RequestHandler.weather = weather
        RequestHandler.pulses = pulses
        self._thread = threading.Thread(target=self._server.serve_forever, name="WebServer", daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._server.shutdown()
        self._thread.join(timeout=5)
