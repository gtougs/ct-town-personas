"""
api/routers/anchors.py
Anchor-based source-market endpoints.

All scoring is done at request time from cached Parquet files — no DB needed.
Heavy results (top-markets) are limited to n=25 by default to keep payloads small.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Request

from pipeline.anchors import load_all_anchors, score_towns
from pipeline.behavior_overlay import apply_behavior_overlay

router = APIRouter()

PROCESSED_DIR = Path(__file__).parents[2] / "data" / "processed"
_ANCHORS: dict[str, dict] = {}  # lazy-loaded cache


def _get_anchors() -> dict[str, dict]:
    global _ANCHORS
    if not _ANCHORS:
        _ANCHORS = load_all_anchors()
    return _ANCHORS


def _get_state(req: Request):
    return req.app.state


def _load_lodes(year: int = 2021) -> pd.DataFrame:
    path = PROCESSED_DIR / f"lodes_anchor_flows_{year}.parquet"
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("")
def list_anchors():
    """All configured attractions."""
    anchors = _get_anchors()
    return {
        "anchors": [
            {
                "id": key,
                "name": cfg["name"],
                "town": cfg["location"]["town"],
                "lat": cfg["location"]["lat"],
                "lon": cfg["location"]["lon"],
            }
            for key, cfg in anchors.items()
        ]
    }


@router.get("/{anchor_id}/top-markets")
def top_markets(
    anchor_id: str,
    request: Request,
    n: int = Query(15, ge=1, le=25),
    year: Optional[int] = Query(None),
):
    """Top-N source towns for an anchor, scored and ranked."""
    anchors = _get_anchors()
    if anchor_id not in anchors:
        raise HTTPException(404, f"Anchor '{anchor_id}' not found. Available: {list(anchors)}")

    state = _get_state(request)
    if state.features.empty:
        raise HTTPException(503, "Feature data not loaded. Run: make pipeline")

    yr = year or int(state.features["year"].max())
    lodes = _load_lodes()

    scored = score_towns(state.features, anchors[anchor_id], lodes_df=lodes or None, year=yr)
    scored = apply_behavior_overlay(scored)

    top = scored.head(n)
    return {
        "anchor": anchor_id,
        "year": yr,
        "total_towns_scored": len(scored),
        "markets": _rows_to_records(top),
    }


@router.get("/{anchor_id}/personas")
def anchor_personas(
    anchor_id: str,
    request: Request,
    year: Optional[int] = Query(None),
):
    """Persona and behavior distribution across an anchor's top-50 catchment."""
    anchors = _get_anchors()
    if anchor_id not in anchors:
        raise HTTPException(404, f"Anchor '{anchor_id}' not found.")

    state = _get_state(request)
    if state.features.empty:
        raise HTTPException(503, "Feature data not loaded. Run: make pipeline")

    yr = year or int(state.features["year"].max())
    lodes = _load_lodes()

    scored = score_towns(state.features, anchors[anchor_id], lodes_df=lodes or None, year=yr)
    scored = apply_behavior_overlay(scored)

    catchment = scored.head(50)

    # Merge archetype labels from cluster output
    clusters = state.clusters
    if not clusters.empty:
        yr_clusters = clusters[clusters["year"] == yr][["town", "archetype_label"]]
        catchment = catchment.merge(yr_clusters, on="town", how="left")
    else:
        catchment["archetype_label"] = "Unknown"

    behavior_dist = (
        catchment["tourism_behavior"].value_counts(normalize=True)
        .mul(100).round(1).to_dict()
    )
    archetype_dist = (
        catchment["archetype_label"].value_counts(normalize=True)
        .mul(100).round(1).to_dict()
    )

    return {
        "anchor": anchor_id,
        "year": yr,
        "catchment_size": len(catchment),
        "tourism_behavior_distribution": behavior_dist,
        "archetype_distribution": archetype_dist,
        "top_10": _rows_to_records(catchment.head(10)),
    }


@router.get("/{anchor_id}/compare")
def compare_anchors(
    anchor_id: str,
    request: Request,
    with_anchor: str = Query(..., alias="with"),
    year: Optional[int] = Query(None),
    n: int = Query(15, ge=1, le=25),
):
    """Side-by-side source-market overlap between two anchors."""
    anchors = _get_anchors()
    for aid in [anchor_id, with_anchor]:
        if aid not in anchors:
            raise HTTPException(404, f"Anchor '{aid}' not found. Available: {list(anchors)}")

    state = _get_state(request)
    if state.features.empty:
        raise HTTPException(503, "Feature data not loaded. Run: make pipeline")

    yr = year or int(state.features["year"].max())
    lodes = _load_lodes()

    scored_a = score_towns(state.features, anchors[anchor_id], lodes_df=lodes or None, year=yr)
    scored_b = score_towns(state.features, anchors[with_anchor], lodes_df=lodes or None, year=yr)

    top_a = set(scored_a.head(n)["town"])
    top_b = set(scored_b.head(n)["town"])

    shared = sorted(top_a & top_b)
    only_a = sorted(top_a - top_b)
    only_b = sorted(top_b - top_a)

    return {
        "anchor_a": anchor_id,
        "anchor_b": with_anchor,
        "year": yr,
        "top_n": n,
        "shared_markets": shared,
        f"only_{anchor_id}": only_a,
        f"only_{with_anchor}": only_b,
        "overlap_pct": round(len(shared) / n * 100, 1),
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _rows_to_records(df: pd.DataFrame) -> list[dict]:
    cols = ["town", "rank", "opportunity_score", "demographic_score",
            "accessibility_score", "drive_time_min", "drive_band", "tourism_behavior"]
    present = [c for c in cols if c in df.columns]
    return df[present].to_dict(orient="records")
