# app.py
# ======
# Flask backend for the AI-Based Sustainable Route Recommendation System.
# Phase 1 + Web Dashboard.
#
# Modes
# -----
# SIMULATED : Uses the synthetic 8-node graph from simulation_data.py.
#             Always available offline, no external requests.
# REAL      : Downloads a real road network via OSMnx from OpenStreetMap.
#             Requires internet access. Falls back to SIMULATED on error.
#
# Traffic data: NOT live. All congestion values are synthetic estimates.
# ML scoring:   NOT trained. Formula-based scoring from sustainability.py.
#               ML model is a planned future extension.

import os
import json
import traceback

from flask import Flask, render_template, request, jsonify

from road_network    import build_graph, validate_nodes, is_connected_path
from route_optimizer import (
    compute_all_routes,
    find_shortest_distance_route,
    find_fastest_time_route,
)
from sustainability  import score_routes, PREFERENCE_PROFILES
from simulation_data import NODES as SIM_NODES

app = Flask(__name__)

# Build the simulated graph once at startup (fast, no network needed)
_SIM_GRAPH = build_graph()

# Fixed geographic positions for the simulated nodes.
# These are mapped to a compact area in Bengaluru for display purposes.
# They are ILLUSTRATIVE ONLY and do not match real intersections.
SIM_NODE_COORDS = {
    "A": [12.9716, 77.5946],   # City centre reference
    "B": [12.9650, 77.5870],
    "C": [12.9750, 77.6050],
    "D": [12.9580, 77.5780],
    "E": [12.9680, 77.5980],
    "F": [12.9770, 77.6130],
    "G": [12.9600, 77.5900],
    "H": [12.9640, 77.6070],
}


# ---------------------------------------------------------------------------
# Helper: serialise a route dict for JSON (strip non-serialisable objects)
# ---------------------------------------------------------------------------

def _serialise_route(route: dict, rank: int,
                     is_recommended: bool,
                     is_shortest: bool,
                     is_fastest: bool,
                     mode: str = "simulated") -> dict:
    """Convert a route dict into a JSON-safe dict for the frontend."""
    out = {
        "rank"               : rank,
        "path_str"           : route["path_str"],
        "distance_km"        : route["distance_km"],
        "travel_time_min"    : route["travel_time_min"],
        "fuel_L"             : route["fuel_L"],
        "co2_kg"             : route["co2_kg"],
        "avg_congestion"     : route["avg_congestion"],
        "sustainability_score": route.get("sustainability_score", 0.0),
        "is_recommended"     : is_recommended,
        "is_shortest"        : is_shortest,
        "is_fastest"         : is_fastest,
        "mode"               : mode,
        "pollution_note"     : "Pollution exposure: FUTURE EXTENSION",
        "ml_note"            : "ML-based scoring: PENDING (formula-based for now)",
        "traffic_note"       : route.get(
            "traffic_note",
            "Travel time estimated from speed and synthetic congestion. NOT real-time."
        ),
        "data_source"        : route.get("data_source", "Synthetic simulated data"),
        "coordinates"        : route.get("coordinates", []),
    }

    # For simulated mode, build polyline from fixed node coordinates
    if mode == "simulated" and not out["coordinates"]:
        path_nodes = route.get("path", [])
        out["coordinates"] = [
            SIM_NODE_COORDS[n] for n in path_nodes if n in SIM_NODE_COORDS
        ]

    return out


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Serve the main dashboard page."""
    return render_template("index.html")


@app.route("/api/nodes")
def api_nodes():
    """Return simulated node list with their display coordinates."""
    nodes = [
        {"id": n, "label": n, "lat": SIM_NODE_COORDS[n][0], "lon": SIM_NODE_COORDS[n][1]}
        for n in SIM_NODES
    ]
    return jsonify({"nodes": nodes})


@app.route("/api/route/simulated", methods=["POST"])
def api_route_simulated():
    """
    Compute routes on the SIMULATED graph.

    POST body (JSON):
        source      : node label e.g. "A"
        destination : node label e.g. "H"
        preference  : "fastest" | "eco" | "balanced"

    Returns JSON with all candidate routes, scores, and baselines.
    """
    body = request.get_json(force=True)
    source      = str(body.get("source", "A")).upper().strip()
    destination = str(body.get("destination", "H")).upper().strip()
    preference  = str(body.get("preference", "balanced")).lower().strip()

    # --- Input validation ---
    try:
        validate_nodes(_SIM_GRAPH, source, destination)
    except ValueError as e:
        return jsonify({"error": str(e), "available_nodes": SIM_NODES}), 400

    if preference not in PREFERENCE_PROFILES:
        return jsonify({"error": f"Unknown preference '{preference}'. "
                                 f"Use: {list(PREFERENCE_PROFILES.keys())}"}), 400

    if not is_connected_path(_SIM_GRAPH, source, destination):
        return jsonify({"error": f"No path between '{source}' and '{destination}'."}), 404

    # --- Compute ---
    raw_routes    = compute_all_routes(_SIM_GRAPH, source, destination)
    shortest_r    = find_shortest_distance_route(raw_routes)
    fastest_r     = find_fastest_time_route(raw_routes)
    scored_routes = score_routes(raw_routes, preference)
    recommended   = scored_routes[0]

    out_routes = []
    for rank, route in enumerate(scored_routes, start=1):
        out_routes.append(_serialise_route(
            route, rank,
            is_recommended = route["path_str"] == recommended["path_str"],
            is_shortest    = route["path_str"] == shortest_r["path_str"],
            is_fastest     = route["path_str"] == fastest_r["path_str"],
            mode           = "simulated",
        ))

    baseline_shortest = _serialise_route(shortest_r, 0, False, True, False, "simulated")
    baseline_fastest  = _serialise_route(fastest_r,  0, False, False, True, "simulated")
    baseline_rec      = _serialise_route(
        recommended, 0, True, False, False, "simulated"
    )

    return jsonify({
        "mode"             : "simulated",
        "source"           : source,
        "destination"      : destination,
        "preference"       : preference,
        "disclaimer"       : (
            "All metrics computed from SYNTHETIC data. "
            "Not real measurements."
        ),
        "ml_note"          : "ML scoring: PENDING. Using formula-based scoring.",
        "routes"           : out_routes,
        "baseline"         : {
            "shortest"     : baseline_shortest,
            "fastest"      : baseline_fastest,
            "recommended"  : baseline_rec,
        },
        "sim_node_coords"  : SIM_NODE_COORDS,
    })


@app.route("/api/route/real", methods=["POST"])
def api_route_real():
    """
    Compute routes on a REAL OpenStreetMap road network via OSMnx.

    POST body (JSON):
        origin_lat      : float
        origin_lon      : float
        dest_lat        : float
        dest_lon        : float
        preference      : "fastest" | "eco" | "balanced"

    Falls back to a JSON error (does NOT auto-switch to simulated mode;
    that switch is handled client-side so the user sees clear feedback).
    """
    # Late import so the module loads even if osmnx is absent
    try:
        from osm_network import build_osm_graph, find_osm_routes
    except ImportError as e:
        return jsonify({"error": f"OSMnx not available: {e}"}), 503

    body = request.get_json(force=True)
    try:
        lat1 = float(body["origin_lat"])
        lon1 = float(body["origin_lon"])
        lat2 = float(body["dest_lat"])
        lon2 = float(body["dest_lon"])
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"error": f"Invalid coordinates: {e}"}), 400

    preference = str(body.get("preference", "balanced")).lower().strip()
    if preference not in PREFERENCE_PROFILES:
        return jsonify({"error": f"Unknown preference '{preference}'."}), 400

    try:
        G, orig_node, dest_node = build_osm_graph(lat1, lon1, lat2, lon2)
    except Exception as e:
        return jsonify({
            "error": f"Could not load road network from OpenStreetMap: {e}",
            "hint" : "Check internet connection. Falling back to simulated mode.",
        }), 502

    try:
        raw_routes = find_osm_routes(G, orig_node, dest_node)
    except Exception as e:
        return jsonify({"error": f"Route calculation failed: {e}"}), 500

    if not raw_routes:
        return jsonify({"error": "No driveable routes found between those points."}), 404

    shortest_r    = min(raw_routes, key=lambda r: r["distance_km"])
    fastest_r     = min(raw_routes, key=lambda r: r["travel_time_h"])
    scored_routes = score_routes(raw_routes, preference)
    recommended   = scored_routes[0]

    out_routes = []
    for rank, route in enumerate(scored_routes, start=1):
        out_routes.append(_serialise_route(
            route, rank,
            is_recommended = route["path_str"] == recommended["path_str"],
            is_shortest    = route["path_str"] == shortest_r["path_str"],
            is_fastest     = route["path_str"] == fastest_r["path_str"],
            mode           = "real",
        ))

    return jsonify({
        "mode"        : "real",
        "preference"  : preference,
        "disclaimer"  : (
            "Road geometry from OpenStreetMap (c) contributors, ODbL. "
            "Fuel, CO2, congestion: SYNTHETIC estimates, NOT real measurements."
        ),
        "ml_note"     : "ML scoring: PENDING. Using formula-based scoring.",
        "traffic_note": (
            "Travel time estimated from OSM speed data with synthetic congestion. "
            "NOT real-time traffic."
        ),
        "routes"      : out_routes,
        "baseline"    : {
            "shortest"    : _serialise_route(shortest_r, 0, False, True, False, "real"),
            "fastest"     : _serialise_route(fastest_r,  0, False, False, True, "real"),
            "recommended" : _serialise_route(recommended, 0, True, False, False, "real"),
        },
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
