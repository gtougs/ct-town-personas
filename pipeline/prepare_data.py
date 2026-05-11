"""
pipeline/prepare_data.py

Data preparation script that:
1. Filters county/state rows from feature store
2. Deduplicates to one row per town per year  
3. Adds IRS SOI zip-level income bracket data
4. Builds enriched time series (Zillow + SOTS business)
5. Re-runs clustering with corrected archetype labels

Run: python -m pipeline.prepare_data
"""

import logging
import pandas as pd
import numpy as np
import requests
from pathlib import Path
from io import StringIO

logger = logging.getLogger(__name__)
PROCESSED = Path("data/processed")
RAW = Path("data/raw")

# ── Rows to exclude — not actual towns ────────────────────────────────────────
NOT_TOWNS = [
    "Connecticut",
    "Fairfield County", "Hartford County", "Litchfield County",
    "Middlesex County", "New Haven County", "New London County",
    "Tolland County", "Windham County",
]

# ── Corrected archetype labels based on actual cluster inspection ─────────────
# These are assigned AFTER fitting — update to match what you see in the data
ARCHETYPE_LABELS = {
    0: "Affluent Commuter Belt",
    1: "Working-Class Urban",
    2: "Rural & Small Town",
    3: "Young Professional Hub",
    4: "Mixed-Income Transitional",
}


def run():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )

    logger.info("=" * 60)
    logger.info("CT Town Personas — Data Preparation")
    logger.info("=" * 60)

    # ── Step 1: Clean feature store ───────────────────────────────────────────
    logger.info("\n[1/5] Cleaning feature store ...")
    df = pd.read_parquet(PROCESSED / "town_features_all_years.parquet")
    before = len(df)

    # Remove county/state rows
    df = df[~df["town"].isin(NOT_TOWNS)]
    # Also catch any "County" suffix we missed
    df = df[~df["town"].str.contains("County|Connecticut", na=False)]
    # Deduplicate
    df = df.drop_duplicates(subset=["town", "year"], keep="last")

    logger.info(f"  Removed {before - len(df)} non-town rows")
    logger.info(f"  Clean: {df['town'].nunique()} towns × {df['year'].nunique()} years")
    df.to_parquet(PROCESSED / "town_features_all_years.parquet", index=False)

    # ── Step 2: IRS SOI income distribution ───────────────────────────────────
    logger.info("\n[2/5] Adding IRS SOI income distribution ...")
    irs_df = _fetch_irs_soi()
    if irs_df is not None:
        irs_path = PROCESSED / "irs_income_distribution.parquet"
        irs_df.to_parquet(irs_path, index=False)
        logger.info(f"  IRS SOI saved → {irs_path} ({irs_df.shape})")
    else:
        logger.warning("  IRS SOI fetch failed — skipping")

    # ── Step 3: Rebuild Zillow time series ─────────────────────────────────────
    logger.info("\n[3/5] Rebuilding enriched time series ...")
    _rebuild_enriched(df)

    # ── Step 4: Re-cluster with clean data ────────────────────────────────────
    logger.info("\n[4/5] Re-clustering towns ...")
    year_features = df[df["year"] == df["year"].max()].copy()
    _recluster(year_features)

    # ── Step 5: Rebuild personas ───────────────────────────────────────────────
    logger.info("\n[5/5] Rebuilding persona cards ...")
    clusters = pd.read_parquet(PROCESSED / "town_clusters.parquet")
    centroids = pd.read_parquet(PROCESSED / "cluster_centroids.parquet")
    from pipeline.persona import PersonaBuilder
    PersonaBuilder().build_all_towns(year_features, clusters, centroids, year=int(year_features["year"].max()))

    logger.info("\n✓ Data preparation complete.")
    _print_cluster_summary()


def _fetch_irs_soi() -> pd.DataFrame:
    """
    Pull IRS Statistics of Income zip-level data.
    Maps zip codes to CT towns using USPS zip-to-town crosswalk.
    Returns income bracket distribution by town.
    """
    try:
        # IRS SOI 2020 zip-level data (most recent available)
        url = "https://www.irs.gov/pub/irs-soi/20zpallagi.csv"
        logger.info(f"  Fetching IRS SOI from {url} ...")
        resp = requests.get(url, timeout=60, stream=True)
        resp.raise_for_status()

        # Read relevant columns only
        chunks = []
        for chunk in pd.read_csv(
            StringIO(resp.text),
            usecols=["STATE", "zipcode", "N1", "N2", "A00100",
                     "N1", "mars1", "mars2", "NUMDEP",
                     "A00200", "N00200",   # wages
                     "A00300", "N00300"],  # dividends (wealth proxy)
            chunksize=50_000,
            low_memory=False,
        ):
            ct_chunk = chunk[chunk["STATE"] == "CT"]
            if not ct_chunk.empty:
                chunks.append(ct_chunk)

        if not chunks:
            return None

        irs = pd.concat(chunks, ignore_index=True)

        # Map CT zip codes to towns using a simple lookup
        irs = _map_zips_to_towns(irs)
        if irs is None:
            return None

        # Aggregate to town level
        town_irs = irs.groupby("town").agg(
            total_returns=("N1", "sum"),
            total_exemptions=("N2", "sum"),
            total_agi=("A00100", "sum"),
            total_wages=("A00200", "sum"),
            wage_returns=("N00200", "sum"),
            dividend_returns=("N00300", "sum"),
            total_dividends=("A00300", "sum"),
        ).reset_index()

        # Derived metrics
        town_irs["avg_agi_per_return"] = town_irs["total_agi"] / town_irs["total_returns"].replace(0, np.nan) * 1000
        town_irs["avg_wage_per_return"] = town_irs["total_wages"] / town_irs["wage_returns"].replace(0, np.nan) * 1000
        town_irs["pct_dividend_filers"] = town_irs["dividend_returns"] / town_irs["total_returns"].replace(0, np.nan) * 100
        town_irs["irs_year"] = 2020

        return town_irs

    except Exception as e:
        logger.error(f"  IRS SOI error: {e}")
        return None


def _map_zips_to_towns(df: pd.DataFrame) -> pd.DataFrame:
    """Map CT zip codes to town names using HUD crosswalk or simple lookup."""
    # CT zip-to-town mapping (major zips)
    ZIP_TO_TOWN = {
        "06001": "Avon", "06002": "Bloomfield", "06010": "Bristol",
        "06013": "Burlington", "06016": "East Windsor", "06019": "Canton",
        "06020": "Canton", "06021": "Colebrook", "06022": "Granby",
        "06023": "East Granby", "06024": "Norfolk", "06025": "East Hartford",
        "06026": "East Granby", "06027": "East Hartland", "06028": "East Windsor",
        "06029": "Ellington", "06030": "Farmington", "06031": "Falls Village",
        "06032": "Farmington", "06033": "Glastonbury", "06034": "Farmington",
        "06035": "Granby", "06037": "Berlin", "06039": "Lakeville",
        "06040": "Manchester", "06041": "Manchester", "06042": "Manchester",
        "06043": "Bolton", "06045": "Manchester", "06050": "New Britain",
        "06051": "New Britain", "06052": "New Britain", "06053": "New Britain",
        "06057": "New Hartford", "06058": "Norfolk", "06059": "North Canton",
        "06060": "North Granby", "06061": "Pine Meadow", "06062": "Plainville",
        "06063": "Barkhamsted", "06064": "Poquonock", "06065": "Riverton",
        "06066": "Vernon", "06067": "Rocky Hill", "06068": "Salisbury",
        "06069": "Sharon", "06070": "Simsbury", "06071": "Somers",
        "06072": "Somersville", "06073": "South Glastonbury", "06074": "South Windsor",
        "06075": "Stafford", "06076": "Staffordville", "06077": "Stafford Springs",
        "06078": "Suffield", "06079": "Taconic", "06080": "Suffield",
        "06081": "Tariffville", "06082": "Enfield", "06083": "Enfield",
        "06084": "Tolland", "06085": "Unionville", "06087": "Unionville",
        "06088": "East Windsor", "06089": "Weatogue", "06090": "West Granby",
        "06091": "West Hartland", "06092": "West Simsbury", "06093": "West Suffield",
        "06095": "Windsor", "06096": "Windsor Locks", "06098": "Winsted",
        "06101": "Hartford", "06102": "Hartford", "06103": "Hartford",
        "06104": "Hartford", "06105": "Hartford", "06106": "Hartford",
        "06107": "West Hartford", "06108": "East Hartford", "06109": "Wethersfield",
        "06110": "West Hartford", "06111": "Newington", "06112": "Hartford",
        "06114": "Hartford", "06115": "Hartford", "06117": "West Hartford",
        "06118": "East Hartford", "06119": "West Hartford", "06120": "Hartford",
        "06160": "Hartford", "06176": "Hartford",
        "06201": "Ansonia", "06226": "Willimantic", "06231": "Amston",
        "06232": "Andover", "06233": "Brooklyn", "06234": "Brooklyn",
        "06235": "Chaplin", "06237": "Columbia", "06238": "Coventry",
        "06239": "Danielson", "06241": "Dayville", "06242": "Eastford",
        "06243": "East Killingly", "06244": "East Woodstock", "06245": "Fabyan",
        "06246": "Grosvenordale", "06247": "Hampton", "06248": "Hebron",
        "06249": "Lebanon", "06250": "Mansfield", "06251": "Mansfield Center",
        "06254": "North Franklin", "06255": "North Grosvenordale",
        "06256": "North Windham", "06258": "Pomfret", "06259": "Pomfret Center",
        "06260": "Putnam", "06262": "Quinebaug", "06263": "Rogers",
        "06264": "Scotland", "06265": "South Killingly", "06266": "South Windham",
        "06267": "South Woodstock", "06268": "Storrs", "06269": "Storrs",
        "06277": "Thompson", "06278": "Ashford", "06279": "Willington",
        "06280": "Windham", "06281": "Woodstock", "06282": "Woodstock Valley",
        "06320": "New London", "06330": "Baltic", "06331": "Canterbury",
        "06332": "Central Village", "06333": "East Lyme", "06334": "Bozrah",
        "06335": "Gales Ferry", "06336": "Gilman", "06338": "Moosup",
        "06339": "Mystic", "06340": "Groton", "06349": "Groton",
        "06350": "Hanover", "06351": "Jewett City", "06353": "Montville",
        "06354": "Moosup", "06355": "Mystic", "06357": "Niantic",
        "06359": "North Stonington", "06360": "Norwich", "06365": "Preston",
        "06370": "Oakdale", "06371": "Old Lyme", "06372": "Old Mystic",
        "06373": "Oneco", "06374": "Plainfield", "06375": "Quaker Hill",
        "06376": "South Lyme", "06377": "Sterling", "06378": "Stonington",
        "06379": "Pawcatuck", "06380": "Taftville", "06382": "Uncasville",
        "06383": "Versailles", "06384": "Voluntown", "06385": "Waterford",
        "06387": "Wauregan", "06388": "West Mystic", "06389": "Yantic",
        "06401": "Ansonia", "06403": "Beacon Falls", "06405": "Branford",
        "06408": "Cheshire", "06409": "Centerbrook", "06410": "Cheshire",
        "06411": "Cheshire", "06412": "Chester", "06413": "Clinton",
        "06414": "Cobalt", "06415": "Colchester", "06416": "Cromwell",
        "06417": "Deep River", "06418": "Derby", "06419": "Killingworth",
        "06420": "Salem", "06422": "Durham", "06423": "East Haddam",
        "06424": "East Hampton", "06426": "Essex", "06437": "Guilford",
        "06438": "Haddam", "06439": "Hadlyme", "06440": "Hawleyville",
        "06441": "Higganum", "06442": "Ivoryton", "06443": "Madison",
        "06444": "Marion", "06447": "Marlborough", "06450": "Meriden",
        "06451": "Meriden", "06455": "Middlefield", "06456": "Middle Haddam",
        "06457": "Middletown", "06459": "Middletown", "06460": "Milford",
        "06461": "Milford", "06467": "Milldale", "06468": "Monroe",
        "06469": "Moodus", "06470": "Newtown", "06471": "North Branford",
        "06472": "North Branford", "06473": "North Haven", "06474": "North Madison",
        "06475": "Old Saybrook", "06477": "Orange", "06478": "Oxford",
        "06479": "Plantsville", "06480": "Portland", "06481": "Rockfall",
        "06482": "Sandy Hook", "06483": "Seymour", "06484": "Shelton",
        "06487": "Southbury", "06488": "Southbury", "06489": "Southington",
        "06491": "Stevenson", "06492": "Wallingford", "06494": "Wallingford",
        "06495": "Wallingford", "06498": "Westbrook", "06501": "New Haven",
        "06502": "New Haven", "06503": "New Haven", "06504": "New Haven",
        "06505": "New Haven", "06506": "New Haven", "06507": "New Haven",
        "06508": "New Haven", "06509": "New Haven", "06510": "New Haven",
        "06511": "New Haven", "06512": "East Haven", "06513": "New Haven",
        "06514": "Hamden", "06515": "New Haven", "06516": "West Haven",
        "06517": "Hamden", "06518": "Hamden", "06519": "New Haven",
        "06524": "Bethany", "06525": "Woodbridge", "06530": "New Haven",
        "06531": "New Haven", "06532": "New Haven", "06533": "New Haven",
        "06534": "New Haven", "06535": "New Haven", "06536": "New Haven",
        "06537": "New Haven", "06538": "New Haven", "06540": "New Haven",
        "06601": "Bridgeport", "06602": "Bridgeport", "06604": "Bridgeport",
        "06605": "Bridgeport", "06606": "Bridgeport", "06607": "Bridgeport",
        "06608": "Bridgeport", "06610": "Bridgeport", "06611": "Trumbull",
        "06612": "Easton", "06614": "Stratford", "06615": "Stratford",
        "06708": "Waterbury", "06710": "Waterbury", "06712": "Prospect",
        "06716": "Wolcott", "06720": "Waterbury", "06721": "Waterbury",
        "06722": "Waterbury", "06723": "Waterbury", "06724": "Waterbury",
        "06725": "Waterbury", "06726": "Waterbury", "06749": "Waterbury",
        "06750": "Bantam", "06751": "Bethlehem", "06752": "Bridgewater",
        "06753": "Cornwall", "06754": "Cornwall Bridge", "06755": "Gaylordsville",
        "06756": "Goshen", "06757": "Kent", "06758": "Lakeville",
        "06759": "Litchfield", "06762": "Middlebury", "06763": "Morris",
        "06770": "Naugatuck", "06776": "New Milford", "06777": "New Preston",
        "06778": "Northfield", "06779": "Oakville", "06781": "Pequabuck",
        "06782": "Plymouth", "06783": "Roxbury", "06784": "Sherman",
        "06785": "South Kent", "06786": "Terryville", "06787": "Thomaston",
        "06788": "Torrington", "06790": "Torrington", "06791": "Harwinton",
        "06793": "Washington", "06794": "Washington Depot",
        "06795": "Watertown", "06796": "West Cornwall", "06798": "Woodbury",
        "06801": "Bethel", "06804": "Brookfield", "06807": "Cos Cob",
        "06810": "Danbury", "06811": "Danbury", "06812": "New Fairfield",
        "06813": "Danbury", "06814": "Danbury", "06816": "Danbury",
        "06817": "Danbury", "06820": "Darien", "06824": "Fairfield",
        "06825": "Fairfield", "06829": "Georgetown", "06830": "Greenwich",
        "06831": "Greenwich", "06836": "Greenwich", "06838": "Greenwich",
        "06840": "New Canaan", "06850": "Norwalk", "06851": "Norwalk",
        "06852": "Norwalk", "06853": "Norwalk", "06854": "Norwalk",
        "06855": "Norwalk", "06856": "Norwalk", "06857": "Norwalk",
        "06858": "Norwalk", "06860": "Norwalk", "06870": "Old Greenwich",
        "06875": "Redding", "06876": "Redding Ridge", "06877": "Ridgefield",
        "06878": "Riverside", "06879": "Ridgefield", "06880": "Westport",
        "06881": "Westport", "06883": "Weston", "06888": "Westport",
        "06889": "Westport", "06890": "Southport", "06896": "Redding",
        "06897": "Wilton", "06901": "Stamford", "06902": "Stamford",
        "06903": "Stamford", "06904": "Stamford", "06905": "Stamford",
        "06906": "Stamford", "06907": "Stamford",
    }

    df = df.copy()
    df["zipcode"] = df["zipcode"].astype(str).str.zfill(5)
    df["town"] = df["zipcode"].map(ZIP_TO_TOWN)
    df = df.dropna(subset=["town"])
    return df


def _rebuild_enriched(features_df: pd.DataFrame):
    """Rebuild enriched time series with clean town list."""
    from ingestion.ctdata_client import CTDataClient

    ZILLOW_ID = "1e3233e0-e442-4401-bf5d-3835a591fd3e"
    valid_towns = set(features_df["town"].unique())

    try:
        ct = CTDataClient()
        df = ct.fetch_by_resource_id(ZILLOW_ID)
        year_cols = [c for c in df.columns if c.isdigit()]
        zillow = df[["Town"] + year_cols].rename(columns={"Town": "town"})
        zillow["town"] = zillow["town"].str.strip().str.title()
        zillow = zillow[zillow["town"].isin(valid_towns)]
        zillow = zillow.melt(id_vars=["town"], value_vars=year_cols,
                              var_name="year", value_name="value")
        zillow["year"] = zillow["year"].astype(int)
        zillow["value"] = pd.to_numeric(zillow["value"], errors="coerce")
        zillow = zillow.dropna(subset=["value"])
        zillow["indicator"] = "zillow_home_value"

        enriched = zillow[["town", "year", "indicator", "value"]]
        enriched.to_parquet(PROCESSED / "enriched_timeseries.parquet", index=False)
        logger.info(f"  Zillow: {enriched['town'].nunique()} towns, {sorted(enriched['year'].unique())}")
    except Exception as e:
        logger.warning(f"  Zillow rebuild failed: {e}")


def _recluster(year_features: pd.DataFrame):
    """Re-run clustering with updated archetype labels."""
    import sys
    sys.path.insert(0, ".")
    from pipeline.cluster import TownClusterer

    clusterer = TownClusterer(n_clusters=5)
    clusters = clusterer.fit_predict(year_features)

    # Print what's in each cluster so we can rename intelligently
    logger.info("\n  Cluster contents:")
    for cid in sorted(clusters["cluster_id"].unique()):
        towns = clusters[clusters["cluster_id"] == cid]["town"].tolist()
        label = clusters[clusters["cluster_id"] == cid]["archetype_label"].iloc[0]
        logger.info(f"  [{cid}] {label}: {towns[:8]}{'...' if len(towns) > 8 else ''}")


def _print_cluster_summary():
    clusters = pd.read_parquet(PROCESSED / "town_clusters.parquet")
    logger.info("\nFinal cluster distribution:")
    print(clusters.groupby("archetype_label")["town"].count().to_string())
    logger.info("\nSpot check:")
    for town in ["Greenwich", "Hartford", "Andover", "Westport", "Bridgeport", "Stamford"]:
        row = clusters[clusters["town"] == town]
        if not row.empty:
            r = row.iloc[0]
            logger.info(f"  {town:<15} → {r['archetype_label']}")


if __name__ == "__main__":
    run()
