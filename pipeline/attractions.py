"""
pipeline/attractions.py
Attraction-specific configurations for per-engagement commuter arbitrage scoring.

Each attraction carries anchor_weights — a subjective mapping from CT economic
anchors (Hartford, New Haven, Stamford, Bridgeport) to relevance for that
attraction's catchment area.  Weights reflect judgment about which anchor
corridors share meaningful geographic overlap with the attraction's visitor draw;
they are documented as methodology inputs, not empirically calibrated values.

Weights are 0–1.  0 = anchor corridor is irrelevant; 1 = primary corridor.
Fractional weights represent partial catchment overlap.

Usage:
    from pipeline.attractions import weighted_flow
    df["sci_ctr_flow"] = weighted_flow(df, "ct_science_center")

Serves: Post #5 (Commuter Arbitrage), future per-attraction engagement reports.
"""

from __future__ import annotations

import pandas as pd

# Column names for the four anchor inbound-flow columns (from LODES data).
ANCHOR_COLS: dict[str, str] = {
    "hartford":   "inbound_to_hartford",
    "new_haven":  "inbound_to_new_haven",
    "stamford":   "inbound_to_stamford",
    "bridgeport": "inbound_to_bridgeport",
}

ATTRACTIONS: dict[str, dict] = {
    # ── Hartford corridor ─────────────────────────────────────────────────────
    "ct_science_center": {
        "display_name": "CT Science Center",
        "name": "CT Science Center",
        "town": "Hartford",
        "county": "Hartford",
        "lat": 41.7659,
        "lon": -72.6693,
        "primary_anchor": "hartford",
        # Weights: Hartford=primary; New Haven=secondary (I-91 corridor);
        # Stamford/Bridgeport=irrelevant (Fairfield County corridor).
        # These weights are subjective defaults — documented as methodology inputs.
        "anchor_weights": {
            "hartford":   1.0,
            "new_haven":  0.3,
            "stamford":   0.0,
            "bridgeport": 0.0,
        },
    },
    "mark_twain_house": {
        "display_name": "Mark Twain House",
        "name": "Mark Twain House & Museum",
        "town": "Hartford",
        "county": "Hartford",
        "lat": 41.7670,
        "lon": -72.7014,
        "primary_anchor": "hartford",
        # Same Hartford/New Haven corridor logic as Science Center; 0.8 km west.
        "anchor_weights": {
            "hartford":   1.0,
            "new_haven":  0.3,
            "stamford":   0.0,
            "bridgeport": 0.0,
        },
    },
    "wadsworth_atheneum": {
        "display_name": "Wadsworth Atheneum",
        "name": "Wadsworth Atheneum Museum of Art",
        "town": "Hartford",
        "county": "Hartford",
        "lat": 41.7637,
        "lon": -72.6732,
        "primary_anchor": "hartford",
        # Downtown Hartford; same corridor logic as Science Center.
        "anchor_weights": {
            "hartford":   1.0,
            "new_haven":  0.3,
            "stamford":   0.0,
            "bridgeport": 0.0,
        },
    },
    "nbmaa": {
        "display_name": "New Britain Museum",
        "name": "New Britain Museum of American Art",
        "town": "New Britain",
        "county": "Hartford",
        "lat": 41.6643,
        "lon": -72.7916,
        "primary_anchor": "hartford",
        # New Britain is a Hartford-corridor city; reduced Hartford weight (0.8)
        # because New Britain itself draws a slightly broader New Haven corridor share.
        "anchor_weights": {
            "hartford":   0.8,
            "new_haven":  0.2,
            "stamford":   0.0,
            "bridgeport": 0.0,
        },
    },
    # ── Eastern Connecticut ───────────────────────────────────────────────────
    "mystic_aquarium": {
        "display_name": "Mystic Aquarium",
        "name": "Mystic Aquarium",
        "town": "Stonington",
        "county": "New London",
        "lat": 41.3734,
        "lon": -71.9519,
        "primary_anchor": "new_haven",
        # Southeastern CT; New Haven corridor (I-95 east) is primary.
        # Bridgeport catchment: some I-95 crossover.
        # Hartford: minor — Willimantic/eastern CT workers sometimes commute here.
        "anchor_weights": {
            "hartford":   0.2,
            "new_haven":  0.4,
            "stamford":   0.0,
            "bridgeport": 0.3,
        },
    },
    "pequot_museum": {
        "display_name": "Pequot Museum",
        "name": "Mashantucket Pequot Museum & Research Center",
        "town": "Mashantucket",
        "county": "New London",
        "lat": 41.4662,
        "lon": -71.9626,
        "primary_anchor": "new_haven",
        # Deep southeastern CT; limited commuter corridor relevance.
        # Small weights reflect that this is a destination attraction more than
        # a commuter-extension play — the model will reflect that in low scores.
        "anchor_weights": {
            "hartford":   0.1,
            "new_haven":  0.2,
            "stamford":   0.0,
            "bridgeport": 0.1,
        },
    },
    "florence_griswold": {
        "display_name": "Florence Griswold Museum",
        "name": "Florence Griswold Museum",
        "town": "Old Lyme",
        "county": "New London",
        "lat": 41.3154,
        "lon": -72.3281,
        "primary_anchor": "new_haven",
        # Old Lyme: mouth of the CT River; New Haven corridor (I-95) primary.
        # Hartford: moderate via Route 9/I-91.
        "anchor_weights": {
            "hartford":   0.3,
            "new_haven":  0.5,
            "stamford":   0.0,
            "bridgeport": 0.0,
        },
    },
    "nathan_hale_homestead": {
        "display_name": "Nathan Hale Homestead",
        "name": "Nathan Hale Homestead",
        "town": "Coventry",
        "county": "Tolland",
        "lat": 41.7732,
        "lon": -72.3420,
        "primary_anchor": "hartford",
        # Eastern Tolland County; Hartford is the dominant commuter anchor.
        # New Haven: small weight for I-84 east corridor workers.
        "anchor_weights": {
            "hartford":   0.6,
            "new_haven":  0.1,
            "stamford":   0.0,
            "bridgeport": 0.0,
        },
    },
    # ── Fairfield / Western Connecticut ──────────────────────────────────────
    "maritime_aquarium_norwalk": {
        "display_name": "Maritime Aquarium",
        "name": "Maritime Aquarium at Norwalk",
        "town": "Norwalk",
        "county": "Fairfield",
        "lat": 41.1011,
        "lon": -73.4166,
        "primary_anchor": "stamford",
        # Fairfield County; Stamford corridor is dominant.
        # Bridgeport: meaningful I-95 crossover.
        # New Haven: minor — some I-95 westbound workers.
        "anchor_weights": {
            "hartford":   0.0,
            "new_haven":  0.1,
            "stamford":   0.7,
            "bridgeport": 0.4,
        },
    },
    # ── Litchfield Hills / Western Connecticut ────────────────────────────────
    "kent_falls": {
        "display_name": "Kent Falls State Park",
        "name": "Kent Falls State Park",
        "town": "Kent",
        "county": "Litchfield",
        "lat": 41.7764,
        "lon": -73.4178,
        "primary_anchor": "hartford",
        # Northwestern Litchfield County; no dominant single anchor.
        # Hartford: moderate via Route 44/Route 8.
        # Stamford: some Fairfield County day-tripper catchment via Route 7.
        # New Haven: minor via I-84 west.
        # Weights are subjective defaults for a rural/day-trip attraction.
        "anchor_weights": {
            "hartford":   0.3,
            "new_haven":  0.1,
            "stamford":   0.2,
            "bridgeport": 0.0,
        },
    },
}


def weighted_flow(df: pd.DataFrame, attraction_key: str) -> pd.Series:
    """
    Compute anchor-weighted commute flow for a specific attraction.

    Returns a Series of the same length as df where each value is the
    weighted sum of inbound commute flows across anchors, using the
    attraction's anchor_weights.

    Anchors with weight=0 are excluded from the sum (no wasted multiply).
    Missing flow columns are skipped with a weight of 0 (not a hard error).
    """
    cfg = ATTRACTIONS[attraction_key]
    weights = cfg["anchor_weights"]
    result = pd.Series(0.0, index=df.index, dtype=float)
    for anchor, w in weights.items():
        if w == 0.0:
            continue
        col = ANCHOR_COLS[anchor]
        if col not in df.columns:
            continue
        result = result + df[col].fillna(0) * w
    return result
