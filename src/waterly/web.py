#  MIT License
#
#  Copyright (c) 2025 by Dan Luca. All rights reserved.
#

import os

from datetime import datetime
from flask import Flask, jsonify, request, render_template, send_from_directory, abort
from werkzeug.exceptions import HTTPException
from .queues import send_message_to_scheduler
from .model.measurement import convert_measurement
from .model.times import valid_timezone, now_local
from .config import get_project_root, CONFIG, Settings
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


@app.get("/about")
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
                           "zone z where m.name in ('temperature', 'humidity', 'ph', 'rpitemp', 'water') and m.zone_id = z.id").fetchall()
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
            result[zone_name][name] = reading
            result[zone_name][f"{name}_unit"] = unit
            if name == "water":
                result[zone_name]["last_watering"] = datetime.fromtimestamp(tutc/1000, valid_timezone(tz)).strftime("%b %d, %Y")
        # total water consumed per zone
        waters = cur.execute("select sum(m.reading), z.name, m.unit from measurement m, zone z where m.name ='water' "
                             "and z.id=m.zone_id group by m.zone_id, unit").fetchall()
        for w, z, u in waters:
            if "total_water" not in result[z]:
                result[z]["total_water"] = 0
            result[z]["total_water"] += convert_measurement(w, u, result[z]["water_unit"])
            if "last_watering" not in result[z]:
                result[z]["last_watering"] = "n/a"
        # weather info - exclude items without precipitation probability (current conditions)
        now = now_local()
        wrows = cur.execute("select w.forecast_ts_utc, w.tz, w.temperature_2m, w.temperature_unit, w.precipitation, "
                           "w.precipitation_unit, w.precipitation_probability from v_weather_12h_window w "
                            "where w.precipitation_probability is not null").fetchall()
        weather = {"prev12": {}, "next12": {}}
        for ts, tz, temp, temp_unit, precip, precip_unit, precip_prob in wrows:
            # find temp min and max for previous 12h and next 12h
            time = datetime.fromtimestamp(ts/1000.0, valid_timezone(tz))
            if now < time:
                if "temp_min" not in weather["prev12"]:
                    weather["prev12"]["temp_min"] = temp
                weather["prev12"]["temp_min"] = min(temp, weather["prev12"]["temp_min"])
                if "temp_max" not in weather["prev12"]:
                    weather["prev12"]["temp_max"] = temp
                weather["prev12"]["temp_max"] = max(temp, weather["prev12"]["temp_max"])
                weather["prev12"]["temp_unit"] = temp_unit
                if "precip" not in weather["prev12"]:
                    weather["prev12"]["precip"] = 0
                weather["prev12"]["precip"] += precip
                weather["prev12"]["precip_unit"] = precip_unit
                if "precip_prob" not in weather["prev12"]:
                    weather["prev12"]["precip_prob"] = precip_prob
                weather["prev12"]["precip_prob"] = max(precip_prob, weather["prev12"]["precip_prob"])
            else:
                if "temp_min" not in weather["next12"]:
                    weather["next12"]["temp_min"] = temp
                weather["next12"]["temp_min"] = min(temp, weather["next12"]["temp_min"])
                if "temp_max" not in weather["next12"]:
                    weather["next12"]["temp_max"] = temp
                weather["next12"]["temp_max"] = max(temp, weather["next12"]["temp_max"])
                weather["next12"]["temp_unit"] = temp_unit
                if "precip" not in weather["next12"]:
                    weather["next12"]["precip"] = 0
                weather["next12"]["precip"] += precip
                weather["next12"]["precip_unit"] = precip_unit
                if "precip_prob" not in weather["next12"]:
                    weather["next12"]["precip_prob"] = precip_prob
                weather["next12"]["precip_prob"] = max(precip_prob, weather["next12"]["precip_prob"])
        weather["timestamp"] = {"date": now.strftime("%b %d, %Y"), "time": now.strftime("%H:%M"), "utc": now.timestamp()}
        weather["location"] = CONFIG[Settings.LOCATION]
        result["weather"] = weather
        return jsonify(result)

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


