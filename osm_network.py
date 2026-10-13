# osm_network.py
# ==============
# Wraps OSMnx to fetch a real road network for a given pair of
# geographic coordinates and compute routes on it.
#
# DATA NOTICE
# -----------
# Road geometry comes from OpenStreetMap (c) OpenStreetMap contributors,
# licensed under ODbL (https://www.openstreetmap.org/copyright).
# All fuel, CO2, and congestion estimates are still SYNTHETIC approximations
# derived from OSM road attributes. They are NOT real measurements.
#
# TRAFFIC DATA
# ------------
# No live traffic API is used. Travel time is estimated from OSM speed
# attributes (maxspeed tag) with a configurable synthetic congestion factor
# applied uniformly. This is clearly labelled in all API responses.
#
# ML SCORING NOTE
# ---------------
# The sustainability score uses the same formula-based approach as Phase 1.
# ML-based scoring (Random Forest / XGBoost) is a planned future extension.

import math
import osmnx as ox
import networkx as nx

from simulation_data import (
    FUEL_CONSUMPTION_L_PER_KM,
    CONGESTION_FUEL_MULTIPLIER,
    CO2_KG_PER_LITRE_PETROL,
    CONGESTION_SPEED_FACTOR,
)

# Synthetic uniform congestion applied to all OSM edges (0.0 - 1.0).
# This is NOT real-time data. Labelled clearly in API responses.
SYNTHETIC_OSM_CONGESTION = 0.30

# Default assumed speed (km/h) when OSM maxspeed tag is missing.
DEFAULT_SPEED_KMH = 40

# Maximum number of candidate paths returned for a real OSM query.
MAX_OSM_CANDIDATE_PATHS = 5

# Maximum graph radius (metres) around each point when fetching OSM data.
OSM_GRAPH_RADIUS_M = 2000


def _speed_from_osm(data: dict) -> float:
    """
    Extract a numeric speed (km/h) from an OSM edge data dict.
    OSM maxspeed values can be strings like "50", "50 mph", or lists.
    Falls back to DEFAULT_SPEED_KMH when the tag is absent or unparseable.
    """
    raw = data.get("speed_kph") or data.get("maxspeed", None)
    if raw is None:
        return DEFAULT_SPEED_KMH
    if isinstance(raw, list):
        raw = raw[0]
    try:
        # Strip non-numeric suffixes ("50 mph" -> 50)
        speed = float(str(raw).split()[0])
        if "mph" in str(raw).lower():
            speed *= 1.60934   # Convert mph to km/h
        return max(speed, 5.0)  # Minimum 5 km/h
    except (ValueError, IndexError):
        return DEFAULT_SPEED_KMH


def build_osm_graph(lat1: float, lon1: float, lat2: float, lon2: float):
    """
    Download a driveable road network from OSMnx covering both coordinates,
    add fuel/CO2/time attributes, and return (graph, origin_node, dest_node).

    The downloaded area is a bounding box that encompasses both points with
    a small buffer. Uses OSMnx''s drive network type.

    Parameters
    ----------
    lat1, lon1 : latitude/longitude of the origin point
    lat2, lon2 : latitude/longitude of the destination point

    Returns
    -------
    tuple : (nx.MultiDiGraph, int, int)
        graph      - OSMnx drive graph with added attributes
        orig_node  - nearest graph node to (lat1, lon1)
        dest_node  - nearest graph node to (lat2, lon2)

    Raises
    ------
    Exception
        If OSMnx cannot download data (network error, too-small area, etc.)
    """
    # Compute bounding box with 20% padding
    min_lat = min(lat1, lat2)
    max_lat = max(lat1, lat2)
    min_lon = min(lon1, lon2)
    max_lon = max(lon1, lon2)
    lat_pad = max((max_lat - min_lat) * 0.2, 0.005)
    lon_pad = max((max_lon - min_lon) * 0.2, 0.005)

    bbox = (
        max_lat + lat_pad,   # north
        min_lat - lat_pad,   # south
        max_lon + lon_pad,   # east
        min_lon - lon_pad,   # west
    )

    G = ox.graph_from_bbox(
        bbox=bbox,
        network_type="drive",
        simplify=True,
    )

    # Add speed and travel_time attributes (osmnx helper)
    G = ox.add_edge_speeds(G)
    G = ox.add_edge_travel_times(G)

    # Add fuel/CO2 attributes using same formulas as Phase 1
    for u, v, k, data in G.edges(data=True, keys=True):
        length_m   = data.get("length", 0)          # OSMnx stores length in metres
        distance_km = length_m / 1000.0
        speed_kmh   = _speed_from_osm(data)
        congestion  = SYNTHETIC_OSM_CONGESTION      # Uniform synthetic value

        effective_speed = speed_kmh * (1.0 - CONGESTION_SPEED_FACTOR * congestion)
        effective_speed = max(effective_speed, 1.0)
        travel_time_h   = distance_km / effective_speed

        fuel_L  = distance_km * FUEL_CONSUMPTION_L_PER_KM * (1.0 + CONGESTION_FUEL_MULTIPLIER * congestion)
        co2_kg  = fuel_L * CO2_KG_PER_LITRE_PETROL

        data["distance_km"]   = round(distance_km, 4)
        data["speed_kmh"]     = round(speed_kmh, 1)
        data["congestion"]    = congestion
        data["travel_time_h"] = round(travel_time_h, 6)
        data["fuel_L"]        = round(fuel_L, 6)
        data["co2_kg"]        = round(co2_kg, 6)

    orig_node = ox.nearest_nodes(G, X=lon1, Y=lat1)
    dest_node = ox.nearest_nodes(G, X=lon2, Y=lat2)

    return G, orig_node, dest_node


def _sum_attr(G, path_nodes: list, attr: str) -> float:
    """Sum an edge attribute along a path (handles MultiDiGraph)."""
    total = 0.0
    for i in range(len(path_nodes) - 1):
        u, v = path_nodes[i], path_nodes[i + 1]
        # In a MultiDiGraph there may be parallel edges; take the minimum
        edge_data_list = list(G[u][v].values())
        best = min(edge_data_list, key=lambda d: d.get(attr, float("inf")))
        total += best.get(attr, 0.0)
    return total


def _avg_attr(G, path_nodes: list, attr: str) -> float:
    n = len(path_nodes) - 1
    if n <= 0:
        return 0.0
    return _sum_attr(G, path_nodes, attr) / n


def _path_coordinates(G, path_nodes: list) -> list:
    """
    Return a list of [lat, lon] pairs for every node in the path.
    Used by Leaflet to draw polylines.
    """
    coords = []
    for node in path_nodes:
        node_data = G.nodes[node]
        coords.append([node_data["y"], node_data["x"]])  # OSMnx: y=lat, x=lon
    return coords


def find_osm_routes(G, orig_node: int, dest_node: int) -> list:
    """
    Find up to MAX_OSM_CANDIDATE_PATHS simple paths in the OSMnx graph
    and return route metrics dicts compatible with the existing scoring API.

    Uses Dijkstra by travel_time_h weight for the primary path, then
    Dijkstra by distance_km for a second path, then picks additional
    simple paths if available.

    Parameters
    ----------
    G         : OSMnx MultiDiGraph with added attributes
    orig_node : integer node ID of the origin
    dest_node : integer node ID of the destination

    Returns
    -------
    list of dicts (same schema as compute_route_metrics in route_optimizer.py)
    """
    seen_paths = set()
    routes = []

    def make_route(path_nodes, label=""):
        dist   = _sum_attr(G, path_nodes, "distance_km")
        time_h = _sum_attr(G, path_nodes, "travel_time_h")
        fuel   = _sum_attr(G, path_nodes, "fuel_L")
        co2    = _sum_attr(G, path_nodes, "co2_kg")
        cong   = _avg_attr(G, path_nodes, "congestion")
        coords = _path_coordinates(G, path_nodes)

        return {
            "path"            : path_nodes,
            "path_str"        : f"Route {label}" if label else "Route",
            "num_edges"       : len(path_nodes) - 1,
            "distance_km"     : round(dist,   3),
            "travel_time_h"   : round(time_h, 4),
            "travel_time_min" : round(time_h * 60, 2),
            "fuel_L"          : round(fuel,   4),
            "co2_kg"          : round(co2,    4),
            "avg_congestion"  : round(cong,   4),
            "coordinates"     : coords,
            "pollution_exposure": None,
            "data_source"     : "OpenStreetMap (OSMnx)",
            "traffic_note"    : (
                f"Travel time estimated from OSM speed attributes with "
                f"synthetic congestion={SYNTHETIC_OSM_CONGESTION:.0%}. "
                "NOT real-time traffic data."
            ),
        }

    def try_path(weight_attr, label):
        nonlocal routes, seen_paths
        try:
            path = nx.shortest_path(G, orig_node, dest_node, weight=weight_attr)
            key  = tuple(path)
            if key not in seen_paths:
                seen_paths.add(key)
                routes.append(make_route(path, str(len(routes) + 1)))
        except nx.NetworkXNoPath:
            pass

    # Primary path: fastest
    try_path("travel_time_h", "1")
    # Secondary path: shortest distance
    try_path("distance_km", "2")

    # Try to get a few more via simple paths (cap at MAX_OSM_CANDIDATE_PATHS)
    try:
        gen = nx.all_simple_paths(G, orig_node, dest_node, cutoff=15)
        for path in gen:
            key = tuple(path)
            if key not in seen_paths:
                seen_paths.add(key)
                routes.append(make_route(path, str(len(routes) + 1)))
            if len(routes) >= MAX_OSM_CANDIDATE_PATHS:
                break
    except Exception:
        pass

    return routes
