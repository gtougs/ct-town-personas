"""
pipeline/run_all.py — memory-safe orchestrator
"""

import logging
import sys
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.ctdata_client import CTDataClient
from ingestion.lodes_client import LODESClient
from ingestion.socrata_client import SocrataClient
from pipeline.feature_builder import FeatureBuilder
from pipeline.cluster import TownClusterer
from pipeline.persona import PersonaBuilder

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("run_all")

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"


def run(year: int = 2022, n_clusters: int = 5):
    logger.info("=" * 60)
    logger.info(f"CT Town Personas Pipeline — {year}")
    logger.info("=" * 60)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # ── 1. Ingest CTData ─────────────────────────────────────────────────────
    logger.info("\n[1/5] Ingesting from data.ctdata.org ...")
    ct = CTDataClient()
    wide_frames = []

    for name, cfg in ct.datasets.items():
        try:
            df_raw = ct.fetch(name)
            if df_raw.empty:
                continue

            # Skip datasets that didn't get a town column
            if "town" not in df_raw.columns:
                logger.warning(f"  Skipping '{name}' — no 'town' column after standardize")
                continue

            # Filter to most recent available year <= requested year
            if "year" in df_raw.columns:
                df_raw = df_raw.dropna(subset=["year"])
                available = df_raw["year"].unique()
                valid = [y for y in available if y <= year]
                if not valid:
                    logger.warning(f"  Skipping '{name}' — no data for year <= {year} (available: {sorted(available)})")
                    continue
                best_year = max(valid)
                if best_year != year:
                    logger.info(f"  Using vintage {int(best_year)} for '{name}' (requested {year})")
                df_raw = df_raw[df_raw["year"] == best_year].copy()

            # Pivot long → wide
            total_filters = cfg.get("total_filters") or {}
            measure_filter = cfg.get("measure_filter") or None
            variable_col = "Variable" if "Variable" in df_raw.columns else None

            if variable_col:
                df_wide = ct.pivot_to_town_year(
                    df_raw,
                    total_filters=total_filters,
                    measure_filter=measure_filter,
                    variable_col=variable_col,
                )
            else:
                df_wide = df_raw

            if df_wide.empty or "town" not in df_wide.columns:
                logger.warning(f"  Skipping '{name}' — empty after pivot")
                continue

            # Rename pivoted column if canonical_variable set
            canonical = cfg.get("canonical_variable")
            if canonical and canonical in df_wide.columns:
                df_wide = df_wide.rename(columns={canonical: _slugify(canonical)})

            # Keep only town, year, and numeric/useful columns
            keep = ["town", "year"] + [
                c for c in df_wide.columns
                if c not in ["town", "year", "FIPS"]
                and df_wide[c].dtype in ["float64", "int64", "object"]
            ]
            df_wide = df_wide[[c for c in keep if c in df_wide.columns]]

            wide_frames.append(df_wide)
            logger.info(f"  ✓ {name}: {df_wide.shape[0]} towns, {df_wide.shape[1]} cols")

        except Exception as e:
            logger.warning(f"  ✗ '{name}' failed: {e}")

    if not wide_frames:
        logger.error("No CTData datasets loaded. Check ingestion/datasets.yaml.")
        sys.exit(1)

    # Merge all wide frames on (town, year) — left join to keep all towns
    logger.info(f"\n  Merging {len(wide_frames)} datasets ...")
    acs_df = wide_frames[0]
    for df in wide_frames[1:]:
        merge_cols = [c for c in ["town", "year"] if c in df.columns and c in acs_df.columns]
        if not merge_cols:
            continue
        # Drop duplicate columns before merging
        new_cols = [c for c in df.columns if c not in acs_df.columns or c in merge_cols]
        acs_df = acs_df.merge(df[new_cols], on=merge_cols, how="outer")

    acs_df["year"] = year
    logger.info(f"  Merged: {acs_df.shape}")

    # ── 2. Ingest Socrata (business) ─────────────────────────────────────────
    logger.info("\n  Ingesting business data from data.ct.gov ...")
    biz_combined = pd.DataFrame()
    try:
        with SocrataClient() as sc:
            biz_df     = sc.fetch_business_master(start_year=year - 1)
            filing_df  = sc.fetch_filing_history(start_year=year - 1)
        biz_combined = pd.concat([biz_df, filing_df], ignore_index=True)
        logger.info(f"  Business data: {biz_combined.shape}")
    except Exception as e:
        logger.warning(f"  Business data failed ({e}) — continuing without it")

    # ── 3. LODES commute flows ────────────────────────────────────────────────
    logger.info("\n  Ingesting LODES anchor flows (LODES 2021) ...")
    lodes_df = pd.DataFrame()
    try:
        lodes_df = LODESClient().fetch_anchor_flows(year=2021)
        logger.info(f"  LODES flows: {lodes_df.shape}")
    except Exception as e:
        logger.warning(f"  LODES ingestion failed ({e}) — continuing without commute flows")

    # ── 4. Feature engineering ───────────────────────────────────────────────
    logger.info("\n[3/5] Building feature matrix ...")
    features_df = FeatureBuilder().build(
        acs_df,
        biz_combined if not biz_combined.empty else None,
        lodes_df=lodes_df if not lodes_df.empty else None,
        year=year,
    )
    logger.info(f"  Features: {features_df.shape}")

    # Append to all-years file
    all_years_path = PROCESSED_DIR / "town_features_all_years.parquet"
    if all_years_path.exists():
        existing = pd.read_parquet(all_years_path)
        existing  = existing[existing["year"] != year]
        features_df = pd.concat([existing, features_df], ignore_index=True)
    features_df.to_parquet(all_years_path, index=False)

    # ── 4. Clustering ────────────────────────────────────────────────────────
    logger.info(f"\n[4/5] Clustering towns (k={n_clusters}) ...")
    year_features = features_df[features_df["year"] == year].copy()
    clusters_df   = TownClusterer(n_clusters=n_clusters).fit_predict(year_features)
    centroids_df  = pd.read_parquet(PROCESSED_DIR / "cluster_centroids.parquet")
    logger.info(f"  Archetypes: {clusters_df['cluster_id'].nunique()}")

    # ── 5. Personas ──────────────────────────────────────────────────────────
    logger.info("\n[5/5] Building persona cards ...")
    PersonaBuilder().build_all_towns(year_features, clusters_df, centroids_df, year=year)

    logger.info(f"\n✓ Pipeline complete. Output -> {PROCESSED_DIR}")
    logger.info(f"  Files: {[f.name for f in PROCESSED_DIR.iterdir()]}")


def _slugify(s: str) -> str:
    return s.lower().strip().replace(" ", "_").replace("/", "_").replace("-", "_")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--year",       type=int, default=2022)
    p.add_argument("--n-clusters", type=int, default=5)
    args = p.parse_args()
    run(year=args.year, n_clusters=args.n_clusters)
