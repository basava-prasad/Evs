"""
road_network.py
===============
Builds a NetworkX graph from the simulated road-network data defined
in simulation_data.py and provides helper functions for querying it.

Design note
-----------
This module is the single place that constructs the graph object.
When a real data source (e.g. OSMnx) is introduced in a later phase,
only this module needs to change; the rest of the codebase continues
to work because it only ever calls the functions defined here.
"""

import networkx as nx
from simulation_data import (
    NODES, EDGES,
    CONGESTION_SPEED_FACTOR,
    FUEL_CONSUMPTION_L_PER_KM,
    CONGESTION_FUEL_MULTIPLIER,
    CO2_KG_PER_LITRE_PETROL,
)


def build_graph() -> nx.Graph:
    """
    Construct and return an undirected weighted graph from the
    simulated node and edge data.

    Each edge stores:
      distance_km   - road segment length (km)
      speed_kmh     - free-flow speed limit (km/h)
      congestion    - simulated congestion level [0, 1]
      travel_time_h - estimated travel time in hours
      fuel_L        - estimated fuel consumption (litres)
      co2_kg        - estimated CO2 emissions (kg)

    Returns
    -------
    nx.Graph
        The populated road-network graph.
    """
    graph = nx.Graph()

    # Add nodes
    graph.add_nodes_from(NODES)

    # Add edges and pre-compute derived attributes
    for (u, v, attrs) in EDGES:
        distance_km = attrs["distance_km"]
        speed_kmh   = attrs["speed_kmh"]
        congestion  = attrs["congestion"]

        # Effective speed drops as congestion rises.
        # effective_speed = speed_kmh * (1 - CONGESTION_SPEED_FACTOR * congestion)
        effective_speed_kmh = speed_kmh * (1.0 - CONGESTION_SPEED_FACTOR * congestion)
        # Guard against zero or negative speed (shouldn't happen with valid data)
        effective_speed_kmh = max(effective_speed_kmh, 1.0)

        # Travel time in hours: time = distance / speed
        travel_time_h = distance_km / effective_speed_kmh

        # Fuel consumption:
        #   base = distance * base_rate
        #   penalty = 1 + multiplier * congestion  (higher congestion → more fuel)
        fuel_L = (
            distance_km
            * FUEL_CONSUMPTION_L_PER_KM
            * (1.0 + CONGESTION_FUEL_MULTIPLIER * congestion)
        )

        # CO2 emissions: proportional to fuel burned
        co2_kg = fuel_L * CO2_KG_PER_LITRE_PETROL

        graph.add_edge(u, v,
                       distance_km   = distance_km,
                       speed_kmh     = speed_kmh,
                       congestion    = congestion,
                       travel_time_h = travel_time_h,
                       fuel_L        = fuel_L,
                       co2_kg        = co2_kg)

    return graph


def validate_nodes(graph: nx.Graph, source: str, destination: str) -> None:
    """
    Raise a ValueError with a clear message if source or destination
    are not present in the graph or are the same node.

    Parameters
    ----------
    graph       : the road-network graph
    source      : starting intersection label
    destination : ending intersection label
    """
    all_nodes = list(graph.nodes)

    if source not in graph:
        raise ValueError(
            f"Source node '{source}' not found in the road network.\n"
            f"Available nodes: {all_nodes}"
        )
    if destination not in graph:
        raise ValueError(
            f"Destination node '{destination}' not found in the road network.\n"
            f"Available nodes: {all_nodes}"
        )
    if source == destination:
        raise ValueError(
            f"Source and destination are both '{source}'. "
            "Please choose two different intersections."
        )


def get_edge_attr(graph: nx.Graph, path: list, attribute: str) -> float:
    """
    Sum a numeric edge attribute over all segments in a path.

    Parameters
    ----------
    graph     : the road-network graph
    path      : list of node labels in route order, e.g. ["A", "B", "E", "G"]
    attribute : name of the edge attribute to sum

    Returns
    -------
    float
        Total value of the attribute along the path.
    """
    total = 0.0
    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        total += graph[u][v][attribute]
    return total


def average_edge_attr(graph: nx.Graph, path: list, attribute: str) -> float:
    """
    Return the arithmetic mean of a numeric edge attribute over all
    segments in a path.

    Parameters
    ----------
    graph     : the road-network graph
    path      : list of node labels in route order
    attribute : name of the edge attribute to average

    Returns
    -------
    float
        Mean value of the attribute; 0.0 if the path has fewer than 2 nodes.
    """
    num_edges = len(path) - 1
    if num_edges <= 0:
        return 0.0
    return get_edge_attr(graph, path, attribute) / num_edges


def is_connected_path(graph: nx.Graph, source: str, destination: str) -> bool:
    """
    Return True if at least one path exists between source and destination.

    Parameters
    ----------
    graph       : the road-network graph
    source      : starting intersection label
    destination : ending intersection label

    Returns
    -------
    bool
    """
    return nx.has_path(graph, source, destination)
