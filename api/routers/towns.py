"""api/routers/towns.py — town feature and archetype endpoints"""

import json
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Request

from api.models import TownFeaturesResponse, ArchetypeResponse

router = APIRouter()


def _state(req: Request):
    return req.app.state




@router.get("/all-clusters")
def get_all_town_clusters(year: Optional[int] = None, request: Request = None):
    """
    Returns archetype label for every town — used by the choropleth map.
    Lightweight endpoint — just town + archetype_label.
    """
    s = _state(request)
    if s.clusters.empty:
        raise HTTPException(503, "Data not loaded")
    year = year or int(s.clusters["year"].max())
    df = s.clusters[s.clusters["year"] == year][["town", "archetype_label", "dominant_persona_pct"]]
    return {
        "year": year,
        "towns": df.to_dict(orient="records"),
    }


@router.get("/{town}", response_model=TownFeaturesResponse)
def get_town_features(town: str, year: Optional[int] = None, request: Request = None):
    s = _state(request)
    if s.features.empty:
        raise HTTPException(503, "Data not loaded — run: make pipeline")

    town = town.strip().title()
    year = year or int(s.features["year"].max())
    df = s.features[(s.features["town"] == town) & (s.features["year"] == year)]
    if df.empty:
        raise HTTPException(404, f"No data for '{town}' in {year}")

    row = df.iloc[0].where(pd.notna(df.iloc[0]), other=None).to_dict()
    row["town"] = town
    row["year"] = year
    return TownFeaturesResponse(**{k: row.get(k) for k in TownFeaturesResponse.model_fields})


@router.get("/{town}/compare")
def compare_towns(town: str, compare_to: str, year: Optional[int] = None, request: Request = None):
    s = _state(request)
    if s.features.empty:
        raise HTTPException(503, "Data not loaded")

    year = year or int(s.features["year"].max())
    result = {}
    for t in [town.strip().title(), compare_to.strip().title()]:
        df = s.features[(s.features["town"] == t) & (s.features["year"] == year)]
        cl = s.clusters[(s.clusters["town"] == t) & (s.clusters["year"] == year)]
        if df.empty:
            raise HTTPException(404, f"No data for '{t}' in {year}")
        row = df.iloc[0].where(pd.notna(df.iloc[0]), other=None).to_dict()
        if not cl.empty:
            row["archetype"] = cl.iloc[0].get("archetype_label")
        result[t] = row

    return {"year": year, "towns": result}


@router.get("/archetypes/all")
def get_all_archetypes(year: Optional[int] = None, request: Request = None):
    s = _state(request)
    if s.centroids.empty:
        raise HTTPException(503, "Data not loaded")

    year = year or int(s.clusters["year"].max())
    clusters_yr = s.clusters[s.clusters["year"] == year]
    archetypes = []

    for _, row in s.centroids.iterrows():
        cluster_towns = clusters_yr[clusters_yr["cluster_id"] == int(row["cluster_id"])]["town"].tolist()
        rep_towns = json.loads(row.get("representative_towns", "[]"))
        numeric_cols = [
            c for c in row.index
            if c not in ["cluster_id", "archetype_label", "representative_towns"]
            and pd.api.types.is_numeric_dtype(type(row[c]))
        ]
        centroid_stats = {col: round(float(row[col]), 2) if pd.notna(row[col]) else None
                          for col in numeric_cols}
        archetypes.append(ArchetypeResponse(
            cluster_id=int(row["cluster_id"]),
            archetype_label=row["archetype_label"],
            town_count=len(cluster_towns),
            representative_towns=rep_towns,
            centroid_stats=centroid_stats,
        ))

    return {"year": year, "archetypes": archetypes}
