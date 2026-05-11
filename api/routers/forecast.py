"""
api/routers/forecast.py
Time-series forecast endpoints.

Data sources (in priority order):
  1. enriched_timeseries.parquet — Zillow + business formations (real time series)
  2. town_features_all_years.parquet — ACS snapshots (limited vintages)
"""

import numpy as np
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Request

from api.models import IndicatorForecast, ForecastPoint

router = APIRouter()

# Indicators sourced from ACS snapshots
ACS_INDICATORS = [
    "median_household_income",
    "median_home_value",
    "median_rent",
    "gini_ratio",
    "snap_recipients",
    "disengaged_youth",
    "single_parent_families",
    "housing_permits",
    "total_assisted_units",
    "business_formations",
]

# Indicators sourced from enriched time series (real monthly data)
ENRICHED_INDICATORS = [
    "zillow_home_value",
    "annual_business_formations",
]

ALL_INDICATORS = ACS_INDICATORS + ENRICHED_INDICATORS

INDICATOR_LABELS = {
    "median_household_income":    "Median Household Income",
    "median_home_value":          "Median Home Value (ACS)",
    "median_rent":                "Median Rent",
    "gini_ratio":                 "Gini Ratio (Inequality)",
    "snap_recipients":            "SNAP Recipients %",
    "disengaged_youth":           "Disengaged Youth %",
    "single_parent_families":     "Single Parent Families %",
    "housing_permits":            "Housing Permits",
    "total_assisted_units":       "Subsidized Housing Units",
    "business_formations":        "Business Formations (ACS)",
    "zillow_home_value":          "Home Value (Zillow, monthly)",
    "annual_business_formations": "Business Formations (SOTS, annual)",
}


def _get_state(req: Request):
    return req.app.state


def _load_enriched() -> pd.DataFrame:
    from pathlib import Path
    path = Path("data/processed/enriched_timeseries.parquet")
    if path.exists():
        return pd.read_parquet(path)
    return pd.DataFrame()


@router.get("/indicators")
def list_indicators():
    return {
        "acs_indicators": ACS_INDICATORS,
        "enriched_indicators": ENRICHED_INDICATORS,
        "labels": INDICATOR_LABELS,
    }


@router.get("/{town}/{indicator}", response_model=IndicatorForecast)
def get_indicator_forecast(
    town: str,
    indicator: str,
    horizon_years: int = 5,
    request: Request = None,
):
    if indicator not in ALL_INDICATORS:
        raise HTTPException(400, f"'{indicator}' not forecastable. Options: {ALL_INDICATORS}")

    town = town.strip().title()

    # ── Try enriched time series first ──────────────────────────────────────
    if indicator in ENRICHED_INDICATORS:
        enriched = _load_enriched()
        if not enriched.empty:
            town_data = enriched[
                (enriched["town"] == town) &
                (enriched["indicator"] == indicator)
            ][["year", "value"]].dropna().sort_values("year")

            if len(town_data) >= 2:
                return _build_forecast_response(town, indicator, town_data, horizon_years)

    # ── Fall back to ACS features ────────────────────────────────────────────
    s = _get_state(request)
    if s.features.empty:
        raise HTTPException(503, "Data not loaded")

    town_df = (
        s.features[s.features["town"] == town][["year", indicator]]
        .dropna()
        .drop_duplicates(subset=["year"])
        .sort_values("year")
    )

    if len(town_df) < 2:
        raise HTTPException(
            404,
            f"Not enough data for '{town}' / '{indicator}'. "
            f"Available years: {sorted(town_df['year'].tolist())}"
        )

    return _build_forecast_response(town, indicator, town_df, horizon_years)


@router.get("/{town}")
def get_all_forecasts(town: str, horizon_years: int = 5, request: Request = None):
    results = {}
    for ind in ALL_INDICATORS:
        try:
            r = get_indicator_forecast(town, ind, horizon_years, request)
            results[ind] = r.model_dump()
        except HTTPException:
            results[ind] = None
    return {"town": town.strip().title(), "forecasts": results}


# ── Core forecast builder ─────────────────────────────────────────────────────

def _build_forecast_response(
    town: str,
    indicator: str,
    data: pd.DataFrame,
    horizon: int,
) -> IndicatorForecast:
    historical = [
        ForecastPoint(year=int(r["year"]), value=round(float(r.iloc[1]), 2),
                      lower=None, upper=None)
        for _, r in data.iterrows()
    ]

    try:
        forecast_pts, direction, magnitude = _prophet_forecast(data, data.columns[1], horizon)
    except Exception:
        forecast_pts, direction, magnitude = _linear_forecast(data, data.columns[1], horizon)

    return IndicatorForecast(
        town=town,
        indicator=indicator,
        historical=historical,
        forecast=forecast_pts,
        trend_direction=direction,
        trend_magnitude=magnitude,
    )


def _prophet_forecast(df, col, horizon):
    from prophet import Prophet
    prophet_df = pd.DataFrame({
        "ds": pd.to_datetime(df["year"].astype(str) + "-07-01"),
        "y": df[col].astype(float),
    })
    model = Prophet(
        yearly_seasonality=False,
        weekly_seasonality=False,
        daily_seasonality=False,
        changepoint_prior_scale=0.3,
        interval_width=0.80,
    )
    model.fit(prophet_df)
    last_year = int(df["year"].max())
    future = pd.DataFrame({
        "ds": pd.date_range(f"{last_year+1}-07-01", periods=horizon, freq="YS")
    })
    fc = model.predict(future)
    pts = [
        ForecastPoint(
            year=int(r.ds.year),
            value=round(float(r.yhat), 2),
            lower=round(float(r.yhat_lower), 2),
            upper=round(float(r.yhat_upper), 2),
        )
        for r in fc.itertuples()
    ]
    return pts, *_trend(df[col].values, [p.value for p in pts])


def _linear_forecast(df, col, horizon):
    years = df["year"].astype(float).values
    vals  = df[col].astype(float).values
    c = np.polyfit(years, vals, 1)
    last = int(years.max())
    resid = vals - np.polyval(c, years)
    ci = 1.28 * float(np.std(resid)) if len(resid) > 2 else 0
    pts = [
        ForecastPoint(
            year=yr,
            value=round(float(np.polyval(c, yr)), 2),
            lower=round(float(np.polyval(c, yr)) - ci, 2),
            upper=round(float(np.polyval(c, yr)) + ci, 2),
        )
        for yr in range(last+1, last+horizon+1)
    ]
    return pts, *_trend(vals, [p.value for p in pts])


def _trend(historical, forecast):
    if not forecast or len(historical) < 2:
        return "stable", "weak"
    hist_mean = float(np.mean(historical))
    if hist_mean == 0:
        return "stable", "weak"
    pct = (forecast[-1] - hist_mean) / abs(hist_mean)
    direction = "increasing" if pct > 0.02 else ("decreasing" if pct < -0.02 else "stable")
    magnitude = "strong" if abs(pct) > 0.15 else ("moderate" if abs(pct) > 0.05 else "weak")
    return direction, magnitude
