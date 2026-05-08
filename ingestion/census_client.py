"""
census_client.py
Pulls ACS 5-year estimates for all 169 CT towns (county subdivisions).
Reads variable definitions from datasets.yaml.
"""

import os
import logging
import yaml
import requests
import pandas as pd
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DATASETS_PATH = Path(__file__).parent / "datasets.yaml"
RAW_DIR = Path(__file__).parent.parent / "data" / "raw"


def _load_registry() -> dict:
    with open(DATASETS_PATH) as f:
        return yaml.safe_load(f)


class CensusACSClient:
    """
    Pulls ACS 5-year estimates from the Census Bureau API.
    All ACS datasets in datasets.yaml are fetched and merged into
    a single town × year × feature DataFrame.

    Census API key is optional but recommended for rate limits.
    Set CENSUS_API_KEY env var.
    """

    BASE_URL = "https://api.census.gov/data"

    def __init__(self):
        registry = _load_registry()
        self.meta = registry["meta"]
        self.acs_datasets = [
            d for d in registry["datasets"]
            if d["source"] == "census_acs" and "acs_variables" in d
        ]
        self.api_key = os.getenv("CENSUS_API_KEY")  # optional

    def fetch_all(self, vintage: Optional[int] = None) -> pd.DataFrame:
        """
        Fetches all ACS datasets defined in registry for a given vintage year
        and merges them into one wide DataFrame keyed by (town, year).
        """
        vintage = vintage or self.meta["default_acs_vintage"]
        frames = []

        for dataset in self.acs_datasets:
            try:
                df = self._fetch_dataset(dataset, vintage)
                frames.append(df)
                logger.info(f"  ✓ {dataset['name']} ({len(df)} towns)")
            except Exception as e:
                logger.warning(f"  ✗ {dataset['name']} failed: {e}")

        if not frames:
            raise RuntimeError("All ACS fetches failed.")

        # Merge all on town key
        merged = frames[0]
        for df in frames[1:]:
            merged = merged.merge(df, on=["town", "year"], how="outer")

        merged = self._clean_town_names(merged)
        logger.info(f"ACS merge complete: {merged.shape[0]} towns × {merged.shape[1]} columns")
        return merged

    def fetch_vintage_range(self, start: int = 2015, end: int = 2022) -> pd.DataFrame:
        """
        Fetches multiple ACS vintages and stacks them for time-series use.
        Each ACS 5-year vintage is labeled by its end year.
        """
        frames = []
        for year in range(start, end + 1):
            try:
                df = self.fetch_all(vintage=year)
                frames.append(df)
                logger.info(f"  Vintage {year} → {len(df)} towns")
            except Exception as e:
                logger.warning(f"  Vintage {year} failed: {e}")

        if not frames:
            raise RuntimeError("No ACS vintages could be fetched.")

        return pd.concat(frames, ignore_index=True)

    def _fetch_dataset(self, dataset: dict, vintage: int) -> pd.DataFrame:
        """Fetch one ACS dataset for all CT towns."""
        variables = list(dataset["acs_variables"].keys())
        rename_map = dataset["acs_variables"]

        # Census API caps at 50 variables per call
        chunks = [variables[i:i+45] for i in range(0, len(variables), 45)]
        frames = []

        for chunk in chunks:
            get_vars = "NAME," + ",".join(chunk)
            params = {
                "get": get_vars,
                "for": self.meta["acs_geo"],
                "in": f"state:{self.meta['acs_state']}",
            }
            if self.api_key:
                params["key"] = self.api_key

            url = f"{self.BASE_URL}/{vintage}/acs/acs5"
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()

            data = resp.json()
            headers = data[0]
            rows = data[1:]
            df = pd.DataFrame(rows, columns=headers)
            frames.append(df)

        if not frames:
            return pd.DataFrame()

        # Merge chunks on NAME
        result = frames[0]
        for df in frames[1:]:
            drop_cols = [c for c in ["state", "county", "county subdivision"] if c in df.columns]
            result = result.merge(df.drop(columns=drop_cols, errors="ignore"), on="NAME", how="outer")

        # Rename ACS codes to readable names
        result = result.rename(columns=rename_map)

        # Coerce numerics
        for col in rename_map.values():
            if col in result.columns:
                result[col] = pd.to_numeric(result[col], errors="coerce")

        result["year"] = vintage
        result = result.rename(columns={"NAME": "town_raw"})

        return result

    def _clean_town_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalizes town names from Census format:
        'Andover town, Tolland County, Connecticut' → 'Andover'
        """
        if "town_raw" in df.columns:
            df["town"] = df["town_raw"].str.extract(r"^(.+?)\s+(?:town|city|borough)", expand=False)
            df["town"] = df["town"].str.strip().str.title()
            df = df.drop(columns=["town_raw"], errors="ignore")
        return df

    def save_raw(self, df: pd.DataFrame, name: str = "acs_all") -> Path:
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        path = RAW_DIR / f"{name}_{self.meta['default_acs_vintage']}.parquet"
        df.to_parquet(path, index=False)
        logger.info(f"Saved raw ACS → {path}")
        return path


# ── Quick sanity check ────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    client = CensusACSClient()
    df = client.fetch_all(vintage=2022)
    print(df.head())
    print(df.dtypes)
