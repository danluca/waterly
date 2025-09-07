#  MIT License
#
#  Copyright (c) 2025 by Dan Luca. All rights reserved.
#

import os

from .weather import WeatherService
from .pulses import PulseCounter

from flask import Flask, jsonify, request, render_template, send_from_directory, abort
from werkzeug.exceptions import HTTPException
from .config import get_project_root

HTTP_HOST = "0.0.0.0"
HTTP_PORT = 8080
app = Flask(__name__, static_url_path="/static", static_folder="static", template_folder="tmpl", root_path=f"{get_project_root()}/web")

# --------------------------
# HTML pages (from disk)
# --------------------------
@app.get("/")
def home():
    # Renders templates/index.html from the templates/ folder
    return render_template("index.html", title="Home")

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


