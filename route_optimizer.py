"""
route_optimizer.py
==================
Finds candidate routes between a source and destination using
NetworkX path-finding algorithms, and computes per-route metrics.

Design note
-----------
NetworkX's simple_paths generator returns all simple paths (no
repeated nodes). We cap this at MAX_CANDIDATE_PATHS to avoid
combinatorial explosion on larger graphs. On the small simulated
network this limit is never reached, but the cap is there for safety
when the network is later replaced with a real one.
"""

import networkx as nx
from road_network import get_edge_attr, average_edge_attr

# Maximum number of candidate paths to consider.
# Increase this later if the road network grows substantially.
MAX_CANDIDATE_PATHS = 10


def find_candidate_paths(graph: nx.Graph, source: str, destination: str) -> list:
    """
    Generate up to MAX_CANDIDATE_PATHS simple paths from source to
    destination and return them as a list of node-label lists.

    A 'simple path' visits each node at most once, so there are no loops.
    NetworkX uses a depth-first search to enumerate them.

    Parameters
    ----------
    graph       : road-network graph
    source      : starting intersection label
    destination : ending intersection label

    Returns
    -------
    list of lists
        Each inner list is an ordered sequence of node labels, e.g.
        [["A", "B", "E", "G"], ["A", "C", "E", "G"], ...]

    Raises
    ------
    ValueError
        If no path exists between source and destination.
    """
    path_generator = nx.all_simple_paths(graph, source=source, target=destination)

    candidate_paths = []
    for path in path_generator:
        candidate_paths.append(path)
        if len(candidate_paths) >= MAX_CANDIDATE_PATHS:
            break   # Safety cap reached

    if not candidate_paths:
        raise ValueError(
            f"No path found between '{source}' and '{destination}'. "
            "Check that the nodes are connected in the road network."
        )

    return candidate_paths


def compute_route_metrics(graph: nx.Graph, path: list) -> dict:
    """
    Calculate all performance metrics for a single candidate route.

    Metrics returned
    ----------------
    path            : list of node labels
    path_str        : human-readable string like "A -> B -> E -> G"
    num_edges       : number of road segments in the route
    distance_km     : total route distance (km)
    travel_time_h   : estimated total travel time (hours)
    travel_time_min : estimated total travel time (minutes)
    fuel_L          : estimated total fuel consumption (litres)
    co2_kg          : estimated total CO2 emissions (kg)
    avg_congestion  : mean congestion level across all segments [0, 1]

    Parameters
    ----------
    graph : road-network graph (must have pre-computed edge attributes)
    path  : ordered list of node labels for this route

    Returns
    -------
    dict
        Dictionary containing all metrics listed above.
    """
    distance_km    = get_edge_attr(graph, path, "distance_km")
    travel_time_h  = get_edge_attr(graph, path, "travel_time_h")
    fuel_L         = get_edge_attr(graph, path, "fuel_L")
    co2_kg         = get_edge_attr(graph, path, "co2_kg")
    avg_congestion = average_edge_attr(graph, path, "congestion")

    return {
        "path"           : path,
        "path_str"       : " -> ".join(path),
        "num_edges"      : len(path) - 1,
        "distance_km"    : round(distance_km,    3),
        "travel_time_h"  : round(travel_time_h,  4),
        "travel_time_min": round(travel_time_h * 60, 2),
        "fuel_L"         : round(fuel_L,          4),
        "co2_kg"         : round(co2_kg,          4),
        "avg_congestion" : round(avg_congestion,  4),
        # Pollution exposure: FUTURE EXTENSION
        # Will be filled when an air-quality data source is integrated.
        "pollution_exposure": None,
    }


def compute_all_routes(graph: nx.Graph, source: str, destination: str) -> list:
    """
    Find all candidate paths and compute their metrics.

    Parameters
    ----------
    graph       : road-network graph
    source      : starting intersection label
    destination : ending intersection label

    Returns
    -------
    list of dicts
        One metrics dictionary per candidate route.
    """
    paths   = find_candidate_paths(graph, source, destination)
    routes  = [compute_route_metrics(graph, p) for p in paths]
    return routes


def find_shortest_distance_route(routes: list) -> dict:
    """
    Return the route with the smallest total distance.
    This is the conventional shortest-path baseline.

    Parameters
    ----------
    routes : list of route-metrics dicts

    Returns
    -------
    dict
        The route with minimum distance_km.
    """
    return min(routes, key=lambda r: r["distance_km"])


def find_fastest_time_route(routes: list) -> dict:
    """
    Return the route with the smallest estimated travel time.
    This is the conventional fastest-route baseline.

    Parameters
    ----------
    routes : list of route-metrics dicts

    Returns
    -------
    dict
        The route with minimum travel_time_h.
    """
    return min(routes, key=lambda r: r["travel_time_h"])
