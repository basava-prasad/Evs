/**
 * app.js  —  EcoRoute AI Frontend Logic
 * ======================================
 * Handles:
 *   - Leaflet map initialisation and route drawing
 *   - Simulated mode: node dropdowns -> /api/route/simulated
 *   - Real map mode: click-to-pick / coord inputs -> /api/route/real
 *   - Results rendering: route cards, comparison table, score bar
 *   - Error display and loading state
 */

/* ──────────────────────────────────────────────
   STATE
────────────────────────────────────────────── */
let currentMode = "sim";          // "sim" | "real"
let currentPref = "fastest";      // "fastest" | "eco" | "balanced"
let clickPhase  = 0;              // 0=pick origin, 1=pick dest (real mode)
let originMarker = null;
let destMarker   = null;
let routeLayers  = [];            // All polylines currently on the map
let focusedRouteIdx = -1;         // Index of currently focused route card

/* ──────────────────────────────────────────────
   MAP SETUP
────────────────────────────────────────────── */
const map = L.map("map", {
  center: [12.9716, 77.5946],     // Bengaluru centre
  zoom: 13,
  zoomControl: true,
});

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "&copy; <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a> contributors",
  maxZoom: 19,
}).addTo(map);

// Custom marker icons
function makeIcon(color) {
  return L.divIcon({
    className: "",
    html: `<div style="width:18px;height:18px;border-radius:50%;background:${color};border:3px solid white;box-shadow:0 2px 8px rgba(0,0,0,0.5);"></div>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9],
  });
}

const iconOrigin = makeIcon("#f72585");
const iconDest   = makeIcon("#7c3aed");

// Click handler for real-map mode
map.on("click", function (e) {
  if (currentMode !== "real") return;
  const {lat, lng} = e.latlng;

  if (clickPhase === 0) {
    if (originMarker) map.removeLayer(originMarker);
    originMarker = L.marker([lat, lng], {icon: iconOrigin})
      .addTo(map)
      .bindPopup("Origin")
      .openPopup();
    document.getElementById("orig-lat").value = lat.toFixed(6);
    document.getElementById("orig-lon").value = lng.toFixed(6);
    clickPhase = 1;
    showMapHint("Now click to set your <strong>Destination</strong>");
  } else {
    if (destMarker) map.removeLayer(destMarker);
    destMarker = L.marker([lat, lng], {icon: iconDest})
      .addTo(map)
      .bindPopup("Destination")
      .openPopup();
    document.getElementById("dest-lat").value = lat.toFixed(6);
    document.getElementById("dest-lon").value = lng.toFixed(6);
    clickPhase = 0;
    showMapHint("Both points set. Click <strong>Calculate Routes</strong>.");
  }
});

function showMapHint(msg) {
  // show a brief floating hint on the map
  const div = document.getElementById("map-hint") || (() => {
    const d = document.createElement("div");
    d.id = "map-hint";
    d.style.cssText = "position:absolute;top:12px;left:50%;transform:translateX(-50%);z-index:1000;background:rgba(10,14,26,.9);color:#f1f5f9;padding:8px 18px;border-radius:20px;font-size:.85rem;border:1px solid rgba(255,255,255,.15);pointer-events:none;transition:opacity .4s;";
    document.querySelector(".map-section").appendChild(d);
    return d;
  })();
  div.innerHTML = msg;
  div.style.opacity = "1";
  clearTimeout(div._timer);
  div._timer = setTimeout(() => { div.style.opacity = "0"; }, 3500);
}

/* ──────────────────────────────────────────────
   MODE & PREFERENCE CONTROLS
────────────────────────────────────────────── */
function setMode(mode) {
  currentMode = mode;
  document.getElementById("sim-inputs").classList.toggle("hidden", mode !== "sim");
  document.getElementById("real-inputs").classList.toggle("hidden", mode !== "real");
  document.getElementById("btn-sim").classList.toggle("active", mode === "sim");
  document.getElementById("btn-real").classList.toggle("active", mode === "real");

  if (mode === "real" && clickPhase === 0) {
    showMapHint("Click the map to set your <strong>Origin</strong>");
  }
}

function selectPref(el) {
  document.querySelectorAll(".pref-card").forEach(c => c.classList.remove("active"));
  el.classList.add("active");
  currentPref = el.dataset.pref;
}

function swapSimNodes() {
  const s = document.getElementById("sim-source");
  const d = document.getElementById("sim-dest");
  const tmp = s.value; s.value = d.value; d.value = tmp;
}

function swapRealCoords() {
  const swap = (a, b) => { const t = a.value; a.value = b.value; b.value = t; };
  swap(document.getElementById("orig-lat"), document.getElementById("dest-lat"));
  swap(document.getElementById("orig-lon"), document.getElementById("dest-lon"));
  if (originMarker && destMarker) {
    const op = originMarker.getLatLng();
    const dp = destMarker.getLatLng();
    originMarker.setLatLng(dp);
    destMarker.setLatLng(op);
  }
}

/* ──────────────────────────────────────────────
   ROUTE CALCULATION
────────────────────────────────────────────── */
async function calculateRoutes() {
  hideError();
  setLoading(true);
  clearMapRoutes();

  try {
    let data;
    if (currentMode === "sim") {
      data = await callSimulated();
    } else {
      data = await callReal();
    }
    renderResults(data);
    drawRoutes(data.routes, data.sim_node_coords || null);
  } catch (err) {
    showError(err.message || "An unexpected error occurred.");
  } finally {
    setLoading(false);
  }
}

async function callSimulated() {
  const source = document.getElementById("sim-source").value;
  const dest   = document.getElementById("sim-dest").value;

  const resp = await fetch("/api/route/simulated", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({source, destination: dest, preference: currentPref}),
  });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.error || `Server error ${resp.status}`);
  return data;
}

async function callReal() {
  const lat1 = parseFloat(document.getElementById("orig-lat").value);
  const lon1 = parseFloat(document.getElementById("orig-lon").value);
  const lat2 = parseFloat(document.getElementById("dest-lat").value);
  const lon2 = parseFloat(document.getElementById("dest-lon").value);

  if ([lat1,lon1,lat2,lon2].some(isNaN)) {
    throw new Error("Please set both Origin and Destination coordinates (click the map or type them in).");
  }
  if (lat1 === lat2 && lon1 === lon2) {
    throw new Error("Origin and Destination are the same point. Please choose two different locations.");
  }

  const resp = await fetch("/api/route/real", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({origin_lat: lat1, origin_lon: lon1, dest_lat: lat2, dest_lon: lon2, preference: currentPref}),
  });
  const data = await resp.json();
  if (!resp.ok) {
    const hint = data.hint ? ` ${data.hint}` : "";
    throw new Error((data.error || `Server error ${resp.status}`) + hint);
  }
  return data;
}

/* ──────────────────────────────────────────────
   MAP DRAWING
────────────────────────────────────────────── */
const ROUTE_COLORS = {
  recommended : "#00d4aa",
  shortest    : "#f59e0b",
  fastest     : "#3b82f6",
  other       : ["#6366f1", "#ec4899", "#8b5cf6", "#14b8a6", "#f43f5e"],
};

function clearMapRoutes() {
  routeLayers.forEach(l => map.removeLayer(l));
  routeLayers = [];
}

function drawRoutes(routes, simNodeCoords) {
  clearMapRoutes();
  const bounds = [];
  let otherIdx = 0;

  // Draw non-recommended first so the recommended is on top
  const ordered = [...routes].sort((a,b) => (b.is_recommended ? -1 : 1));

  ordered.forEach((route, i) => {
    const coords = route.coordinates;
    if (!coords || coords.length < 2) return;

    let color, weight, opacity, dashArray;
    if (route.is_recommended) {
      color = ROUTE_COLORS.recommended; weight = 6; opacity = 0.95; dashArray = null;
    } else if (route.is_shortest) {
      color = ROUTE_COLORS.shortest;    weight = 4; opacity = 0.80; dashArray = "8,6";
    } else if (route.is_fastest) {
      color = ROUTE_COLORS.fastest;     weight = 4; opacity = 0.80; dashArray = "8,6";
    } else {
      color = ROUTE_COLORS.other[otherIdx % ROUTE_COLORS.other.length];
      otherIdx++; weight = 2.5; opacity = 0.45; dashArray = "4,8";
    }

    const line = L.polyline(coords, {color, weight, opacity, dashArray})
      .addTo(map)
      .bindPopup(buildPopupHTML(route));

    routeLayers.push(line);
    coords.forEach(c => bounds.push(c));

    // Store reference on route for focus
    route._layer = line;
  });

  // Add simulated node markers
  if (simNodeCoords) {
    Object.entries(simNodeCoords).forEach(([label, [lat, lon]]) => {
      const marker = L.circleMarker([lat, lon], {
        radius: 7, color: "#1e293b", fillColor: "#94a3b8",
        fillOpacity: 1, weight: 2,
      }).addTo(map).bindPopup(`<b>Node ${label}</b>`);
      routeLayers.push(marker);
      bounds.push([lat, lon]);
    });
  }

  if (bounds.length > 0) {
    map.fitBounds(bounds, {padding: [40, 40]});
  }
}

function buildPopupHTML(route) {
  const tags = [];
  if (route.is_recommended) tags.push('<span style="color:#e74c3c;font-weight:700;">Recommended</span>');
  if (route.is_shortest)    tags.push('<span style="color:#b45309;font-weight:700;">Shortest</span>');
  if (route.is_fastest)     tags.push('<span style="color:#1d4ed8;font-weight:700;">Fastest</span>');

  return `
    <div style="font-family:Inter,sans-serif;min-width:200px;">
      <div style="font-weight:700;font-size:0.9rem;margin-bottom:6px;">${route.path_str}</div>
      ${tags.length ? `<div style="margin-bottom:8px;font-size:0.75rem;">${tags.join(" &bull; ")}</div>` : ""}
      <table style="width:100%;font-size:0.82rem;border-collapse:collapse;">
        <tr><td style="padding:2px 6px 2px 0;color:#94a3b8;">Distance</td><td><b>${route.distance_km} km</b></td></tr>
        <tr><td style="padding:2px 6px 2px 0;color:#94a3b8;">Time (est)</td><td><b>${route.travel_time_min} min</b></td></tr>
        <tr><td style="padding:2px 6px 2px 0;color:#94a3b8;">Fuel</td><td><b>${route.fuel_L} L</b></td></tr>
        <tr><td style="padding:2px 6px 2px 0;color:#94a3b8;">CO&#8322;</td><td><b>${route.co2_kg} kg</b></td></tr>
        <tr><td style="padding:2px 6px 2px 0;color:#94a3b8;">Congestion</td><td><b>${(route.avg_congestion * 100).toFixed(0)}%</b></td></tr>
        <tr><td style="padding:2px 6px 2px 0;color:#94a3b8;">Score</td><td><b style="color:#e74c3c;">${route.sustainability_score.toFixed(4)}</b></td></tr>
      </table>
      <div style="margin-top:8px;font-size:0.7rem;color:#64748b;font-style:italic;">${route.traffic_note}</div>
    </div>
  `;
}

function focusRoute(idx) {
  if (routeLayers[idx]) {
    routeLayers[idx].openPopup();
    map.panTo(routeLayers[idx].getLatLngs()[0]);
  }
}

/* ──────────────────────────────────────────────
   RESULTS RENDERING
────────────────────────────────────────────── */
const PREF_WEIGHTS = {
  fastest  : {travel_time_min: 0.60, fuel_L: 0.15, co2_kg: 0.15, avg_congestion: 0.10},
  eco      : {travel_time_min: 0.10, fuel_L: 0.40, co2_kg: 0.40, avg_congestion: 0.10},
  balanced : {travel_time_min: 0.25, fuel_L: 0.25, co2_kg: 0.25, avg_congestion: 0.25},
};

function renderResults(data) {
  document.getElementById("results-placeholder").classList.add("hidden");
  document.getElementById("results-content").classList.remove("hidden");

  // Data mode badge
  const badge = document.getElementById("data-mode-badge");
  if (data.mode === "real") {
    badge.textContent = "Real OSM Data";
    badge.className = "data-badge real";
  } else {
    badge.textContent = "Simulated Data";
    badge.className = "data-badge sim";
  }

  // Recommended hero
  const rec = data.routes.find(r => r.is_recommended) || data.routes[0];
  renderHero(rec, data.preference);

  // Route cards
  const grid = document.getElementById("routes-grid");
  grid.innerHTML = "";
  data.routes.forEach((route, idx) => {
    grid.appendChild(buildRouteCard(route, idx));
  });

  // Comparison table
  renderComparisonTable(data.baseline);

  // Weight breakdown
  renderWeights(data.preference || currentPref);

  // Scroll to results
  setTimeout(() => {
    document.getElementById("results").scrollIntoView({behavior:"smooth", block:"start"});
  }, 200);
}

function renderHero(rec, pref) {
  const hero = document.getElementById("rec-hero");
  const scorePercent = (rec.sustainability_score * 100).toFixed(1);

  hero.innerHTML = `
    <div style="flex:1;min-width:200px;">
      <div class="rec-title">Recommended Route &mdash; ${(pref || currentPref).toUpperCase()} Preference</div>
      <div class="rec-route">${rec.path_str}</div>
      <div class="rec-metrics">
        ${metricPill("Distance", rec.distance_km + " km", "#00d4aa")}
        ${metricPill("Travel Time", rec.travel_time_min + " min", "#a78bfa")}
        ${metricPill("Fuel", rec.fuel_L + " L", "#f59e0b")}
        ${metricPill("CO&#8322;", rec.co2_kg + " kg", "#10b981")}
        ${metricPill("Congestion", (rec.avg_congestion * 100).toFixed(0) + "%", "#94a3b8")}
      </div>
      <div style="margin-top:12px;font-size:0.78rem;color:#64748b;font-style:italic;">
        ${rec.data_source} &bull; ${rec.traffic_note}
      </div>
      <div style="margin-top:6px;font-size:0.75rem;color:#fbbf24;">
        Note: ${rec.ml_note}
      </div>
    </div>
    <div class="score-circle">
      <div class="score-val">${scorePercent}%</div>
      <div class="score-label">Score</div>
    </div>
  `;
}

function metricPill(label, value, color) {
  return `
    <div class="rec-metric">
      <div class="rec-metric-val" style="color:${color};">${value}</div>
      <div class="rec-metric-label">${label}</div>
    </div>
  `;
}

function buildRouteCard(route, idx) {
  const card = document.createElement("div");
  const classes = ["route-card"];
  if (route.is_recommended) classes.push("recommended-card");
  else if (route.is_shortest) classes.push("shortest-card");
  else if (route.is_fastest)  classes.push("fastest-card");
  card.className = classes.join(" ");

  const badges = [];
  if (route.is_recommended) badges.push('<span class="badge rec">Recommended</span>');
  if (route.is_shortest)    badges.push('<span class="badge short">Shortest</span>');
  if (route.is_fastest)     badges.push('<span class="badge fast">Fastest</span>');

  const pct = (route.sustainability_score * 100).toFixed(1);
  const congPct = (route.avg_congestion * 100).toFixed(0);

  card.innerHTML = `
    <div class="card-rank">#${route.rank}</div>
    <div class="card-badges">${badges.join("")}</div>
    <div class="card-route">${route.path_str}</div>
    <div class="card-metrics">
      ${cardMetric(route.distance_km + " km", "Distance")}
      ${cardMetric(route.travel_time_min + " min", "Travel Time (est)")}
      ${cardMetric(route.fuel_L + " L", "Fuel (synthetic)")}
      ${cardMetric(route.co2_kg + " kg", "CO&#8322; (synthetic)")}
      ${cardMetric(congPct + "%", "Avg Congestion")}
      ${cardMetric(route.sustainability_score.toFixed(4), "Sust. Score")}
    </div>
    <div class="card-score-bar">
      <div class="score-bar-bg">
        <div class="score-bar-fill" style="width:${pct}%;"></div>
      </div>
      <div class="score-text">${pct}%</div>
    </div>
    <div class="card-note">${route.traffic_note}</div>
    <button class="focus-btn" onclick="focusRouteOnMap(${idx})">Focus on Map</button>
  `;
  return card;
}

function cardMetric(val, label) {
  return `<div class="metric-item"><div class="metric-val">${val}</div><div class="metric-label">${label}</div></div>`;
}

function focusRouteOnMap(cardIdx) {
  // routeLayers are ordered: non-recommended first, then recommended
  // Find the matching layer by searching
  document.querySelector(".map-section").scrollIntoView({behavior:"smooth"});
  setTimeout(() => {
    if (routeLayers[cardIdx]) {
      routeLayers[cardIdx].openPopup();
    }
  }, 400);
}

function renderComparisonTable(baseline) {
  if (!baseline) return;
  const tbody = document.getElementById("comparison-tbody");
  tbody.innerHTML = "";

  const rows = [
    {label: "Shortest Distance", dot: "#b45309", cls: "row-shortest",    route: baseline.shortest},
    {label: "Fastest Time",      dot: "#1d4ed8", cls: "row-fastest",     route: baseline.fastest},
    {label: "AI Recommended",   dot: "#c0392b", cls: "row-recommended", route: baseline.recommended},
  ];

  rows.forEach(({label, dot, cls, route}) => {
    if (!route) return;
    const tr = document.createElement("tr");
    tr.className = cls;
    tr.innerHTML = `
      <td><div class="method-label"><span class="method-dot" style="background:${dot};"></span>${label}</div></td>
      <td style="font-family:'Courier New',monospace;font-size:0.82rem;">${route.path_str}</td>
      <td>${route.distance_km}</td>
      <td>${route.travel_time_min}</td>
      <td>${route.fuel_L}</td>
      <td>${route.co2_kg}</td>
      <td>${(route.avg_congestion * 100).toFixed(0)}%</td>
      <td style="color:#e74c3c;font-weight:700;">${route.sustainability_score ? route.sustainability_score.toFixed(4) : "—"}</td>
    `;
    tbody.appendChild(tr);
  });
}

function renderWeights(pref) {
  const weights = PREF_WEIGHTS[pref] || PREF_WEIGHTS.balanced;
  const el = document.getElementById("weight-breakdown");
  el.innerHTML = "";

  const COLORS = {
    travel_time_min : "#a78bfa",
    fuel_L          : "#f59e0b",
    co2_kg          : "#10b981",
    avg_congestion  : "#94a3b8",
  };
  const LABELS = {
    travel_time_min : "Travel Time",
    fuel_L          : "Fuel",
    co2_kg          : "CO&#8322; Emissions",
    avg_congestion  : "Congestion",
  };

  Object.entries(weights).forEach(([key, w]) => {
    const pct = (w * 100).toFixed(0);
    const div = document.createElement("div");
    div.className = "weight-item";
    div.innerHTML = `
      <div class="weight-name">${LABELS[key]}</div>
      <div class="weight-bar-bg">
        <div class="weight-bar-fill" style="width:${pct}%;background:${COLORS[key]};"></div>
      </div>
      <div class="weight-pct">${pct}%</div>
    `;
    el.appendChild(div);
  });
}

/* ──────────────────────────────────────────────
   UI UTILITIES
────────────────────────────────────────────── */
function setLoading(on) {
  const btn   = document.getElementById("calc-btn");
  const label = document.getElementById("calc-label");
  const spin  = document.getElementById("calc-spinner");
  btn.disabled = on;
  label.classList.toggle("hidden", on);
  spin.classList.toggle("hidden", !on);
}

function showError(msg) {
  const el = document.getElementById("error-banner");
  el.textContent = "Error: " + msg;
  el.classList.remove("hidden");
}

function hideError() {
  document.getElementById("error-banner").classList.add("hidden");
}
