"""api/routers/forecast.py — time-series forecast endpoints"""

import numpy as np
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Request

from api.models import IndicatorForecast, ForecastPoint

router = APIRouter()

FORECASTABLE = [
    "total_population", "median_household_income", "median_home_value",
    "median_gross_rent", "unemployment_rate", "pct_wfh",
    "pct_bachelors_or_higher", "businesses_per_1k",
    "pct_owner_occupied", "pct_in_migration",
]


def _state(req: Request):
    return req.app.state


@router.get("/indicators")
def list_indicators():
    return {"indicators": FORECASTABLE}


@router.get("/{town}/{indicator}", response_model=IndicatorForecast)
def get_indicator_forecast(
    town: str,
    indicator: str,
    horizon_years: int = 5,
    request: Request = None,
):
    if indicator not in FORECASTABLE:
        raise HTTPException(400, f"'{indicator}' not forecastable. Options: {FORECASTABLE}")

    s = _state(request)
    if s.features.empty:
        raise HTTPException(503, "Data not loaded")

    town = town.strip().title()
    town_df = s.features[s.features["town"] == town][["year", indicator]].dropna().sort_values("year")

    if len(town_df) < 2:
        raise HTTPException(404, f"Not enough data for '{town}' / '{indicator}'")

    historical = [
        ForecastPoint(year=int(r["year"]), value=round(float(r[indicator]), 2))
        for _, r in town_df.iterrows()
    ]

    try:
        forecast_pts, direction, magnitude = _prophet_forecast(town_df, indicator, horizon_years)
    except Exception:
        forecast_pts, direction, magnitude = _linear_forecast(town_df, indicator, horizon_years)

    return IndicatorForecast(
        town=town, indicator=indicator,
        historical=historical, forecast=forecast_pts,
        trend_direction=direction, trend_magnitude=magnitude,
    )


@router.get("/{town}")
def get_all_forecasts(town: str, horizon_years: int = 5, request: Request = None):
    results = {}
    for ind in FORECASTABLE:
        try:
            r = get_indicator_forecast(town, ind, horizon_years, request)
            results[ind] = r.model_dump()
        except HTTPException:
            results[ind] = None
    return {"town": town.strip().title(), "forecasts": results}


# ── Engines ───────────────────────────────────────────────────────────────────

def _prophet_forecast(df, indicator, horizon):
    from prophet import Prophet
    prophet_df = pd.DataFrame({
        "ds": pd.to_datetime(df["year"].astype(str) + "-01-01"),
        "y": df[indicator].astype(float),
    })
    model = Prophet(yearly_seasonality=False, weekly_seasonality=False,
                    daily_seasonality=False, changepoint_prior_scale=0.3,
                    interval_width=0.80)
    model.fit(prophet_df)
    last_year = int(df["year"].max())
    future = pd.DataFrame({"ds": pd.date_range(f"{last_year+1}-01-01", periods=horizon, freq="YS")})
    fc = model.predict(future)
    pts = [ForecastPoint(year=int(r.ds.year), value=round(r.yhat, 2),
                         lower=round(r.yhat_lower, 2), upper=round(r.yhat_upper, 2))
           for r in fc.itertuples()]
    return pts, *_trend(df[indicator].values, [p.value for p in pts])


def _linear_forecast(df, indicator, horizon):
    years = df["year"].astype(float).values
    vals  = df[indicator].astype(float).values
    c = np.polyfit(years, vals, 1)
    last = int(years.max())
    resid = vals - np.polyval(c, years)
    ci = 1.28 * float(np.std(resid)) if len(resid) > 2 else 0
    pts = [ForecastPoint(year=yr,
                         value=round(float(np.polyval(c, yr)), 2),
                         lower=round(float(np.polyval(c, yr)) - ci, 2),
                         upper=round(float(np.polyval(c, yr)) + ci, 2))
           for yr in range(last+1, last+horizon+1)]
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
