"""
pipeline/behavior_overlay.py
Tourism behavior tagging for scored towns.

Assigns one of four tourism behaviors to each town based on drive band
and demographic signals. Behavior determines the marketing approach in
persona deep-dives and report copy.

  Day-Tripper          ≤90 min — returns same day; frequency matters
  Weekender            90–180 min — overnight stay; bundle messaging
  Local Repeat Visitor <20 min — membership conversion candidate
  Special-Event-Seeker >180 min — only programming-motivated travel expected

A persona in ct-town-personas is: <demographic archetype> × <tourism behavior>

Serves: /personas/* endpoints, Post #1, Post #5
"""

from __future__ import annotations

import pandas as pd


_LOCAL_THRESHOLD_MIN = 20  # towns under 20 min are Local Repeat Visitor candidates


def assign_behavior(drive_band: str, drive_time_min: float) -> str:
    """Assign a single tourism behavior label from drive band and time."""
    if pd.isna(drive_time_min):
        return "Unknown"
    if drive_time_min <= _LOCAL_THRESHOLD_MIN:
        return "Local Repeat Visitor"
    if drive_band == "Day-Tripper":
        return "Day-Tripper"
    if drive_band == "Weekender":
        return "Weekender"
    return "Special-Event-Seeker"


def apply_behavior_overlay(scored_df: pd.DataFrame) -> pd.DataFrame:
    """
    Add tourism_behavior column to a scored towns DataFrame.

    Expects drive_band and drive_time_min columns (added by anchors.score_towns).
    Returns a copy with the new column; does not modify in place.
    """
    df = scored_df.copy()
    df["tourism_behavior"] = df.apply(
        lambda row: assign_behavior(
            row.get("drive_band", "Unknown"),
            row.get("drive_time_min", float("nan")),
        ),
        axis=1,
    )
    return df
