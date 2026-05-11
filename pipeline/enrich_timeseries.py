"""
pipeline/enrich_timeseries.py

Builds genuine time-series data from:
  1. Zillow Home Value Index (monthly, through ~2024) — from CTData
  2. CT SOTS Business Formations (monthly, current) — from Socrata
  3. Merges with existing ACS snapshots to create a richer feature history

Run: python -m pipeline.enrich_timeseries
"""

import logging
import pandas as pd
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)
PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"

# Resource IDs
ZILLOW_RESOURCE_ID = "1e3233e0-e442-4401-bf5d-3835a591fd3e"


def run():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )

    logger.info("=" * 60)
    logger.info("CT Town Personas — Time Series Enrichment")
    logger.info("=" * 60)

    from ingestion.ctdata_client import CTDataClient
    from ingestion.socrata_client import SocrataClient

    ct = CTDataClient()

    # ── 1. Zillow Home Value Index ────────────────────────────────────────────
    logger.info("\n[1/3] Pulling Zillow Home Value Index ...")
    zillow_ts = _pull_zillow(ct)
    if zillow_ts is not None:
        path = PROCESSED_DIR / "zillow_timeseries.parquet"
        zillow_ts.to_parquet(path, index=False)
        logger.info(f"  Saved Zillow time series → {path}")
        logger.info(f"  Shape: {zillow_ts.shape}")
        logger.info(f"  Years: {sorted(zillow_ts['year'].unique())}")
        logger.info(f"  Sample:\n{zillow_ts[zillow_ts['town'] == 'Greenwich'].head(5)}")

    # ── 2. Business formations time series ───────────────────────────────────
    logger.info("\n[2/3] Pulling business formation time series ...")
    biz_ts = _pull_business_timeseries()
    if biz_ts is not None:
        path = PROCESSED_DIR / "business_timeseries.parquet"
        biz_ts.to_parquet(path, index=False)
        logger.info(f"  Saved business time series → {path}")
        logger.info(f"  Shape: {biz_ts.shape}")

    # ── 3. Merge into enriched all-years features ────────────────────────────
    logger.info("\n[3/3] Merging enriched data into feature store ...")
    _merge_enriched(zillow_ts, biz_ts)

    logger.info("\n✓ Enrichment complete.")


def _pull_zillow(ct) -> pd.DataFrame:
    """
    Pull Zillow Home Value Index from CTData.
    Expected schema: Town | Date | Value (monthly home value index)
    Returns annual medians by town.
    """
    try:
        df = ct.fetch_by_resource_id(ZILLOW_RESOURCE_ID)
        logger.info(f"  Raw Zillow: {df.shape} | cols: {list(df.columns)}")

        if df.empty:
            logger.warning("  Zillow returned empty DataFrame")
            return None

        # Normalize town column
        town_col = next((c for c in df.columns if "town" in c.lower()), None)
        if not town_col:
            logger.warning(f"  No town column found. Columns: {list(df.columns)}")
            return None

        df = df.rename(columns={town_col: "town"})
        df["town"] = df["town"].str.strip().str.title()

        # Find date/year column
        date_col = next((c for c in df.columns if any(
            x in c.lower() for x in ["date", "month", "year", "period"]
        ) and c != "town"), None)

        if date_col:
            df["date"] = pd.to_datetime(df[date_col], errors="coerce")
            df["year"] = df["date"].dt.year
        else:
            # Try to find numeric year
            for col in df.columns:
                if col != "town":
                    sample = df[col].dropna().iloc[0] if len(df) > 0 else ""
                    if str(sample).startswith(("20", "19")):
                        df["year"] = pd.to_numeric(df[col], errors="coerce")
                        break

        # Find value column
        val_col = next((c for c in df.columns if any(
            x in c.lower() for x in ["value", "index", "price", "zhvi"]
        ) and c not in ["town", "year", "date"]), None)

        if not val_col:
            # Use last numeric column
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            val_col = numeric_cols[-1] if numeric_cols else None

        if not val_col:
            logger.warning("  Could not identify value column in Zillow data")
            return None

        df["zillow_home_value"] = pd.to_numeric(df[val_col], errors="coerce")

        # Aggregate to annual median
        annual = (
            df.groupby(["town", "year"])["zillow_home_value"]
            .median()
            .reset_index()
        )
        annual = annual.dropna(subset=["zillow_home_value"])
        return annual

    except Exception as e:
        logger.error(f"  Zillow pull failed: {e}")
        return None


def _pull_business_timeseries() -> pd.DataFrame:
    """
    Pull CT SOTS business master and aggregate to annual formations per town.
    """
    try:
        from ingestion.socrata_client import SocrataClient
        with SocrataClient() as sc:
            df = sc.fetch_business_master(start_year=2015)

        if df.empty:
            return None

        if "filing_date" in df.columns:
            df["filing_date"] = pd.to_datetime(df["filing_date"], errors="coerce")
            df["year"] = df["filing_date"].dt.year

        if "year" not in df.columns or "town" not in df.columns:
            return None

        # Count formations per town per year
        annual = (
            df.dropna(subset=["year", "town"])
            .groupby(["town", "year"])
            .size()
            .reset_index(name="annual_business_formations")
        )
        annual["year"] = annual["year"].astype(int)
        annual = annual[annual["year"] >= 2015]
        return annual

    except Exception as e:
        logger.error(f"  Business time series pull failed: {e}")
        return None


def _merge_enriched(zillow_ts: pd.DataFrame, biz_ts: pd.DataFrame):
    """
    Merges Zillow and business time series into the existing feature store.
    Creates a new enriched_timeseries.parquet for use by the forecast router.
    """
    frames = []

    if zillow_ts is not None and not zillow_ts.empty:
        frames.append(zillow_ts.rename(columns={"zillow_home_value": "value"})
                      .assign(indicator="zillow_home_value"))

    if biz_ts is not None and not biz_ts.empty:
        frames.append(biz_ts.rename(columns={"annual_business_formations": "value"})
                      .assign(indicator="annual_business_formations"))

    if not frames:
        logger.warning("  No enriched data to merge")
        return

    enriched = pd.concat(frames, ignore_index=True)
    enriched = enriched[["town", "year", "indicator", "value"]].dropna()

    path = PROCESSED_DIR / "enriched_timeseries.parquet"
    enriched.to_parquet(path, index=False)
    logger.info(f"  Enriched time series saved → {path}")
    logger.info(f"  Indicators: {enriched['indicator'].unique().tolist()}")
    logger.info(f"  Years: {sorted(enriched['year'].unique())}")
    logger.info(f"  Towns: {enriched['town'].nunique()}")


if __name__ == "__main__":
    run()
