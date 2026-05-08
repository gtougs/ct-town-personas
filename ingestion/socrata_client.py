from dotenv import load_dotenv
load_dotenv()

"""
socrata_client.py
Thin wrapper around sodapy for pulling CT open data.
Reads dataset config from datasets.yaml.
"""

import os
import logging
import yaml
import pandas as pd
from sodapy import Socrata
from pathlib import Path
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

DATASETS_PATH = Path(__file__).parent / "datasets.yaml"
RAW_DIR = Path(__file__).parent.parent / "data" / "raw"


def _load_registry() -> dict:
    with open(DATASETS_PATH) as f:
        return yaml.safe_load(f)


class SocrataClient:
    """
    Pulls datasets from data.ct.gov via the SODA API.
    App token is optional but avoids throttling — set SOCRATA_APP_TOKEN env var.
    """

    def __init__(self):
        registry = _load_registry()
        self.meta = registry["meta"]
        self.datasets = {d["name"]: d for d in registry["datasets"] if d["source"] == "socrata"}
        self.client = Socrata(
            self.meta["socrata_domain"],
            app_token=os.getenv("SOCRATA_APP_TOKEN"),  # None = unauthenticated (throttled)
            timeout=15,
        )

    def fetch(
        self,
        dataset_name: str,
        limit: int = 100_000,
        where: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Pull a registered dataset by name. Returns a cleaned DataFrame
        with canonical column names as defined in datasets.yaml.
        """
        if dataset_name not in self.datasets:
            raise KeyError(f"Dataset '{dataset_name}' not found in registry. "
                           f"Available: {list(self.datasets.keys())}")

        cfg = self.datasets[dataset_name]
        dataset_id = cfg["id"]

        logger.info(f"Fetching '{dataset_name}' ({dataset_id}) from data.ct.gov ...")

        results = self.client.get(
            dataset_id,
            limit=limit,
            where=where,
        )

        df = pd.DataFrame.from_records(results)

        if df.empty:
            logger.warning(f"No records returned for '{dataset_name}'")
            return df

        # Rename to canonical names if field map defined
        if "fields" in cfg:
            rename_map = {k: v for k, v in cfg["fields"].items() if k in df.columns}
            df = df.rename(columns=rename_map)
            df = df[[v for v in cfg["fields"].values() if v in df.columns]]

        df = self._coerce_types(df, cfg)
        logger.info(f"  → {len(df):,} rows, {list(df.columns)}")
        return df

    def fetch_business_master(self, start_year: int = 2015) -> pd.DataFrame:
        """
        CT SOTS Business Master (n7gp-d28j) — all registered businesses.
        Filters by Date_Registration. Parses year/month for time-series use.
        """
        where = f"Date_Registration >= '{start_year}-01-01T00:00:00.000'"
        df = self.fetch("business_master", limit=500_000, where=where)
        if "filing_date" in df.columns:
            df["filing_date"] = pd.to_datetime(df["filing_date"], errors="coerce")
            df["year"]  = df["filing_date"].dt.year
            df["month"] = df["filing_date"].dt.month
        return df

    def fetch_filing_history(self, start_year: int = 2015) -> pd.DataFrame:
        """
        CT SOTS Business Filing History (ah3s-bes7) — formation & dissolution events.
        Filters by TransactionDate. Parses year/month for time-series use.
        """
        where = f"filing_date >= '{start_year}-01-01T00:00:00.000'"
        df = self.fetch("business_filing_history", limit=500_000, where=where)
        if "filing_date" in df.columns:
            df["filing_date"] = pd.to_datetime(df["filing_date"], errors="coerce")
            df["year"]  = df["filing_date"].dt.year
            df["month"] = df["filing_date"].dt.month
        return df

    def save_raw(self, df: pd.DataFrame, dataset_name: str) -> Path:
        """Save raw pull to Parquet for reproducibility."""
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d")
        path = RAW_DIR / f"{dataset_name}_{ts}.parquet"
        df.to_parquet(path, index=False)
        logger.info(f"  Saved raw → {path}")
        return path

    def _coerce_types(self, df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
        """Best-effort numeric coercion for common Socrata string fields."""
        numeric_hints = {"population", "income", "value", "rent", "rate", "units", "count"}
        for col in df.columns:
            if any(hint in col.lower() for hint in numeric_hints):
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# ── Quick sanity check ────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    with SocrataClient() as client:
        df = client.fetch("population_by_town", limit=50)
        print(df.head())

    def fetch_business_master(self, start_year: int = 2021) -> pd.DataFrame:
        """
        Pulls CT SOTS Business Master — all registered businesses.
        Filters by registration date >= start_year.
        """
        where = f"Date_Registration >= '{start_year}-01-01T00:00:00'"
        df = self.fetch("business_master", where=where)
        if "filing_date" in df.columns:
            df["filing_date"] = pd.to_datetime(df["filing_date"], errors="coerce")
            df["year"]  = df["filing_date"].dt.year
            df["month"] = df["filing_date"].dt.month
        return df

    def fetch_filing_history(self, start_year: int = 2021) -> pd.DataFrame:
        """
        Pulls CT SOTS Business Filing History — transaction-level events
        (formations, amendments, dissolutions).
        """
        where = f"TransactionDate >= '{start_year}-01-01T00:00:00'"
        df = self.fetch("business_filing_history", where=where)
        if "filing_date" in df.columns:
            df["filing_date"] = pd.to_datetime(df["filing_date"], errors="coerce")
            df["year"]  = df["filing_date"].dt.year
            df["month"] = df["filing_date"].dt.month
        return df
