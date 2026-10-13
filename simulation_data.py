# simulation_data.py
# ==================
# Contains the SIMULATED road-network data for Phase 1 of the
# AI-Based Sustainable Route Recommendation System.
#
# IMPORTANT - DATA DISCLAIMER
# -----------------------------
# All values in this file are SYNTHETIC. They were chosen to be
# plausible for a small urban road network but do NOT represent any
# real city or real-world measurements. Labels like "speed_kmh" and
# "congestion" are simulated proxies, not live sensor readings.
#
# When real OpenStreetMap / OSMnx data is integrated in a later phase,
# this file can be replaced by a loader that reads from that source.
# The rest of the codebase treats the graph as a plain NetworkX object,
# so the swap requires changing only this file.
#
# Graph layout (node names are intersection labels)
# --------------------------------------------------
#          A
#         / \
#        B   C
#       / \ / \
#      D   E   F
#       \ /   /
#        G---H
#
# Nodes  = road intersections.
# Edges  = road segments with attributes:
#   distance_km  - length of the segment in kilometres
#   speed_kmh    - free-flow speed limit in km/h
#   congestion   - simulated level 0.0 (clear) to 1.0 (gridlock)
#
# Effective speed formula:
#   effective_speed = speed_kmh * (1 - 0.7 * congestion)
# At full congestion (1.0) the road is passable at 30% of its speed limit.

# ---------------------------------------------------------------------------
# Node definitions
# Each node is an intersection with a human-readable label.
# ---------------------------------------------------------------------------
NODES = [
    "A",   # Starting neighbourhood hub
    "B",   # Residential junction
    "C",   # Commercial area junction
    "D",   # Industrial zone junction
    "E",   # Central crossroads
    "F",   # Ring-road junction
    "G",   # South-west exit
    "H",   # South-east exit
]

# ---------------------------------------------------------------------------
# Edge definitions
# Each tuple is: (from_node, to_node, attributes_dict)
# Roads are UNDIRECTED - traffic can flow in both directions.
# ---------------------------------------------------------------------------
EDGES = [
    # (source, target, {distance_km, speed_kmh, congestion})

    # --- Top section: A <-> B, A <-> C ---
    ("A", "B", {"distance_km": 2.0,  "speed_kmh": 50,  "congestion": 0.2}),
    ("A", "C", {"distance_km": 2.5,  "speed_kmh": 60,  "congestion": 0.1}),

    # --- Middle section: B <-> D, B <-> E, C <-> E, C <-> F ---
    ("B", "D", {"distance_km": 3.0,  "speed_kmh": 40,  "congestion": 0.6}),
    ("B", "E", {"distance_km": 2.8,  "speed_kmh": 50,  "congestion": 0.4}),
    ("C", "E", {"distance_km": 1.5,  "speed_kmh": 60,  "congestion": 0.3}),
    ("C", "F", {"distance_km": 3.5,  "speed_kmh": 70,  "congestion": 0.2}),

    # --- Bottom section: D <-> G, E <-> G, F <-> H ---
    ("D", "G", {"distance_km": 1.8,  "speed_kmh": 40,  "congestion": 0.5}),
    ("E", "G", {"distance_km": 2.2,  "speed_kmh": 50,  "congestion": 0.35}),
    ("F", "H", {"distance_km": 2.0,  "speed_kmh": 70,  "congestion": 0.15}),

    # --- Connector: G <-> H ---
    ("G", "H", {"distance_km": 1.2,  "speed_kmh": 40,  "congestion": 0.45}),

    # --- Extra connectors to ensure multiple paths exist between far nodes ---
    ("E", "F", {"distance_km": 2.0,  "speed_kmh": 55,  "congestion": 0.25}),
    ("D", "E", {"distance_km": 1.5,  "speed_kmh": 40,  "congestion": 0.55}),
]

# ---------------------------------------------------------------------------
# Fuel / Emissions baseline assumptions
# ---------------------------------------------------------------------------
# These constants define the simple formula used to estimate fuel use and CO2.
# They are intentionally transparent so any academic reviewer can scrutinise them.
#
# Formula (per road segment):
#   base_fuel_L         = distance_km * FUEL_CONSUMPTION_L_PER_KM
#   congestion_penalty  = 1 + CONGESTION_FUEL_MULTIPLIER * congestion
#   segment_fuel_L      = base_fuel_L * congestion_penalty
#   segment_co2_kg      = segment_fuel_L * CO2_KG_PER_LITRE_PETROL
#
# Assumptions and limitations:
#   1. Assumes a generic petrol passenger car.
#   2. Base consumption (0.08 L/km) corresponds to roughly 80 ml/km,
#      typical for a compact petrol car at steady speed.
#   3. Congestion increases fuel use: stop-start driving at congestion=1.0
#      roughly doubles consumption (multiplier factor up to 2.0).
#   4. CO2 factor (2.31 kg/L) is the standard IPCC/DEFRA value for petrol.
#   5. No cold-start penalty, no road gradient, no vehicle load modelled.
#   6. Electric-vehicle support is a planned future extension.
#
# Source references for the constants:
#   - DEFRA / BEIS GHG Conversion Factors 2023 (2.31 kg CO2 per litre petrol)
#   - IEA data on average passenger car fuel economy
# ---------------------------------------------------------------------------

FUEL_CONSUMPTION_L_PER_KM = 0.08      # Base fuel use: litres per kilometre
CONGESTION_FUEL_MULTIPLIER = 1.0       # At congestion=1.0, fuel cost doubles
CO2_KG_PER_LITRE_PETROL    = 2.31     # kg of CO2 emitted per litre of petrol

# Congestion effect on speed: effective_speed = speed * (1 - factor * congestion)
CONGESTION_SPEED_FACTOR    = 0.7      # 70 % speed reduction at full congestion
