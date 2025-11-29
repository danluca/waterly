#  MIT License
#
#  Copyright (c) 2025 by Dan Luca. All rights reserved.
#

import os
import re
import logging
import json

from dataclasses import asdict
from datetime import datetime
from pytz import timezone
from flask import Flask, jsonify, request, render_template, send_from_directory, abort, Response
from werkzeug.exceptions import HTTPException

from .patch import PATCHES
from .queues import send_message_to_scheduler, QueueMessage, Action
from .model.measurement import convert_measurement_unit_type
from .model.times import valid_timezone, now_local
from .model.units import UnitType, Unit
from .model.about import ABOUT
from .config import get_project_root, CONFIG, Settings, RPI_ZONE_NAME
from .storage import db

HTTP_HOST = "0.0.0.0"
HTTP_PORT = 8080
app = Flask(__name__, static_url_path="/static", static_folder="static", template_folder="tmpl", root_path=f"{get_project_root()}/web")

# --------------------------
# HTML pages (from disk)
# --------------------------
@app.get("/")
@app.get("/index.html")
def home():
    # Renders templates/index.html from the templates/ folder
    # return render_template("index.html", title="Home")
    directory = app.static_folder
    filename = "index.html"
    if not os.path.exists(os.path.join(directory, filename)):
        abort(404)
    return send_from_directory(directory, filename, mimetype="text/html")


# @app.get("/about.html")
def about():
    # Renders templates/about.html
    return render_template("about.html", title="About")

# Optional: serve raw HTML files from a pages/ directory (no templating)
@app.get("/html/<path:filename>")
def serve_raw_page(filename: str):
    # Restrict to .html files only
    if not filename.endswith(".html"):
        abort(404)
    directory = app.static_folder
    if not os.path.exists(os.path.join(directory, filename)):
        abort(404)
    return send_from_directory(directory, filename)

# --------------------------
# JSON REST API
# --------------------------
@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})

@app.get("/api/about")
def api_about():
    info = asdict(ABOUT)
    now = now_local()
    tz = CONFIG[Settings.LOCAL_TIMEZONE]
    tz_name = getattr(tz, "zone", None) or str(tz)
    # include computed properties not present in asdict
    try:
        info["wifi_bars"] = ABOUT.wifi_bars if ABOUT.wifi_rssi is not None else None
    except Exception:
        info["wifi_bars"] = None
    info.update({
        "now": now.isoformat(),
        "timezone": tz_name,
    })
    return jsonify(info)

@app.get("/api/manifest")
def manifest():
    directory = app.static_folder
    filename = "manifest.json"
    if not os.path.exists(os.path.join(directory, filename)):
        abort(404)
    return send_from_directory(directory, filename, mimetype="application/json")

@app.get("/api/items")
def list_items():
    return jsonify({"items": []})

@app.post("/api/items")
def create_item():
    return jsonify({"id": 0, "message": "Unsupported operation"}), 201

@app.get("/api/items/<int:item_id>")
def get_item(item_id: int):
    return jsonify({"error": "not found"}), 404

@app.put("/api/items/<int:item_id>")
def update_item(item_id: int):
    return jsonify({"id": item_id, "message": "Unsupported operation"})

@app.delete("/api/items/<int:item_id>")
def delete_item(item_id: int):
    return jsonify({"deleted": item_id})

@app.get("/api/latest/sensors")
def get_latest_sensors():
    with db() as conn:
        cur = conn.cursor()
        # most recent measurements
        rows = cur.execute("select m.name, m.ts_utc, m.tz, m.reading, m.unit, z.name, z.description from v_latest_measurement m, "
                           "zone z where m.name in ('temperature', 'humidity', 'ph', 'rpitemp', 'water', 'nitrogen', 'phosphorus', 'potassium', 'envtemp', 'envhumidity') "
                           "and m.zone_id = z.id").fetchall()
        result = {}
        for name, tutc, tz, reading, unit, zone_name, zone_desc in rows:
            if zone_name not in result:
                result[zone_name] = {}
            result[zone_name]["utc"] = max(int(tutc/1000), result[zone_name].get("utc", 0))
            time = datetime.fromtimestamp(result[zone_name]["utc"], valid_timezone(tz))
            result[zone_name]["name"] = zone_name
            result[zone_name]["desc"] = zone_desc
            result[zone_name]["ts"] = time.isoformat()
            result[zone_name]["date"] = time.strftime("%b %d, %Y")
            result[zone_name]["time"] = time.strftime("%H:%M")
            v, u = convert_measurement_unit_type(reading, unit, CONFIG[Settings.UNITS])
            result[zone_name][name] = v
            result[zone_name][f"{name}_unit"] = u
            patch = next((p for p in PATCHES if p.zone.name == zone_name), None)
            if patch:
                result[zone_name]["water_state"] = patch.water_state
            if name == "water":
                result[zone_name]["last_watering"] = datetime.fromtimestamp(tutc/1000, valid_timezone(tz)).strftime("%b %d, %Y")
        # total water consumed per zone
        waters = cur.execute("select sum(m.reading), z.name, m.unit from measurement m, zone z where m.name ='water' "
                             "and z.id=m.zone_id group by m.zone_id, unit").fetchall()
        for w, z, u in waters:
            if "total_water" not in result[z]:
                result[z]["total_water"] = 0
            v, u = convert_measurement_unit_type(w, u, CONFIG[Settings.UNITS])
            result[z]["total_water"] += v   # the units are the same as the water reading above
            if "last_watering" not in result[z]:
                result[z]["last_watering"] = "n/a"
        # weather info - exclude items without precipitation probability (current conditions)
        now = now_local()
        wrows = cur.execute("select w.forecast_ts_utc, w.tz, w.temperature_2m, w.temperature_unit, w.precipitation, "
                           "w.precipitation_unit, w.precipitation_probability, w.soil_moisture_1_to_3cm, w.moisture_unit from v_weather_12h_window w "
                            "where w.precipitation_probability is not null").fetchall()
        weather = {"prev12": {}, "next12": {}}
        for ts, tz, temp, temp_unit, precip, precip_unit, precip_prob, soil_moisture, moisture_unit in wrows:
            # find temp min and max for previous 12h and next 12h
            time = datetime.fromtimestamp(ts/1000.0, valid_timezone(tz))
            c_temp, c_temp_unit = convert_measurement_unit_type(temp, temp_unit, CONFIG[Settings.UNITS])
            c_precip, c_precip_unit = convert_measurement_unit_type(precip, precip_unit, CONFIG[Settings.UNITS])
            if now >= time:
                if "temp_min" not in weather["prev12"]:
                    weather["prev12"]["temp_min"] = c_temp
                weather["prev12"]["temp_min"] = min(c_temp, weather["prev12"]["temp_min"])
                if "temp_max" not in weather["prev12"]:
                    weather["prev12"]["temp_max"] = c_temp
                weather["prev12"]["temp_max"] = max(c_temp, weather["prev12"]["temp_max"])
                weather["prev12"]["temp_unit"] = c_temp_unit
                if "precip" not in weather["prev12"]:
                    weather["prev12"]["precip"] = 0
                weather["prev12"]["precip"] += c_precip
                weather["prev12"]["precip_unit"] = c_precip_unit
                if "precip_prob" not in weather["prev12"]:
                    weather["prev12"]["precip_prob"] = precip_prob
                weather["prev12"]["precip_prob"] = max(precip_prob, weather["prev12"]["precip_prob"])
                if "soil_moisture_min" not in weather["prev12"]:
                    weather["prev12"]["soil_moisture_min"] = soil_moisture
                weather["prev12"]["soil_moisture_min"] = min(soil_moisture, weather["prev12"]["soil_moisture_min"])
                if "soil_moisture_max" not in weather["prev12"]:
                    weather["prev12"]["soil_moisture_max"] = soil_moisture
                weather["prev12"]["soil_moisture_max"] = max(soil_moisture, weather["prev12"]["soil_moisture_max"])
                weather["prev12"]["soil_moisture_unit"] = moisture_unit
            else:
                if "temp_min" not in weather["next12"]:
                    weather["next12"]["temp_min"] = c_temp
                weather["next12"]["temp_min"] = min(c_temp, weather["next12"]["temp_min"])
                if "temp_max" not in weather["next12"]:
                    weather["next12"]["temp_max"] = c_temp
                weather["next12"]["temp_max"] = max(c_temp, weather["next12"]["temp_max"])
                weather["next12"]["temp_unit"] = c_temp_unit
                if "precip" not in weather["next12"]:
                    weather["next12"]["precip"] = 0
                weather["next12"]["precip"] += c_precip
                weather["next12"]["precip_unit"] = c_precip_unit
                if "precip_prob" not in weather["next12"]:
                    weather["next12"]["precip_prob"] = precip_prob
                weather["next12"]["precip_prob"] = max(precip_prob, weather["next12"]["precip_prob"])
                if "soil_moisture_min" not in weather["next12"]:
                    weather["next12"]["soil_moisture_min"] = soil_moisture
                weather["next12"]["soil_moisture_min"] = min(soil_moisture, weather["next12"]["soil_moisture_min"])
                if "soil_moisture_max" not in weather["next12"]:
                    weather["next12"]["soil_moisture_max"] = soil_moisture
                weather["next12"]["soil_moisture_max"] = max(soil_moisture, weather["next12"]["soil_moisture_max"])
                weather["next12"]["soil_moisture_unit"] = moisture_unit
        weather["timestamp"] = {"date": now.strftime("%b %d, %Y"), "time": now.strftime("%H:%M"), "utc": now.timestamp()}
        weather["location"] = CONFIG[Settings.LOCATION]
        weather["prev12"]["soil_moisture_min"] = 100.0 * weather["prev12"]["soil_moisture_min"]
        weather["prev12"]["soil_moisture_max"] = 100.0 * weather["prev12"]["soil_moisture_max"]
        weather["next12"]["soil_moisture_min"] = 100.0 * weather["next12"]["soil_moisture_min"]
        weather["next12"]["soil_moisture_max"] = 100.0 * weather["next12"]["soil_moisture_max"]
        weather["prev12"]["soil_moisture_unit"] = Unit.PERCENT
        weather["next12"]["soil_moisture_unit"] = Unit.PERCENT
        forecast_time = CONFIG[Settings.WEATHER_LAST_CHECK_TIMESTAMP]
        weather["forecast_time"] = {"date": forecast_time.strftime("%b %d, %Y"), "time": forecast_time.strftime("%H:%M"), "utc": forecast_time.timestamp()}
        result["weather"] = weather
        result[RPI_ZONE_NAME]["wifi_bars"] = ABOUT.wifi_bars
        return jsonify(result)

@app.post("/api/water/<string:zone_name>/start")
def api_start_watering(zone_name: str):
    # Validate zone exists
    patch = next((p for p in PATCHES if p.zone.name == zone_name), None)
    if patch is None:
        return jsonify({"error": "not_found", "message": f"Zone '{zone_name}' not found"}), 404

    body = request.get_json(silent=True) or {}
    minutes = body.get("minutes") if isinstance(body, dict) else None
    if minutes is None:
        minutes = request.args.get("minutes")
    # Validate minutes if provided
    if minutes is not None:
        try:
            minutes = int(minutes)
            if minutes <= 0:
                raise ValueError("minutes must be > 0")
        except Exception as e:
            return jsonify({"error": "invalid_request", "message": f"Invalid 'minutes' value: {e}"}), 400

    try:
        msg = QueueMessage(Action.START_WATERING, {"zone": zone_name, "minutes": minutes})
        send_message_to_scheduler(msg)
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to enqueue start watering message: {e}")
        return jsonify({"error": "internal_error", "message": "Could not submit watering request"}), 500

    return jsonify({"status": "accepted", "zone": zone_name, "minutes": minutes}), 202


@app.post("/api/water/<string:zone_name>/stop")
def api_stop_watering(zone_name: str):
    # Validate zone exists
    patch = next((p for p in PATCHES if p.zone.name == zone_name), None)
    if patch is None:
        return jsonify({"error": "not_found", "message": f"Zone '{zone_name}' not found"}), 404

    try:
        msg = QueueMessage(Action.STOP_WATERING, {"zone": zone_name})
        send_message_to_scheduler(msg)
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to enqueue stop watering message: {e}")
        return jsonify({"error": "internal_error", "message": "Could not submit stop request"}), 500

    return jsonify({"status": "accepted", "zone": zone_name}), 202


# --------------------------
# Settings page and Config API
# --------------------------
@app.get("/settings")
@app.get("/about")
@app.get("/settings.html")
def settings_page():
    directory = app.static_folder
    # filename = "settings.html"
    filename = "index.html"
    if not os.path.exists(os.path.join(directory, filename)):
        abort(404)
    return send_from_directory(directory, filename, mimetype="text/html")


@app.get("/api/config")
def get_config():
    # return jsonify(CONFIG.to_json())
    return Response(CONFIG.to_json(), mimetype="application/json")

@app.post("/api/config")
def update_config():
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"error": "invalid_request", "message": "Expected JSON object"}), 400

    changed = []
    errors = []
    def set_value(setting: Settings, value):
        try:
            CONFIG[setting] = value
            changed.append(setting.name)
        except Exception as e2:
            errors.append({"setting": setting.name, "message": str(e2)})

    # Map incoming modifiable fields to Settings - note the fields that have "last" in their name are not modifiable
    if Settings.UNITS.name in body:
        u = str(body[Settings.UNITS.name]).lower()
        if u in (UnitType.METRIC.name, UnitType.IMPERIAL.name):
            set_value(Settings.UNITS, UnitType[u])
        elif u in (UnitType.METRIC.value, UnitType.IMPERIAL.value):
            set_value(Settings.UNITS, UnitType(u))
        else:
            errors.append({"setting": Settings.UNITS, "message": f"Invalid value (use '{UnitType.METRIC.value}' or '{UnitType.IMPERIAL.value}')"})

    if Settings.LOCAL_TIMEZONE.name in body:
        # noinspection PyBroadException
        try:
            set_value(Settings.LOCAL_TIMEZONE, timezone(body[Settings.LOCAL_TIMEZONE.name]))
        except Exception as e:
            errors.append({"setting": Settings.LOCAL_TIMEZONE, "message": f"Invalid timezone: {e}"})

    if Settings.WATERING_START_TIME.name in body:
        # Expect HH:MM 24h
        val = str(body[Settings.WATERING_START_TIME.name]).strip()
        if re.match(r'^\d{2}:\d{2}$', val):
            set_value(Settings.WATERING_START_TIME, val)
        else:
            errors.append({"setting": Settings.WATERING_START_TIME, "message": f"Invalid format: {val}"})

    if Settings.WATERING_MAX_MINUTES_PER_ZONE.name in body:
        try:
            set_value(Settings.WATERING_MAX_MINUTES_PER_ZONE, int(body[Settings.WATERING_MAX_MINUTES_PER_ZONE.name]))
        except Exception as e:
            errors.append({"setting": Settings.WATERING_MAX_MINUTES_PER_ZONE, "message": f"Must be integer: {e}"})

    if Settings.RAIN_CANCEL_PROBABILITY_THRESHOLD.name in body:
        try:
            set_value(Settings.RAIN_CANCEL_PROBABILITY_THRESHOLD, float(body[Settings.RAIN_CANCEL_PROBABILITY_THRESHOLD.name]))
        except Exception as e:
            errors.append({"setting": Settings.RAIN_CANCEL_PROBABILITY_THRESHOLD, "message": f"Must be number: {e}"})

    if Settings.SENSOR_READ_INTERVAL_SECONDS.name in body:
        try:
            set_value(Settings.SENSOR_READ_INTERVAL_SECONDS, int(body[Settings.SENSOR_READ_INTERVAL_SECONDS.name]))
        except Exception as e:
            errors.append({"setting": Settings.SENSOR_READ_INTERVAL_SECONDS, "message": f"Must be integer: {e}"})

    if Settings.WEATHER_CHECK_INTERVAL_SECONDS.name in body:
        try:
            set_value(Settings.WEATHER_CHECK_INTERVAL_SECONDS, int(body[Settings.WEATHER_CHECK_INTERVAL_SECONDS.name]))
        except Exception as e:
            errors.append({"setting": Settings.WEATHER_CHECK_INTERVAL_SECONDS, "message": f"Must be integer: {e}"})

    if Settings.WEATHER_CHECK_PRE_WATERING_SECONDS.name in body:
        try:
            set_value(Settings.WEATHER_CHECK_PRE_WATERING_SECONDS, int(body[Settings.WEATHER_CHECK_PRE_WATERING_SECONDS.name]))
        except Exception as e:
            errors.append({"setting": Settings.WEATHER_CHECK_PRE_WATERING_SECONDS, "message": f"Must be integer: {e}"})

    if Settings.LOCATION.name in body:
        loc = body[Settings.LOCATION.name]
        try:
            lat = float(loc.get("latitude"))
            lon = float(loc.get("longitude"))
            set_value(Settings.LOCATION, {"latitude": lat, "longitude": lon})
        except Exception as e:
            errors.append({"setting": Settings.LOCATION, "message": f"latitude/longitude must be specified numeric values: {e}"})

    if Settings.GARDENING_SEASON.name in body:
        season = body[Settings.GARDENING_SEASON.name]
        if isinstance(season, dict) and "start" in season and "stop" in season:
            start = str(season["start"]).strip()
            stop = str(season["stop"]).strip()
            if re.match(r'^\d{2}-\d{2}$', start) and re.match(r'^\d{2}-\d{2}$', stop):
                set_value(Settings.GARDENING_SEASON, {"start": start, "stop": stop})
            else:
                errors.append({"setting": Settings.GARDENING_SEASON, "message": f"Expect object with start, stop in pattern MM-DD: {season}"})
        else:
            errors.append({"setting": Settings.GARDENING_SEASON, "message": f"Expect object with start, stop (MM-DD): {season}"})

    if Settings.HUMIDITY_TARGET_PERCENT.name in body:
        h = body[Settings.HUMIDITY_TARGET_PERCENT.name]
        if isinstance(h, dict):
            set_value(Settings.HUMIDITY_TARGET_PERCENT, {k: float(v) for k, v in h.items()})
        else:
            errors.append({"setting": Settings.HUMIDITY_TARGET_PERCENT, "message": f"Expect object per zone: {{Z1: 70, ...}}: {h}"})

    if Settings.TREND_MAX_SAMPLES.name in body:
        try:
            set_value(Settings.TREND_MAX_SAMPLES, int(body[Settings.TREND_MAX_SAMPLES.name]))
        except Exception as e:
            errors.append({"setting": Settings.TREND_MAX_SAMPLES, "message": f"Must be integer: {e}"})

    # Trigger save to disk (DB persistence already handled via callback)
    try:
        CONFIG.save_to_file()
    except Exception as e:
        # non-fatal
        logging.getLogger(__name__).warning(f"Could not save CONFIG to file {e}")
        pass

    # Notify scheduler about config changes
    if changed:
        try:
            msg = QueueMessage(Action.UPDATE_CONFIG)
            send_message_to_scheduler(msg)
        except Exception as e:
            logging.getLogger(__name__).warning(f"Could not send update config message to scheduler {e}")
            pass

    status = 200 if not errors else 207  # 207 Multi-Status for partial failures
    obj = json.loads(CONFIG.to_json())
    return jsonify({"updated": changed, "errors": errors, "config": obj}), status

# --------------------------
# Error handling
# - JSON responses for /api/* errors
# - Default HTML error pages for others
# --------------------------
@app.errorhandler(HTTPException)
def handle_http_exception(e: HTTPException):
    if request.path.startswith("/api/"):
        return jsonify({"error": e.name, "message": e.description, "status": e.code}), e.code
    # Use default HTML error for non-API routes
    return e

def create_app():
    return app

def run_app():
    app.run(host=HTTP_HOST, port=HTTP_PORT, debug=False)


