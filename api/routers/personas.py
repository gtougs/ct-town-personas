"""api/routers/personas.py — persona card endpoints"""

import numpy as np
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Request

from api.models import TownPersonaResponse
from pipeline.persona import PersonaBuilder

router = APIRouter()
_builder = PersonaBuilder()


def _state(req: Request):
    return req.app.state


@router.get("/{town}", response_model=TownPersonaResponse)
def get_town_personas(town: str, year: Optional[int] = None, request: Request = None):
    s = _state(request)
    if s.features.empty:
        raise HTTPException(503, "Data not loaded — run: make pipeline")

    town = town.strip().title()
    year = year or int(s.features["year"].max())
    result = _builder.build_town_personas(s.features, s.clusters, s.centroids, town, year)

    if "error" in result:
        raise HTTPException(404, result["error"])
    return TownPersonaResponse(**result)


@router.get("/{town}/marketer")
def get_marketer_view(town: str, year: Optional[int] = None, request: Request = None):
    full = get_town_personas(town, year, request)
    return {
        "town": full.town, "year": full.year,
        "dominant_archetype": full.dominant_archetype,
        "summary": full.summary,
        "personas": [
            {"archetype": p.archetype, "weight": p.weight, **p.marketer.model_dump()}
            for p in full.personas
        ],
    }


@router.get("/{town}/business")
def get_business_view(town: str, year: Optional[int] = None, request: Request = None):
    full = get_town_personas(town, year, request)
    return {
        "town": full.town, "year": full.year,
        "dominant_archetype": full.dominant_archetype,
        "summary": full.summary,
        "personas": [
            {"archetype": p.archetype, "weight": p.weight, **p.business.model_dump()}
            for p in full.personas
        ],
    }


@router.get("/similar/{town}")
def get_similar_towns(town: str, year: Optional[int] = None, n: int = 5, request: Request = None):
    s = _state(request)
    if s.clusters.empty:
        raise HTTPException(503, "Data not loaded")

    town = town.strip().title()
    year = year or int(s.clusters["year"].max())
    yr_clusters = s.clusters[s.clusters["year"] == year]

    target = yr_clusters[yr_clusters["town"] == town]
    if target.empty:
        raise HTTPException(404, f"Town '{town}' not found")

    tx, ty = float(target.iloc[0]["pca_x"]), float(target.iloc[0]["pca_y"])
    others = yr_clusters[yr_clusters["town"] != town].copy()
    others["distance"] = np.sqrt((others["pca_x"] - tx)**2 + (others["pca_y"] - ty)**2)
    similar = others.nsmallest(n, "distance")[["town", "archetype_label", "distance"]]

    return {"town": town, "year": year, "similar_towns": similar.to_dict(orient="records")}
