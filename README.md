# AI-Based Sustainable Route Recommendation System
## EcoRoute AI — Web Dashboard (Phase 1 Prototype)

> **Academic project — Phase 1 prototype.**
> All fuel/CO2/congestion metrics are computed from SYNTHETIC estimates.
> ML-based scoring is a **pending future extension** (not yet implemented).
> Road geometry in Real Map mode: OpenStreetMap © contributors (ODbL).

---

## Quick Start (Windows PowerShell)

### 1. Activate the virtual environment

```powershell
.venv\Scripts\Activate.ps1
```

### 2. Install dependencies (already done, run only if needed)

```powershell
pip install -r requirements.txt
```

### 3. Start the web dashboard

```powershell
python app.py
```

Then open your browser and go to: **http://127.0.0.1:5000**

### 4. Run the terminal prototype (Phase 1 CLI, still works)

```powershell
python main.py --source A --dest H --preference eco
```

### 5. Run automated tests

```powershell
python tests\test_phase1.py
```

---

## Project structure

```
sustainable-route-system/
|-- app.py                Flask backend (web dashboard entry point)
|-- main.py               Terminal prototype (Phase 1 CLI)
|-- simulation_data.py    Synthetic 8-node road network data
|-- road_network.py       NetworkX graph builder
|-- route_optimizer.py    Route finding and metric computation
|-- sustainability.py     Scoring, normalisation, preference profiles
|-- osm_network.py        OSMnx real road network integration
|-- requirements.txt      Python dependencies
|-- templates/
|   `-- index.html        Dashboard HTML (Leaflet map, route cards)
|-- static/
|   |-- style.css         Dark-mode premium CSS
|   `-- app.js            Frontend JS (map, API calls, rendering)
|-- tests/
|   `-- test_phase1.py    21 automated validation tests
`-- outputs/              CSV exports and PNG plots from CLI mode
```

---

## Two modes

### Simulated Mode (always available, no internet needed)
- Uses the synthetic 8-node graph from simulation_data.py
- Instant results, great for offline demos
- Select nodes A–H from the dropdown

### Real Map Mode (requires internet access)
- Downloads road network from OpenStreetMap via OSMnx
- Click the map twice to set Origin and Destination
- May take 5–30 seconds to fetch data
- Road geometry is real; fuel/CO2/congestion values are still synthetic estimates

---

## Sustainability Score formula

```
score = w_time * norm(time) + w_fuel * norm(fuel) + w_co2 * norm(co2) + w_cong * norm(congestion)
```

All metrics normalised to [0,1] (inverted: 1.0 = best). Weights sum to 1.0.

| Profile  | Time | Fuel | CO2  | Congestion |
|----------|------|------|------|------------|
| Fastest  | 60%  | 15%  | 15%  | 10%        |
| Eco      | 10%  | 40%  | 40%  | 10%        |
| Balanced | 25%  | 25%  | 25%  | 25%        |

---

## What works now

| Feature                              | Status |
|--------------------------------------|--------|
| Flask web dashboard                  | ✅ Working |
| Leaflet.js interactive map (OSM)     | ✅ Working |
| Simulated mode (8-node graph)        | ✅ Working |
| Real mode (OSMnx + OpenStreetMap)    | ✅ Working (internet needed) |
| Route cards with all metrics         | ✅ Working |
| 3 preference profiles                | ✅ Working |
| Baseline comparison table            | ✅ Working |
| Score weight breakdown               | ✅ Working |
| Click-to-set map pins (real mode)    | ✅ Working |
| Terminal CLI (main.py)               | ✅ Working |
| 21 automated tests (all pass)        | ✅ Working |
| CSV export (CLI only)                | ✅ Working |

## Pending (not yet implemented)

- ML-based scoring (Random Forest / XGBoost) — training data needed
- Pollution exposure scoring — air quality API pending
- Electric vehicle battery model
- Live traffic data (no free real-time API identified without key)

---

## Fuel and CO2 formulas (transparent)

```
fuel_L = distance_km * 0.08 * (1 + congestion)
co2_kg = fuel_L * 2.31
```

Source: DEFRA/BEIS GHG Conversion Factors 2023. Generic petrol car assumed.
