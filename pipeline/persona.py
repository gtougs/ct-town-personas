"""
persona.py
Converts cluster centroids + town-level data into structured persona cards.
Fully defensive — works with whatever columns are available.
"""

import json
import logging
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)
PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"

NAICS_SECTOR_LABELS = {
    "44": "Retail Trade", "45": "Retail Trade",
    "72": "Hospitality & Food", "62": "Healthcare",
    "54": "Professional Services", "52": "Finance & Insurance",
    "23": "Construction", "61": "Education Services",
    "81": "Other Services", "92": "Public Administration",
}


class PersonaBuilder:

    def build_town_personas(self, features_df, clusters_df, centroids_df, town, year=None):
        year = year or int(features_df["year"].max())
        town_feat = features_df[(features_df["town"] == town) & (features_df["year"] == year)]
        town_clust = clusters_df[(clusters_df["town"] == town) & (clusters_df["year"] == year)]

        if town_feat.empty or town_clust.empty:
            return {"error": f"No data for {town} in {year}"}

        feat = town_feat.iloc[0]
        clust = town_clust.iloc[0]
        probs = json.loads(clust["persona_probs"])
        sorted_archetypes = sorted(probs.items(), key=lambda x: x[1], reverse=True)

        personas = []
        for archetype_label, prob in sorted_archetypes:
            if prob < 0.05:
                continue
            centroid = centroids_df[centroids_df["archetype_label"] == archetype_label]
            centroid_row = centroid.iloc[0] if not centroid.empty else None
            personas.append({
                "archetype": archetype_label,
                "weight": round(prob, 3),
                "marketer": self._marketer_persona(feat, centroid_row, archetype_label, prob),
                "business": self._business_persona(feat, centroid_row, archetype_label, prob),
            })

        return {
            "town": town,
            "year": year,
            "dominant_archetype": sorted_archetypes[0][0],
            "cluster_id": int(clust["cluster_id"]),
            "pca_x": round(float(clust["pca_x"]), 4),
            "pca_y": round(float(clust["pca_y"]), 4),
            "personas": personas,
            "summary": self._town_summary(feat, sorted_archetypes),
        }

    # ── Marketer persona ──────────────────────────────────────────────────────

    def _marketer_persona(self, feat, centroid, archetype, weight):
        income   = _get(feat, "median_household_income")
        home_val = _get(feat, "median_home_value")
        rent     = _get(feat, "median_rent")
        edu      = _get(feat, "educational_attainment")
        gini     = _get(feat, "gini_ratio")
        snap     = _get(feat, "snap_recipients")
        mobility = _get(feat, "residential_mobility")
        single_p = _get(feat, "single_parent_families")

        return {
            "archetype": archetype,
            "weight": round(weight, 3),
            "description": self._marketer_description(feat, archetype, weight),
            "headline_stats": {
                k: v for k, v in {
                    "household_income":   _fmt_currency(income),
                    "median_home_value":  _fmt_currency(home_val),
                    "median_rent":        _fmt_currency(rent),
                    "educational_attainment": _fmt(edu, suffix="%"),
                    "gini_ratio":         _fmt(gini, decimals=3),
                    "snap_recipients":    _fmt(snap, suffix="%"),
                    "residential_mobility": _fmt(mobility, suffix="%"),
                    "single_parent_families": _fmt(single_p, suffix="%"),
                }.items() if v is not None
            },
            "audience_signals": self._audience_signals(feat),
            "messaging_angles": self._messaging_angles(feat),
            "channel_guidance": self._channel_guidance(feat),
            "new_resident_opportunity": _fmt(mobility, suffix="% moved in recently") if mobility else None,
        }

    def _marketer_description(self, feat, archetype, weight):
        income  = _get(feat, "median_household_income") or 0
        snap    = _get(feat, "snap_recipients") or 0
        gini    = _get(feat, "gini_ratio") or 0
        edu     = _get(feat, "educational_attainment") or 0
        single_p= _get(feat, "single_parent_families") or 0

        income_desc = (
            "high-income" if income > 100_000
            else "moderate-income" if income > 60_000
            else "lower-income" if income > 0
            else ""
        )
        inequality_desc = "with notable income inequality" if gini > 0.45 else ""
        edu_desc = "college-educated" if edu > 30 else ""
        family_desc = "with a significant single-parent household presence" if single_p > 30 else ""

        parts = [p for p in [income_desc, edu_desc] if p]
        desc = f"Primarily {', '.join(parts)} residents" if parts else f"Residents of this {archetype.lower()} area"
        if inequality_desc:
            desc += f" {inequality_desc}"
        if family_desc:
            desc += f", {family_desc}"
        desc += f". Represents {_weight_label(weight)} of this town's character."
        return desc

    def _audience_signals(self, feat):
        signals = []
        income = _get(feat, "median_household_income") or 0
        snap   = _get(feat, "snap_recipients") or 0
        gini   = _get(feat, "gini_ratio") or 0
        edu    = _get(feat, "educational_attainment") or 0
        mobility = _get(feat, "residential_mobility") or 0
        home_val = _get(feat, "median_home_value") or 0
        single_p = _get(feat, "single_parent_families") or 0

        if income > 120_000:
            signals.append({"signal": "Premium buyer segment", "strength": "high"})
        elif income > 75_000:
            signals.append({"signal": "Mid-market buyer", "strength": "medium"})
        if snap > 20:
            signals.append({"signal": "Price-sensitive segment — value messaging matters", "strength": "high"})
        if gini > 0.45:
            signals.append({"signal": "High income inequality — bifurcated market", "strength": "medium"})
        if edu > 40:
            signals.append({"signal": "Educated audience — research-driven purchases", "strength": "medium"})
        if mobility > 10:
            signals.append({"signal": "High residential mobility — new resident targeting", "strength": "medium"})
        if home_val > 500_000:
            signals.append({"signal": "High-value homeowners — premium home services", "strength": "high"})
        if single_p > 30:
            signals.append({"signal": "Single-parent households — value + convenience", "strength": "medium"})
        return signals

    def _messaging_angles(self, feat):
        angles = []
        income = _get(feat, "median_household_income") or 0
        snap   = _get(feat, "snap_recipients") or 0
        edu    = _get(feat, "educational_attainment") or 0
        mobility = _get(feat, "residential_mobility") or 0

        if income > 100_000:
            angles.append("Premium positioning works — quality over price messaging")
        if snap > 15:
            angles.append("Lead with value, savings, and community benefit")
        if edu > 35:
            angles.append("Data-driven messaging resonates — back claims with evidence")
        if mobility > 8:
            angles.append("'New to town?' onboarding campaigns have strong reach here")
        if not angles:
            angles.append("Community-focused messaging with local relevance")
        return angles

    def _channel_guidance(self, feat):
        income = _get(feat, "median_household_income") or 0
        edu    = _get(feat, "educational_attainment") or 0
        home_val = _get(feat, "median_home_value") or 0

        return {
            "digital":      "high" if edu > 35 else "medium",
            "social_media": "LinkedIn" if edu > 40 and income > 80_000 else "Facebook/Instagram",
            "direct_mail":  "high" if home_val > 300_000 else "low",
            "ott_streaming":"high" if income > 80_000 else "medium",
            "local_print":  "medium" if income > 60_000 else "low",
        }

    # ── Business persona ──────────────────────────────────────────────────────

    def _business_persona(self, feat, centroid, archetype, weight):
        income      = _get(feat, "median_household_income")
        home_val    = _get(feat, "median_home_value")
        rent        = _get(feat, "median_rent")
        formations  = _get(feat, "business_formations")
        employers   = _get(feat, "number_of_employers")
        employment  = _get(feat, "annual_average_employment")
        subsidized  = _get(feat, "total_assisted_units")
        permits     = _get(feat, "housing_permits")
        households  = _get(feat, "total_households")
        snap        = _get(feat, "snap_recipients")

        bpi = self._buying_power_index(feat)

        return {
            "archetype": archetype,
            "weight": round(weight, 3),
            "market_summary": self._market_summary(feat, archetype),
            "headline_stats": {
                k: v for k, v in {
                    "median_household_income": _fmt_currency(income),
                    "median_home_value":        _fmt_currency(home_val),
                    "median_rent":              _fmt_currency(rent),
                    "number_of_employers":      _fmt(employers, decimals=0),
                    "annual_avg_employment":    _fmt(employment, decimals=0),
                    "housing_permits":          _fmt(permits, decimals=0),
                    "total_households":         _fmt(households, decimals=0),
                }.items() if v is not None
            },
            "dominant_industries": [],
            "market_gaps": self._infer_gaps(feat),
            "buying_power_index": round(bpi, 1),
            "location_signals": self._location_signals(feat),
        }

    def _buying_power_index(self, feat):
        income   = _get(feat, "median_household_income") or 0
        home_val = _get(feat, "median_home_value") or 0
        edu      = _get(feat, "educational_attainment") or 0
        snap     = _get(feat, "snap_recipients") or 0

        income_score = min(income / 200_000 * 40, 40)
        home_score   = min(home_val / 1_000_000 * 30, 30)
        edu_score    = edu / 100 * 20
        snap_penalty = min(snap / 100 * 10, 10)

        return max(0, income_score + home_score + edu_score - snap_penalty)

    def _market_summary(self, feat, archetype):
        income    = _get(feat, "median_household_income")
        employers = _get(feat, "number_of_employers")
        households= _get(feat, "total_households")

        income_desc = (
            "high-income" if (income or 0) > 100_000
            else "moderate-income" if (income or 0) > 60_000
            else "lower-income"
        )
        parts = []
        if households:
            parts.append(f"~{households:,.0f} households")
        if employers:
            parts.append(f"{employers:,.0f} employers")
        if income:
            parts.append(f"median income {_fmt_currency(income)}")

        desc = f"A {income_desc} {archetype.lower()} market"
        if parts:
            desc += " with " + ", ".join(parts)
        return desc + "."

    def _infer_gaps(self, feat):
        gaps = []
        income   = _get(feat, "median_household_income") or 0
        home_val = _get(feat, "median_home_value") or 0
        snap     = _get(feat, "snap_recipients") or 0
        permits  = _get(feat, "housing_permits") or 0
        subsidized = _get(feat, "total_assisted_units") or 0

        if income > 80_000:
            gaps.append("Financial advisory / wealth management services")
        if home_val > 400_000:
            gaps.append("Premium home services (renovation, landscaping, design)")
        if snap > 20:
            gaps.append("Affordable grocery, childcare, and community services")
        if permits > 50:
            gaps.append("Home furnishing, moving, and new resident services")
        if subsidized > 200:
            gaps.append("Affordable healthcare and social support services")
        if not gaps:
            gaps.append("General retail and community services")
        return gaps[:4]

    def _location_signals(self, feat):
        signals = []
        formations = _get(feat, "business_formations") or 0
        mobility   = _get(feat, "residential_mobility") or 0
        permits    = _get(feat, "housing_permits") or 0
        snap       = _get(feat, "snap_recipients") or 0

        if formations > 50:
            signals.append({"signal": "Active business formation — growing ecosystem", "type": "positive"})
        if mobility > 10:
            signals.append({"signal": "Population inflow — expanding customer base", "type": "positive"})
        if permits > 100:
            signals.append({"signal": "New construction — growth signal", "type": "positive"})
        if snap > 25:
            signals.append({"signal": "High SNAP rate — price-sensitive market", "type": "caution"})
        return signals

    # ── Summary ───────────────────────────────────────────────────────────────

    def _town_summary(self, feat, sorted_archetypes):
        dominant = sorted_archetypes[0][0]
        dominant_pct = round(sorted_archetypes[0][1] * 100)
        town = feat.get("town", "This town")

        # Use whatever fields are available
        stats = []
        income = _get(feat, "median_household_income")
        home_val = _get(feat, "median_home_value")
        employers = _get(feat, "number_of_employers")
        households = _get(feat, "total_households")

        if income:
            stats.append(f"median household income {_fmt_currency(income)}")
        if home_val:
            stats.append(f"median home value {_fmt_currency(home_val)}")
        if employers:
            stats.append(f"{employers:,.0f} employers")
        if households:
            stats.append(f"{households:,.0f} households")

        summary = f"{town} is predominantly characterized as '{dominant}' ({dominant_pct}% match)."
        if stats:
            summary += " " + ", ".join(stats[:3]).capitalize() + "."
        return summary

    def build_all_towns(self, features_df, clusters_df, centroids_df, year=None):
        year = year or int(features_df["year"].max())
        towns = features_df[features_df["year"] == year]["town"].unique()
        records = []

        for town in towns:
            payload = self.build_town_personas(features_df, clusters_df, centroids_df, town, year)
            records.append({"town": town, "year": year, "payload": json.dumps(payload)})

        import pandas as pd
        result = pd.DataFrame(records)
        path = PROCESSED_DIR / f"town_personas_{year}.parquet"
        result.to_parquet(path, index=False)
        logger.info(f"All town personas saved → {path}")
        return result


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get(feat, key):
    """Safely get a value from a Series, returning None if missing or NaN."""
    val = feat.get(key)
    if val is None:
        return None
    try:
        if np.isnan(float(val)):
            return None
        return float(val)
    except (TypeError, ValueError):
        return None


def _fmt(val, suffix="", decimals=1):
    if val is None:
        return None
    return f"{val:,.{decimals}f}{suffix}"


def _fmt_currency(val):
    if val is None:
        return None
    return f"${val:,.0f}"


def _weight_label(weight):
    if weight > 0.75:
        return "a strong majority"
    if weight > 0.50:
        return "a majority"
    return "a plurality"
