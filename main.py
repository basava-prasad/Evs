"""
main.py
=======
Entry point for the AI-Based Sustainable Route Recommendation System
Phase 1 prototype.

Run from the terminal with the virtual environment activated:
  python main.py

Or override the default source, destination, and preference:
  python main.py --source A --dest H --preference eco

DISCLAIMER
----------
All route metrics (fuel, CO2, congestion, travel time) are computed
from SYNTHETIC simulated data. They are approximations intended for
academic prototyping only and must NOT be interpreted as real
engineering or environmental measurements.

Pollution exposure scoring is a FUTURE EXTENSION (not yet implemented).
"""

import argparse
import os
import sys
import csv

import matplotlib
matplotlib.use("Agg")  # Use non-interactive backend so it works without a display
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import networkx as nx

from road_network      import build_graph, validate_nodes, is_connected_path
from route_optimizer   import (
    compute_all_routes,
    find_shortest_distance_route,
    find_fastest_time_route,
)
from sustainability    import score_routes, PREFERENCE_PROFILES

# ---------------------------------------------------------------------------
# Output directory (created automatically if it does not exist)
# ---------------------------------------------------------------------------
OUTPUT_DIR = "outputs"


def ensure_output_dir():
    """Create the outputs folder if it does not already exist."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def format_path(route: dict) -> str:
    return route["path_str"]


def print_section(title: str):
    """Print a visible section header."""
    width = 72
    print("\n" + "=" * width)
    print(f"  {title}")
    print("=" * width)


def print_route_table(scored_routes: list, preference: str,
                      shortest_dist_path: str, fastest_time_path: str):
    """
    Print a formatted table of all candidate routes with their metrics
    and sustainability scores.

    Columns:
      Rank | Route | Dist(km) | Time(min) | Fuel(L) | CO2(kg) | AvgCong | Score | Tag
    """
    best_path = scored_routes[0]["path_str"]

    # Column widths
    col_route  = 32
    col_num    = 9
    col_tag    = 16

    header = (
        f"{'#':<4}"
        f"{'Route':<{col_route}}"
        f"{'Dist(km)':<{col_num}}"
        f"{'Time(min)':<{col_num}}"
        f"{'Fuel(L)':<{col_num}}"
        f"{'CO2(kg)':<{col_num}}"
        f"{'AvgCong':<{col_num}}"
        f"{'Score':<{col_num}}"
        f"{'Tag':<{col_tag}}"
    )
    print(f"\nPreference profile: {preference.upper()}")
    print("-" * len(header))
    print(header)
    print("-" * len(header))

    for rank, route in enumerate(scored_routes, start=1):
        tags = []
        if route["path_str"] == best_path:
            tags.append("RECOMMENDED")
        if route["path_str"] == shortest_dist_path:
            tags.append("SHORTEST")
        if route["path_str"] == fastest_time_path:
            tags.append("FASTEST")
        tag_str = ", ".join(tags) if tags else ""

        print(
            f"{rank:<4}"
            f"{route['path_str']:<{col_route}}"
            f"{route['distance_km']:<{col_num}.2f}"
            f"{route['travel_time_min']:<{col_num}.1f}"
            f"{route['fuel_L']:<{col_num}.3f}"
            f"{route['co2_kg']:<{col_num}.3f}"
            f"{route['avg_congestion']:<{col_num}.3f}"
            f"{route['sustainability_score']:<{col_num}.4f}"
            f"{tag_str:<{col_tag}}"
        )

    print("-" * len(header))
    print(
        "\nRECOMMENDED route for '{}' preference: {}"
        .format(preference.upper(), best_path)
    )


def print_baseline_comparison(routes: list,
                               shortest_route: dict,
                               fastest_route: dict,
                               recommended_route: dict,
                               preference: str):
    """
    Print a side-by-side comparison of the recommended route against
    the two conventional baselines (shortest distance, fastest time).
    """
    print_section("Baseline Comparison")
    print(
        f"  This table compares the AI-recommended route ('{preference}' "
        "preference)\n"
        "  against the conventional shortest-distance and fastest-time baselines.\n"
    )

    rows = [
        ("Conventional: Shortest distance", shortest_route),
        ("Conventional: Fastest time",      fastest_route),
        (f"AI-recommended ({preference})",  recommended_route),
    ]

    col_label = 38
    col_val   = 12

    header = (
        f"{'Method':<{col_label}}"
        f"{'Route':<36}"
        f"{'Dist(km)':<{col_val}}"
        f"{'Time(min)':<{col_val}}"
        f"{'Fuel(L)':<{col_val}}"
        f"{'CO2(kg)':<{col_val}}"
        f"{'AvgCong':<{col_val}}"
    )
    print("-" * len(header))
    print(header)
    print("-" * len(header))
    for label, route in rows:
        print(
            f"{label:<{col_label}}"
            f"{route['path_str']:<36}"
            f"{route['distance_km']:<{col_val}.2f}"
            f"{route['travel_time_min']:<{col_val}.1f}"
            f"{route['fuel_L']:<{col_val}.3f}"
            f"{route['co2_kg']:<{col_val}.3f}"
            f"{route['avg_congestion']:<{col_val}.3f}"
        )
    print("-" * len(header))


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------

def export_to_csv(scored_routes: list, preference: str,
                  source: str, destination: str):
    """
    Export all candidate route metrics to a CSV file in the outputs folder.

    Parameters
    ----------
    scored_routes : list of route dicts sorted by sustainability score
    preference    : user preference string (for filename)
    source        : source node label
    destination   : destination node label
    """
    filename = os.path.join(
        OUTPUT_DIR,
        f"routes_{source}_to_{destination}_{preference}.csv"
    )

    fieldnames = [
        "rank",
        "path",
        "distance_km",
        "travel_time_min",
        "fuel_L",
        "co2_kg",
        "avg_congestion",
        "sustainability_score",
        "preference",
        "is_recommended",
        "pollution_exposure_note",
    ]

    with open(filename, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        best_path = scored_routes[0]["path_str"]
        for rank, route in enumerate(scored_routes, start=1):
            writer.writerow({
                "rank"                   : rank,
                "path"                   : route["path_str"],
                "distance_km"            : route["distance_km"],
                "travel_time_min"        : route["travel_time_min"],
                "fuel_L"                 : route["fuel_L"],
                "co2_kg"                 : route["co2_kg"],
                "avg_congestion"         : route["avg_congestion"],
                "sustainability_score"   : route["sustainability_score"],
                "preference"             : preference,
                "is_recommended"         : route["path_str"] == best_path,
                "pollution_exposure_note": "FUTURE EXTENSION - not yet implemented",
            })

    print(f"\n  Results exported to: {filename}")
    return filename


# ---------------------------------------------------------------------------
# Visualisation
# ---------------------------------------------------------------------------

# Fixed node positions for a consistent layout that matches the diagram
# in simulation_data.py
NODE_POSITIONS = {
    "A": (2,   4),
    "B": (1,   3),
    "C": (3,   3),
    "D": (0,   2),
    "E": (2,   2),
    "F": (4,   2),
    "G": (1,   1),
    "H": (3,   1),
}


def visualise_network(graph: nx.Graph,
                      recommended_path: list,
                      preference: str,
                      source: str,
                      destination: str):
    """
    Draw the road network, highlighting the recommended route.

    Saves the figure to outputs/network_<source>_to_<dest>_<pref>.png.

    Parameters
    ----------
    graph            : the road-network graph
    recommended_path : list of node labels for the best route
    preference       : user preference string (for title and filename)
    source           : source node label
    destination      : destination node label
    """
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.set_facecolor("#1a1a2e")
    fig.patch.set_facecolor("#1a1a2e")

    pos = NODE_POSITIONS

    # --- Draw all edges (background) ---
    nx.draw_networkx_edges(
        graph, pos,
        edge_color="#3a3a5c",
        width=2.5,
        ax=ax,
    )

    # --- Highlight recommended-route edges ---
    recommended_edges = [
        (recommended_path[i], recommended_path[i + 1])
        for i in range(len(recommended_path) - 1)
    ]
    nx.draw_networkx_edges(
        graph, pos,
        edgelist=recommended_edges,
        edge_color="#00d4aa",
        width=5.0,
        ax=ax,
        alpha=0.9,
    )

    # --- Node colouring ---
    node_colors = []
    for node in graph.nodes:
        if node == source:
            node_colors.append("#f72585")      # Bright pink for source
        elif node == destination:
            node_colors.append("#7209b7")      # Purple for destination
        elif node in recommended_path:
            node_colors.append("#00d4aa")      # Teal for route nodes
        else:
            node_colors.append("#4a4a7a")      # Dark for other nodes

    nx.draw_networkx_nodes(
        graph, pos,
        node_color=node_colors,
        node_size=700,
        ax=ax,
    )

    nx.draw_networkx_labels(
        graph, pos,
        font_color="white",
        font_size=13,
        font_weight="bold",
        ax=ax,
    )

    # --- Edge labels: show distance and congestion ---
    edge_labels = {
        (u, v): f"{d['distance_km']:.1f}km\ncong:{d['congestion']:.2f}"
        for u, v, d in graph.edges(data=True)
    }
    nx.draw_networkx_edge_labels(
        graph, pos,
        edge_labels=edge_labels,
        font_size=7,
        font_color="#cccccc",
        ax=ax,
        bbox={"boxstyle": "round,pad=0.2", "facecolor": "#2d2d4a", "alpha": 0.7},
    )

    # --- Legend ---
    legend_elements = [
        mpatches.Patch(color="#f72585",  label=f"Source ({source})"),
        mpatches.Patch(color="#7209b7",  label=f"Destination ({destination})"),
        mpatches.Patch(color="#00d4aa",  label=f"Recommended route ({preference})"),
        mpatches.Patch(color="#4a4a7a",  label="Other intersections"),
        mpatches.Patch(color="#3a3a5c",  label="Other roads"),
    ]
    ax.legend(
        handles=legend_elements,
        loc="lower left",
        facecolor="#2d2d4a",
        edgecolor="#5a5a8a",
        labelcolor="white",
        fontsize=9,
    )

    route_str = " -> ".join(recommended_path)
    ax.set_title(
        f"Sustainable Route Recommendation  |  {source} to {destination}\n"
        f"Profile: {preference.upper()}  |  Recommended: {route_str}\n"
        "(SIMULATED DATA - not real-world measurements)",
        color="white",
        fontsize=11,
        pad=14,
    )

    plt.tight_layout()
    filename = os.path.join(
        OUTPUT_DIR,
        f"network_{source}_to_{destination}_{preference}.png"
    )
    plt.savefig(filename, dpi=130, facecolor=fig.get_facecolor())
    plt.close()
    print(f"  Network plot saved to: {filename}")
    return filename


# ---------------------------------------------------------------------------
# Main program
# ---------------------------------------------------------------------------

def parse_arguments():
    """Parse optional command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "AI-Based Sustainable Route Recommendation System - Phase 1 Prototype\n"
            "All data is SIMULATED for academic prototyping purposes."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--source",
        default="A",
        help="Source intersection label (default: A). "
             "Available: A B C D E F G H",
    )
    parser.add_argument(
        "--dest",
        default="H",
        help="Destination intersection label (default: H). "
             "Available: A B C D E F G H",
    )
    parser.add_argument(
        "--preference",
        default="balanced",
        choices=list(PREFERENCE_PROFILES.keys()),
        help=(
            "User preference profile (default: balanced). "
            "Options: fastest | eco | balanced"
        ),
    )
    return parser.parse_args()


def main():
    args = parse_arguments()
    source      = args.source.upper()
    destination = args.dest.upper()
    preference  = args.preference.lower()

    ensure_output_dir()

    print_section(
        "AI-Based Sustainable Route Recommendation System  |  Phase 1 Prototype"
    )
    print(
        "\n  DISCLAIMER: All metrics use SYNTHETIC simulated data.\n"
        "  Results are for academic demonstration only.\n"
        "  Pollution exposure scoring: FUTURE EXTENSION (not implemented).\n"
    )
    print(f"  Source      : {source}")
    print(f"  Destination : {destination}")
    print(f"  Preference  : {preference.upper()}")

    # --- Step 1: Build graph ---
    graph = build_graph()

    # --- Step 2: Validate inputs ---
    try:
        validate_nodes(graph, source, destination)
    except ValueError as err:
        print(f"\n  ERROR: {err}")
        sys.exit(1)

    if not is_connected_path(graph, source, destination):
        print(
            f"\n  ERROR: No path exists between '{source}' and '{destination}'.\n"
            "  The road network may be disconnected for this pair."
        )
        sys.exit(1)

    # --- Step 3: Find all candidate routes and compute metrics ---
    print_section("Candidate Route Discovery")
    try:
        raw_routes = compute_all_routes(graph, source, destination)
    except ValueError as err:
        print(f"\n  ERROR: {err}")
        sys.exit(1)

    print(f"\n  Found {len(raw_routes)} candidate route(s) from {source} to {destination}.\n")

    # --- Step 4: Identify conventional baselines ---
    shortest_route   = find_shortest_distance_route(raw_routes)
    fastest_route    = find_fastest_time_route(raw_routes)

    # --- Step 5: Score routes for the chosen preference ---
    scored_routes = score_routes(raw_routes, preference)
    recommended   = scored_routes[0]

    # --- Step 6: Print results table ---
    print_section("Route Comparison Table")
    print_route_table(
        scored_routes,
        preference,
        shortest_dist_path = shortest_route["path_str"],
        fastest_time_path  = fastest_route["path_str"],
    )

    # --- Step 7: Baseline comparison ---
    print_baseline_comparison(
        raw_routes,
        shortest_route,
        fastest_route,
        recommended,
        preference,
    )

    # --- Step 8: Show scores for all three profiles (for comparison) ---
    print_section("Scores Under All Three Preference Profiles")
    print(
        "  This shows how the same routes rank differently depending on\n"
        "  the user preference — demonstrating configurable weighting.\n"
    )
    for pref in PREFERENCE_PROFILES:
        scored = score_routes(raw_routes, pref)
        best   = scored[0]
        print(
            f"  {pref.upper():<10}  Best route: {best['path_str']:<30}"
            f"  Score: {best['sustainability_score']:.4f}"
        )

    # --- Step 9: Export CSV ---
    print_section("Export")
    export_to_csv(scored_routes, preference, source, destination)

    # --- Step 10: Visualise ---
    visualise_network(
        graph,
        recommended_path = recommended["path"],
        preference       = preference,
        source           = source,
        destination      = destination,
    )

    print_section("Run Complete")
    print(
        f"\n  Recommended route ({preference.upper()}): "
        f"{recommended['path_str']}\n"
        f"  Sustainability Score : {recommended['sustainability_score']:.4f}\n"
        f"  Total Distance       : {recommended['distance_km']:.2f} km\n"
        f"  Est. Travel Time     : {recommended['travel_time_min']:.1f} min\n"
        f"  Est. Fuel Use        : {recommended['fuel_L']:.3f} L  (simulated)\n"
        f"  Est. CO2 Emissions   : {recommended['co2_kg']:.3f} kg (simulated)\n"
        f"  Avg. Congestion      : {recommended['avg_congestion']:.3f}\n"
    )
    print(
        "  All outputs saved to the 'outputs/' folder.\n"
        "  Next phase will add machine learning, a real road network, and a web UI.\n"
    )


if __name__ == "__main__":
    main()
