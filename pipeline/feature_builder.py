"""
feature_builder.py
Assembles the town x year feature matrix from CTData columns.
Fully defensive — no hardcoded column assumptions.
"""
import logging
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)
PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"


class FeatureBuilder:

    def build(
        self,
        acs_df: pd.DataFrame,
        biz_df: Optional[pd.DataFrame] = None,
        lodes_df: Optional[pd.DataFrame] = None,
        gtfs_df: Optional[pd.DataFrame] = None,
        year: Optional[int] = None,
    ) -> pd.DataFrame:
        logger.info("Building feature matrix ...")
        df = acs_df.copy()

        # Normalize column names
        df.columns = [
            c.strip().lower()
             .replace(" ", "_")
             .replace("/", "_")
             .replace("-", "_")
            for c in df.columns
        ]

        logger.info(f"  Columns: {list(df.columns)}")

        # Coerce everything except identifiers to numeric
        for col in df.columns:
            if col in ["town", "fips", "year"]:
                continue
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df["year"] = year or df.get("year", pd.Series([2022] * len(df)))

        # Join LODES anchor flow columns (inbound_to_hartford, etc.)
        if lodes_df is not None and not lodes_df.empty and "town" in lodes_df.columns:
            flow_cols = [c for c in lodes_df.columns if c.startswith("inbound_to_")]
            df = df.merge(lodes_df[["town"] + flow_cols], on="town", how="left")
            df[flow_cols] = df[flow_cols].fillna(0)
            logger.info(f"  Joined LODES flows: {flow_cols}")

        # Join GTFS transit metrics (stop_count, has_transit)
        if gtfs_df is not None and not gtfs_df.empty and "town" in gtfs_df.columns:
            transit_cols = [c for c in gtfs_df.columns if c in ("stop_count", "has_transit", "agency_count")]
            df = df.merge(gtfs_df[["town"] + transit_cols], on="town", how="left")
            df["stop_count"] = df["stop_count"].fillna(0).astype(int)
            df["has_transit"] = df["has_transit"].fillna(False).astype(bool)
            logger.info(f"  Joined GTFS transit: {transit_cols}")

        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        out = PROCESSED_DIR / f"town_features_{year or 'all'}.parquet"
        df.to_parquet(out, index=False)

        # Also write the all-years file
        all_years = PROCESSED_DIR / "town_features_all_years.parquet"
        if all_years.exists():
            existing = pd.read_parquet(all_years)
            existing = existing[existing["year"] != year]
            df = pd.concat([existing, df], ignore_index=True)
        df.to_parquet(all_years, index=False)

        logger.info(f"  Saved → {out} ({acs_df.shape[0]} rows × {df.shape[1]} cols)")
        return df
