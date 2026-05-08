"""
pipeline/generate_mock.py
Generates realistic synthetic data for all 169 CT towns so you can run
the full app stack — API + frontend — without Census or Socrata API keys.

This is NOT for production. It exists solely to let you:
  - validate the pipeline works end to end
  - demo the frontend to stakeholders
  - develop and test the UI before real data is wired

Real data will naturally replace this when you run: make pipeline

Usage: python -m pipeline.generate_mock
       make mock
"""

import json
import logging
import numpy as np
import pandas as pd
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger("mock")

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"

# All 169 Connecticut towns
CT_TOWNS = [
    "Andover", "Ansonia", "Ashford", "Avon", "Barkhamsted", "Beacon Falls",
    "Berlin", "Bethany", "Bethel", "Bethlehem", "Bloomfield", "Bolton",
    "Bozrah", "Branford", "Bridgeport", "Bridgewater", "Bristol", "Brookfield",
    "Brooklyn", "Burlington", "Canaan", "Canterbury", "Canton", "Chaplin",
    "Cheshire", "Chester", "Clinton", "Colchester", "Colebrook", "Columbia",
    "Cornwall", "Coventry", "Cromwell", "Danbury", "Darien", "Deep River",
    "Derby", "Durham", "Eastford", "East Granby", "East Haddam", "East Hampton",
    "East Hartford", "East Haven", "East Lyme", "East Windsor", "Ellington",
    "Enfield", "Essex", "Fairfield", "Farmington", "Franklin", "Glastonbury",
    "Goshen", "Granby", "Greenwich", "Griswold", "Groton", "Guilford",
    "Haddam", "Hamden", "Hampton", "Hartford", "Hartland", "Harwinton",
    "Hebron", "Kent", "Killingly", "Killingworth", "Lebanon", "Ledyard",
    "Lisbon", "Litchfield", "Lyme", "Madison", "Manchester", "Mansfield",
    "Marlborough", "Meriden", "Middlebury", "Middlefield", "Middletown",
    "Milford", "Monroe", "Montville", "Morris", "Naugatuck", "New Britain",
    "New Canaan", "New Fairfield", "New Hartford", "New Haven", "Newington",
    "New London", "New Milford", "Newtown", "Norfolk", "North Branford",
    "North Canaan", "North Haven", "North Stonington", "Norwalk", "Norwich",
    "Old Lyme", "Old Saybrook", "Orange", "Oxford", "Plainfield", "Plainville",
    "Plymouth", "Pomfret", "Portland", "Preston", "Prospect", "Putnam",
    "Redding", "Ridgefield", "Rocky Hill", "Roxbury", "Salem", "Salisbury",
    "Scotland", "Seymour", "Sharon", "Shelton", "Sherman", "Simsbury",
    "Somers", "South Windsor", "Southbury", "Southington", "Sprague",
    "Stafford", "Stamford", "Sterling", "Stonington", "Stratford", "Suffield",
    "Thomaston", "Thompson", "Tolland", "Torrington", "Trumbull", "Union",
    "Vernon", "Voluntown", "Wallingford", "Warren", "Washington", "Waterbury",
    "Waterford", "Watertown", "West Hartford", "West Haven", "Westbrook",
    "Weston", "Westport", "Wethersfield", "Willington", "Wilton", "Winchester",
    "Windham", "Windsor", "Windsor Locks", "Wolcott", "Woodbridge",
    "Woodbury", "Woodstock",
]

# Town archetype seeds — drives which "type" of profile each town gets
# Based loosely on real CT geography
ARCHETYPES = {
    "Affluent Suburban": {
        "towns": ["Greenwich", "Darien", "New Canaan", "Westport", "Wilton", "Ridgefield",
                  "Weston", "Fairfield", "Woodbridge", "Orange", "Simsbury", "Glastonbury",
                  "Avon", "Farmington", "West Hartford", "Madison"],
        "params": dict(
            median_age=(44, 3), median_household_income=(175000, 35000),
            median_home_value=(950000, 200000), median_gross_rent=(2400, 400),
            pct_owner_occupied=(78, 5), vacancy_rate=(4, 1.5),
            pct_bachelors_or_higher=(68, 6), pct_graduate_degree=(35, 6),
            pct_wfh=(32, 6), unemployment_rate=(3.2, 0.8),
            businesses_per_1k=(28, 6), business_formation_rate=(0.12, 0.03),
            total_population=(18000, 8000), pct_in_migration=(4.2, 1.2),
        )
    },
    "Working-Class Urban": {
        "towns": ["Bridgeport", "New Haven", "Hartford", "Waterbury", "New Britain",
                  "Meriden", "Norwich", "New London", "Ansonia", "Derby",
                  "Naugatuck", "Putnam", "Windham", "Killingly"],
        "params": dict(
            median_age=(34, 4), median_household_income=(42000, 9000),
            median_home_value=(185000, 40000), median_gross_rent=(1050, 150),
            pct_owner_occupied=(35, 8), vacancy_rate=(14, 4),
            pct_bachelors_or_higher=(22, 6), pct_graduate_degree=(8, 3),
            pct_wfh=(12, 4), unemployment_rate=(9.5, 2.5),
            businesses_per_1k=(18, 5), business_formation_rate=(0.09, 0.03),
            total_population=(55000, 35000), pct_in_migration=(6.8, 2.0),
        )
    },
    "Rural / Small Town": {
        "towns": ["Andover", "Ashford", "Barkhamsted", "Bethlehem", "Bolton", "Bozrah",
                  "Canaan", "Canterbury", "Chaplin", "Colebrook", "Columbia", "Cornwall",
                  "Eastford", "Franklin", "Goshen", "Hampton", "Hartland", "Hebron",
                  "Kent", "Lebanon", "Lisbon", "Lyme", "Marlborough", "Morris",
                  "Norfolk", "North Canaan", "North Stonington", "Pomfret", "Preston",
                  "Roxbury", "Salem", "Salisbury", "Scotland", "Sharon", "Sherman",
                  "Sprague", "Sterling", "Tolland", "Union", "Voluntown",
                  "Warren", "Washington", "Willington", "Winchester", "Woodstock"],
        "params": dict(
            median_age=(47, 5), median_household_income=(72000, 15000),
            median_home_value=(290000, 70000), median_gross_rent=(1100, 200),
            pct_owner_occupied=(82, 5), vacancy_rate=(8, 3),
            pct_bachelors_or_higher=(32, 8), pct_graduate_degree=(14, 5),
            pct_wfh=(18, 5), unemployment_rate=(5.2, 1.5),
            businesses_per_1k=(12, 4), business_formation_rate=(0.07, 0.02),
            total_population=(3500, 2500), pct_in_migration=(3.1, 1.0),
        )
    },
    "Young Professional": {
        "towns": ["Stamford", "Norwalk", "Hamden", "West Haven", "Milford",
                  "Stratford", "Shelton", "Middletown", "Manchester", "Vernon",
                  "Enfield", "Groton", "Storrs", "Mansfield"],
        "params": dict(
            median_age=(34, 3), median_household_income=(88000, 18000),
            median_home_value=(420000, 80000), median_gross_rent=(1750, 300),
            pct_owner_occupied=(52, 8), vacancy_rate=(6, 2),
            pct_bachelors_or_higher=(48, 8), pct_graduate_degree=(20, 5),
            pct_wfh=(28, 7), unemployment_rate=(4.8, 1.2),
            businesses_per_1k=(22, 5), business_formation_rate=(0.14, 0.04),
            total_population=(42000, 25000), pct_in_migration=(7.5, 2.5),
        )
    },
    "Mixed-Income Transitional": {
        "towns": [],  # remainder
        "params": dict(
            median_age=(41, 4), median_household_income=(95000, 22000),
            median_home_value=(380000, 90000), median_gross_rent=(1500, 300),
            pct_owner_occupied=(65, 8), vacancy_rate=(6, 2.5),
            pct_bachelors_or_higher=(40, 9), pct_graduate_degree=(18, 6),
            pct_wfh=(22, 6), unemployment_rate=(5.5, 1.5),
            businesses_per_1k=(20, 5), business_formation_rate=(0.10, 0.03),
            total_population=(22000, 15000), pct_in_migration=(5.0, 1.8),
        )
    },
}

NAICS_BY_ARCHETYPE = {
    "Affluent Suburban":         ["Professional Services", "Real Estate", "Finance & Insurance"],
    "Working-Class Urban":       ["Healthcare", "Retail Trade", "Administrative Services"],
    "Rural / Small Town":        ["Construction", "Agriculture & Forestry", "Other Services"],
    "Young Professional":        ["Information & Media", "Professional Services", "Hospitality & Food"],
    "Mixed-Income Transitional": ["Healthcare", "Retail Trade", "Professional Services"],
}


def _assign_archetypes():
    assignment = {}
    for arch, cfg in ARCHETYPES.items():
        for t in cfg["towns"]:
            assignment[t] = arch
    for t in CT_TOWNS:
        if t not in assignment:
            assignment[t] = "Mixed-Income Transitional"
    return assignment


def _sample(mu, sigma, n=1, lo=None, hi=None):
    rng = np.random.default_rng(hash(str(mu) + str(sigma)) % (2**32))
    vals = rng.normal(mu, sigma, n)
    if lo is not None: vals = np.maximum(vals, lo)
    if hi is not None: vals = np.minimum(vals, hi)
    return vals if n > 1 else float(vals[0])


def generate_features(years=(2018, 2019, 2020, 2021, 2022)) -> pd.DataFrame:
    """Generate a town × year feature DataFrame with realistic per-archetype distributions."""
    logger.info(f"Generating features for {len(CT_TOWNS)} towns × {len(years)} years ...")
    archetype_map = _assign_archetypes()
    rng = np.random.default_rng(42)
    rows = []

    for town in CT_TOWNS:
        arch = archetype_map[town]
        params = ARCHETYPES[arch]["params"]
        naics = NAICS_BY_ARCHETYPE[arch]

        # Town-level noise seed (persistent across years)
        town_seed = rng.normal(0, 0.15, len(params))

        for i, year in enumerate(years):
            # Small year-over-year drift
            drift = 1.0 + (i * rng.uniform(0.005, 0.025))
            row = {"town": town, "year": year, "archetype_label": arch}

            for j, (feat, (mu, sigma)) in enumerate(params.items()):
                base = mu * (1 + town_seed[j] * 0.5)
                val = rng.normal(base * drift, sigma * 0.3)
                # Clip percentage columns
                if feat.startswith("pct_"):
                    val = float(np.clip(val, 0, 99))
                elif feat in ("unemployment_rate", "vacancy_rate"):
                    val = float(np.clip(val, 0, 30))
                elif feat in ("median_household_income", "median_home_value"):
                    val = float(max(val, 25000))
                else:
                    val = float(max(val, 0))
                row[feat] = round(val, 2)

            # Derived columns
            row["per_capita_income"] = round(row["median_household_income"] * rng.uniform(0.45, 0.65), 0)
            row["affordability_ratio"] = round((row["median_gross_rent"] * 12) / row["median_household_income"], 3)
            row["pct_hs_or_higher"] = round(min(row["pct_bachelors_or_higher"] + rng.uniform(20, 35), 99), 1)
            row["pct_owner_occupied"] = round(float(np.clip(row["pct_owner_occupied"], 10, 95)), 1)
            row["pct_insured"] = round(float(np.clip(rng.normal(93, 4), 70, 99)), 1)
            row["pct_disabled"] = round(float(np.clip(rng.normal(10, 3), 2, 25)), 1)
            row["pct_no_vehicle"] = round(float(np.clip(rng.normal(8, 5), 0, 35)), 1)
            row["pct_same_house"] = round(float(np.clip(rng.normal(85, 5), 60, 97)), 1)
            row["pct_interstate_in"] = round(float(np.clip(rng.normal(2, 1), 0, 10)), 1)
            row["pct_white"] = round(float(np.clip(rng.normal(65, 20), 5, 95)), 1)
            row["pct_black"] = round(float(np.clip(rng.normal(12, 10), 0, 60)), 1)
            row["pct_hispanic"] = round(float(np.clip(rng.normal(16, 12), 0, 60)), 1)
            row["pct_asian"] = round(float(np.clip(rng.normal(5, 4), 0, 30)), 1)
            row["pct_foreign_born"] = round(float(np.clip(rng.normal(14, 9), 0, 45)), 1)
            row["median_year_built"] = round(float(np.clip(rng.normal(1972, 15), 1900, 2020)), 0)
            row["pct_single_family"] = round(float(np.clip(rng.normal(65, 20), 10, 95)), 1)
            row["mean_commute_score"] = round(float(np.clip(rng.normal(15, 8), 0, 50)), 1)
            row["business_dissolution_rate"] = round(float(np.clip(row["business_formation_rate"] * rng.uniform(0.3, 0.7), 0, 0.5)), 3)
            row["business_survival_score"] = round(1 - row["business_dissolution_rate"], 3)
            row["population_growth_rate"] = round(float(rng.normal(0.8, 1.5)), 2)
            row["top_naics_1"] = naics[0]
            row["top_naics_2"] = naics[1] if len(naics) > 1 else None
            row["top_naics_3"] = naics[2] if len(naics) > 2 else None
            row["active_businesses"] = int(max(row["total_population"] * row["businesses_per_1k"] / 1000, 5))

            rows.append(row)

    return pd.DataFrame(rows)


def generate_clusters(features_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Assign cluster IDs matching archetype labels, compute PCA-like 2D coords."""
    import json
    from sklearn.preprocessing import StandardScaler
    from sklearn.decomposition import PCA

    ARCHETYPE_IDS = {
        "Affluent Suburban":         0,
        "Working-Class Urban":       1,
        "Rural / Small Town":        2,
        "Young Professional":        3,
        "Mixed-Income Transitional": 4,
    }

    latest = features_df[features_df["year"] == features_df["year"].max()].copy()

    numeric_cols = [c for c in latest.columns if latest[c].dtype in (float, int)
                    and c not in ("year",) and not c.startswith("top_")]
    X = latest[numeric_cols].fillna(latest[numeric_cols].median())
    X_scaled = StandardScaler().fit_transform(X)
    coords = PCA(n_components=2, random_state=42).fit_transform(X_scaled)

    cluster_df = pd.DataFrame({
        "town":               latest["town"].values,
        "year":               latest["year"].values,
        "cluster_id":         latest["archetype_label"].map(ARCHETYPE_IDS).values,
        "archetype_label":    latest["archetype_label"].values,
        "dominant_persona_pct": np.random.default_rng(42).uniform(0.55, 0.85, len(latest)),
        "pca_x":              coords[:, 0],
        "pca_y":              coords[:, 1],
    })

    # GMM-style soft probabilities (dominant archetype gets bulk of weight)
    probs_list = []
    rng = np.random.default_rng(42)
    for cid in cluster_df["cluster_id"]:
        probs = rng.dirichlet([8 if i == cid else 1 for i in range(5)])
        probs_list.append(json.dumps({
            list(ARCHETYPE_IDS.keys())[i]: round(float(p), 3)
            for i, p in enumerate(probs)
        }))
    cluster_df["persona_probs"] = probs_list

    # Centroids
    centroids = (
        latest.merge(cluster_df[["town", "cluster_id", "archetype_label"]], on="town")
              .groupby(["cluster_id", "archetype_label"])[numeric_cols]
              .mean()
              .reset_index()
    )
    for arch, cid in ARCHETYPE_IDS.items():
        rep = cluster_df[cluster_df["cluster_id"] == cid].nlargest(3, "dominant_persona_pct")["town"].tolist()
        centroids.loc[centroids["cluster_id"] == cid, "representative_towns"] = json.dumps(rep)

    return cluster_df, centroids


def run():
    logger.info("Generating mock data for CT Town Personas ...")
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    features_df = generate_features(years=(2018, 2019, 2020, 2021, 2022))
    features_df.to_parquet(PROCESSED_DIR / "town_features_all_years.parquet", index=False)
    logger.info(f"  ✓ Features: {features_df.shape}")

    clusters_df, centroids_df = generate_clusters(features_df)
    clusters_df.to_parquet(PROCESSED_DIR / "town_clusters.parquet", index=False)
    centroids_df.to_parquet(PROCESSED_DIR / "cluster_centroids.parquet", index=False)
    logger.info(f"  ✓ Clusters: {clusters_df['cluster_id'].nunique()} archetypes")

    # Pre-generate persona cards for all towns
    from pipeline.persona import PersonaBuilder
    year = int(features_df["year"].max())
    PersonaBuilder().build_all_towns(
        features_df[features_df["year"] == year],
        clusters_df, centroids_df, year=year
    )
    logger.info(f"  ✓ Persona cards: {len(CT_TOWNS)} towns")
    logger.info(f"\n✓ Mock data ready in {PROCESSED_DIR}")
    logger.info("  Run: make api   (then: make frontend)")


if __name__ == "__main__":
    run()
