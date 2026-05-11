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
