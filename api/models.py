"""
api/models.py
Pydantic response models. These define the exact shape of every API response
and serve as documentation for the frontend team.
"""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


# ── Shared ────────────────────────────────────────────────────────────────────

class LocationSignal(BaseModel):
    signal: str
    type: str  # "positive" | "caution" | "neutral"


class AudienceSignal(BaseModel):
    signal: str
    strength: str  # "high" | "medium" | "low"


# ── Marketer persona ──────────────────────────────────────────────────────────

class ChannelGuidance(BaseModel):
    digital: str
    social_media: str
    direct_mail: str
    ott_streaming: str
    local_print: str


class MarketerPersona(BaseModel):
    archetype: str
    weight: float
    description: str
    headline_stats: dict[str, Optional[str]]
    audience_signals: list[AudienceSignal]
    messaging_angles: list[str]
    channel_guidance: ChannelGuidance
    new_resident_opportunity: Optional[str]


# ── Business owner persona ────────────────────────────────────────────────────

class BusinessPersona(BaseModel):
    archetype: str
    weight: float
    market_summary: str
    headline_stats: dict[str, Optional[str]]
    dominant_industries: list[str]
    market_gaps: list[str]
    buying_power_index: float
    location_signals: list[LocationSignal]


# ── Combined persona card ─────────────────────────────────────────────────────

class PersonaCard(BaseModel):
    archetype: str
    weight: float
    marketer: MarketerPersona
    business: BusinessPersona


# ── Town persona response ─────────────────────────────────────────────────────

class TownPersonaResponse(BaseModel):
    town: str
    year: int
    dominant_archetype: str
    cluster_id: int
    pca_x: float
    pca_y: float
    summary: str
    personas: list[PersonaCard]


# ── Town features (raw indicators) ───────────────────────────────────────────

class TownFeaturesResponse(BaseModel):
    town: str
    year: int
    total_population: Optional[float]
    median_age: Optional[float]
    median_household_income: Optional[float]
    per_capita_income: Optional[float]
    median_home_value: Optional[float]
    median_gross_rent: Optional[float]
    pct_owner_occupied: Optional[float]
    vacancy_rate: Optional[float]
    unemployment_rate: Optional[float]
    pct_wfh: Optional[float]
    pct_bachelors_or_higher: Optional[float]
    pct_graduate_degree: Optional[float]
    businesses_per_1k: Optional[float]
    business_survival_score: Optional[float]
    pct_insured: Optional[float]
    pct_same_house: Optional[float]
    pct_in_migration: Optional[float]
    top_naics_1: Optional[str]
    top_naics_2: Optional[str]
    top_naics_3: Optional[str]


# ── Cluster / archetype ───────────────────────────────────────────────────────

class ArchetypeResponse(BaseModel):
    cluster_id: int
    archetype_label: str
    town_count: int
    representative_towns: list[str]
    centroid_stats: dict[str, Optional[float]]


# ── Forecast ─────────────────────────────────────────────────────────────────

class ForecastPoint(BaseModel):
    year: int
    value: float
    lower: Optional[float] = None
    upper: Optional[float] = None


class IndicatorForecast(BaseModel):
    town: str
    indicator: str
    historical: list[ForecastPoint]
    forecast: list[ForecastPoint]
    trend_direction: str   # "increasing" | "decreasing" | "stable"
    trend_magnitude: str   # "strong" | "moderate" | "weak"
