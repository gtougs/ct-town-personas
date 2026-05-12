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
    "ct_science_center": {
        "name": "CT Science Center",
        "lat": 41.7659,
        "lon": -72.6693,
        "primary_anchor": "hartford",
        # anchor_weights rationale:
        #   Hartford = 1.0  (primary — attraction is in Hartford)
        #   New Haven = 0.3 (secondary — I-91 corridor, some shared suburban catchment)
        #   Stamford = 0.0  (Fairfield County corridor is irrelevant for Hartford)
        #   Bridgeport = 0.0 (same reason)
        # These weights are subjective defaults.  A client engagement can recalibrate
        # based on observed visitation data or ticket-purchase geography.
        "anchor_weights": {
            "hartford":   1.0,
            "new_haven":  0.3,
            "stamford":   0.0,
            "bridgeport": 0.0,
        },
    },
    # Add additional attractions here as engagements are onboarded.
    # Template:
    # "short_key": {
    #     "name": "...",
    #     "lat": ..., "lon": ...,
    #     "primary_anchor": "...",
    #     "anchor_weights": {"hartford": ..., "new_haven": ..., ...},
    # },
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
