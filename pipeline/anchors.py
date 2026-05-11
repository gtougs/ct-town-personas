"""
pipeline/anchors.py
Anchor config loading and opportunity scoring.

An "anchor" is a CT cultural attraction: (name, lat, lon, demographic_weights,
drive_band_config). Opportunity scoring ranks all CT towns by audience fit for
a specific anchor.

Composite score: 60% demographic, 40% accessibility
  Accessibility: 70% drive-band tier, 15% within-band proximity, 15% LODES flow

Anchor configs live in config/anchors/*.yaml. Add a new YAML to score any
CT attraction without touching this module.

Serves: Post #1 (closest-affluent-town fallacy), Post #5 (commuter arbitrage),
        /anchors/* API endpoints
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import yaml
from sklearn.preprocessing import MinMaxScaler

from pipeline.drive_time import add_drive_columns

log = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).parents[1] / "config" / "anchors"
PROCESSED_DIR = Path(__file__).parents[1] / "data" / "processed"

DEMO_WEIGHT = 0.60
ACCESS_WEIGHT = 0.40


# ── Config loading ─────────────────────────────────────────────────────────────

def load_anchor(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def load_all_anchors() -> dict[str, dict]:
    """Return {short_name: config} for every YAML in config/anchors/."""
    anchors = {}
    for p in sorted(CONFIG_DIR.glob("*.yaml")):
        cfg = load_anchor(p)
        anchors[cfg["short_name"]] = cfg
    return anchors


# ── Scoring ────────────────────────────────────────────────────────────────────

def score_towns(
    features_df: pd.DataFrame,
    anchor: dict,
    lodes_df: Optional[pd.DataFrame] = None,
    year: Optional[int] = None,
) -> pd.DataFrame:
    """
    Score and rank all CT towns for a given anchor.

    Returns features_df with added columns:
      demographic_score   (0–100)
      drive_time_min
      drive_band          (Day-Tripper | Weekender | Beyond | Unknown)
      accessibility_score (0–100)
      opportunity_score   (0–100, weighted composite)
      rank                (1 = highest opportunity)

    Every scoring step is traceable — no silent imputation beyond median fill
    for missing demographic features.
    """
    loc = anchor["location"]
    bands = anchor.get("drive_bands", {})
    day_max = bands.get("day_tripper", {}).get("max_minutes", 90)
    weekender_max = bands.get("weekender", {}).get("max_minutes", 180)

    df = features_df.copy()
    if year is not None:
        df = df[df["year"] == year].copy()

    df = add_drive_columns(df, loc["lat"], loc["lon"], day_max, weekender_max)

    # Join LODES inbound flow for this anchor's town if available
    anchor_town = loc.get("town", "")
    lodes_col = f"inbound_to_{anchor_town.lower().replace(' ', '_')}"
    if lodes_df is not None and lodes_col in lodes_df.columns:
        df = df.merge(lodes_df[["town", lodes_col]].rename(columns={lodes_col: "inbound_workers"}),
                      on="town", how="left")
        df["inbound_workers"] = df["inbound_workers"].fillna(0)
    elif "inbound_workers" not in df.columns:
        df["inbound_workers"] = 0

    df["demographic_score"] = _demographic_score(df, anchor["demographic_weights"])
    df["accessibility_score"] = _accessibility_score(df, anchor_town)
    df["opportunity_score"] = (
        DEMO_WEIGHT * df["demographic_score"] + ACCESS_WEIGHT * df["accessibility_score"]
    ).round(2)

    df = df.sort_values("opportunity_score", ascending=False).reset_index(drop=True)
    df["rank"] = range(1, len(df) + 1)

    log.info(
        "Scored %d towns for '%s' | range %.1f – %.1f",
        len(df), anchor["name"],
        df["opportunity_score"].min(), df["opportunity_score"].max(),
    )
    return df


def score_and_save(
    features_df: pd.DataFrame,
    anchor: dict,
    lodes_df: Optional[pd.DataFrame] = None,
    year: int = 2022,
) -> pd.DataFrame:
    scored = score_towns(features_df, anchor, lodes_df=lodes_df, year=year)
    out = PROCESSED_DIR / f"town_scores_{anchor['short_name']}_{year}.parquet"
    scored.to_parquet(out, index=False)
    log.info("Saved -> %s", out)
    return scored


# ── Internal scoring helpers ───────────────────────────────────────────────────

def _demographic_score(df: pd.DataFrame, weights: dict) -> pd.Series:
    available = {k: w for k, w in weights.items() if k in df.columns}
    missing = set(weights) - set(available)
    if missing:
        log.warning("Demographic weight columns not in feature matrix: %s", missing)
    if not available:
        log.error("No demographic features available — returning zero scores")
        return pd.Series(0.0, index=df.index)

    total = sum(available.values())
    norm_weights = {k: w / total for k, w in available.items()}

    feature_matrix = df[list(available)].fillna(df[list(available)].median())
    scaled = MinMaxScaler().fit_transform(feature_matrix)
    scaled_df = pd.DataFrame(scaled, columns=list(available), index=df.index)

    score = sum(scaled_df[feat] * w for feat, w in norm_weights.items())
    return (score * 100).round(2)


def _accessibility_score(df: pd.DataFrame, anchor_town: str) -> pd.Series:
    """
    Three-component accessibility score (0–100):
      band_score  (0–70)  Drive-band tier
      time_score  (0–15)  Within-band proximity refinement
      lodes_score (0–15)  LODES inbound commute flow proxy
    """
    band_score = df["drive_band"].map({
        "Day-Tripper": 70.0,
        "Weekender":   38.0,
        "Beyond":       7.0,
        "Unknown":      0.0,
    }).fillna(0.0)

    max_drive = df["drive_time_min"].replace([np.inf, -np.inf], np.nan).max()
    time_score = (1 - df["drive_time_min"].fillna(max_drive) / max_drive) * 15

    workers = df["inbound_workers"].copy()
    workers.loc[df["town"] == anchor_town] = 0  # exclude self-commuters
    max_workers = workers.replace(0, np.nan).max()
    if pd.notna(max_workers) and max_workers > 0:
        lodes_score = (workers / max_workers * 15).fillna(0).clip(0, 15)
    else:
        lodes_score = pd.Series(0.0, index=df.index)

    return (band_score + time_score + lodes_score).clip(0, 100).round(2)
