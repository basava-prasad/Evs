"""
sustainability.py
=================
Implements the Sustainability Score for Phase 1.

How the score works
-------------------
Each candidate route has four numeric metrics:
  1. travel_time_min  (lower is better)
  2. fuel_L           (lower is better)
  3. co2_kg           (lower is better)
  4. avg_congestion   (lower is better)

Step 1 - Normalise each metric to [0, 1].
  For metrics where lower is better we invert after normalising so that
  a value of 1.0 always means "best" and 0.0 means "worst".

  raw_normalised = (value - min_value) / (max_value - min_value)

  If all routes have the same value for a metric (max == min), every
  route receives a normalised score of 1.0 for that metric, meaning
  the metric does not differentiate between routes.

  After raw normalisation, inverted_score = 1 - raw_normalised.

Step 2 - Weighted sum.
  sustainability_score = sum(weight_i * inverted_score_i)

  Weights are defined by a preference profile and must sum to 1.0.
  Higher sustainability_score = better route for that preference.

Step 3 - Rank routes.
  Routes are sorted by sustainability_score descending; the first
  route in the sorted list is the recommended one.

Preference profiles
-------------------
Three built-in profiles balance the four metrics differently:

  "fastest"   : prioritises travel time heavily
  "eco"       : prioritises fuel and CO2 equally; deprioritises time
  "balanced"  : equal weight across all four metrics

Users can also supply a custom weight dict to override the profiles.

Pollution exposure
------------------
Pollution exposure is listed as a future extension. When integrated it
will be added as a fifth metric with its own weight, and the existing
weights will be adjusted to maintain sum == 1.0.
"""

# ---------------------------------------------------------------------------
# Built-in preference profiles
# Keys must match the metric names used in compute_route_metrics()
# ---------------------------------------------------------------------------
PREFERENCE_PROFILES = {
    "fastest": {
        "travel_time_min": 0.60,
        "fuel_L"         : 0.15,
        "co2_kg"         : 0.15,
        "avg_congestion" : 0.10,
    },
    "eco": {
        "travel_time_min": 0.10,
        "fuel_L"         : 0.40,
        "co2_kg"         : 0.40,
        "avg_congestion" : 0.10,
    },
    "balanced": {
        "travel_time_min": 0.25,
        "fuel_L"         : 0.25,
        "co2_kg"         : 0.25,
        "avg_congestion" : 0.25,
    },
}

METRICS_TO_SCORE = ["travel_time_min", "fuel_L", "co2_kg", "avg_congestion"]


def _validate_weights(weights: dict) -> None:
    """
    Check that all required metric keys are present in weights and
    that the values are non-negative and sum to approximately 1.0.

    Raises ValueError with a descriptive message if validation fails.
    """
    for key in METRICS_TO_SCORE:
        if key not in weights:
            raise ValueError(
                f"Weight dictionary is missing key '{key}'. "
                f"Required keys: {METRICS_TO_SCORE}"
            )
        if weights[key] < 0:
            raise ValueError(
                f"Weight for '{key}' is negative ({weights[key]}). "
                "All weights must be >= 0."
            )

    total = sum(weights[k] for k in METRICS_TO_SCORE)
    if abs(total - 1.0) > 1e-6:
        raise ValueError(
            f"Weights must sum to 1.0, but they sum to {total:.6f}. "
            f"Received weights: {weights}"
        )


def get_weights(preference: str, custom_weights: dict = None) -> dict:
    """
    Return the weight dictionary for the given preference string,
    or validate and return custom_weights if supplied.

    Parameters
    ----------
    preference     : one of "fastest", "eco", "balanced"
    custom_weights : optional dict overriding the built-in profiles

    Returns
    -------
    dict
        Validated weight dictionary.

    Raises
    ------
    ValueError
        If preference is unrecognised or weights are invalid.
    """
    if custom_weights is not None:
        _validate_weights(custom_weights)
        return custom_weights

    preference_lower = preference.lower()
    if preference_lower not in PREFERENCE_PROFILES:
        valid = list(PREFERENCE_PROFILES.keys())
        raise ValueError(
            f"Unknown preference '{preference}'. "
            f"Valid options are: {valid}"
        )

    return PREFERENCE_PROFILES[preference_lower]


def normalise_metrics(routes: list) -> list:
    """
    Add a 'normalised' sub-dict to each route containing inverted
    normalised scores for each metric (1.0 = best, 0.0 = worst).

    This function does NOT modify the original metric values.

    Parameters
    ----------
    routes : list of route-metrics dicts (from compute_all_routes)

    Returns
    -------
    list of dicts
        Same routes, each augmented with a 'normalised' key.
    """
    for metric in METRICS_TO_SCORE:
        values     = [r[metric] for r in routes]
        min_val    = min(values)
        max_val    = max(values)
        value_range = max_val - min_val

        for route in routes:
            if "normalised" not in route:
                route["normalised"] = {}

            if value_range == 0:
                # All routes identical for this metric -> neutral score
                route["normalised"][metric] = 1.0
            else:
                raw = (route[metric] - min_val) / value_range
                # Invert: lower raw value is better, so higher inverted score
                route["normalised"][metric] = round(1.0 - raw, 6)

    return routes


def compute_sustainability_scores(routes: list, weights: dict) -> list:
    """
    Compute and attach a sustainability_score to each route.

    Score formula:
      score = sum(weight_i * normalised_score_i  for each metric i)

    Higher score = better route for the chosen preference profile.

    Parameters
    ----------
    routes  : list of route dicts that already have a 'normalised' key
              (i.e. normalise_metrics() must be called first)
    weights : validated weight dictionary

    Returns
    -------
    list of dicts
        Routes sorted by sustainability_score descending (best first).
    """
    for route in routes:
        score = sum(
            weights[metric] * route["normalised"][metric]
            for metric in METRICS_TO_SCORE
        )
        route["sustainability_score"] = round(score, 6)
        route["weights_used"]         = weights

    # Sort best-first
    routes_sorted = sorted(routes, key=lambda r: r["sustainability_score"], reverse=True)
    return routes_sorted


def score_routes(routes: list, preference: str,
                 custom_weights: dict = None) -> list:
    """
    Convenience wrapper: validate weights, normalise metrics, compute
    scores, and return routes sorted best-first.

    Parameters
    ----------
    routes         : raw route dicts from compute_all_routes()
    preference     : "fastest", "eco", or "balanced"
    custom_weights : optional override dict

    Returns
    -------
    list of dicts
        Routes with sustainability_score added, sorted best-first.
    """
    # Work on a shallow copy so the original list is not mutated
    import copy
    routes_copy = copy.deepcopy(routes)

    weights = get_weights(preference, custom_weights)
    routes_copy = normalise_metrics(routes_copy)
    routes_sorted = compute_sustainability_scores(routes_copy, weights)
    return routes_sorted
