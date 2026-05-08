"""
ctdata_client.py

Pulls CTData datasets as CSV files via CKAN's resource_show endpoint.

The DataStore query API on data.ctdata.org is broken (PostgreSQL window
function error). Instead we:
  1. Call resource_show to get the direct CSV download URL
  2. Download with pd.read_csv()

This is simpler and more reliable.
"""

import logging
import time
import requests
import pandas as pd
import yaml
from io import StringIO
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

BASE_URL         = "http://data.ctdata.org"
RESOURCE_SHOW    = f"{BASE_URL}/api/3/action/resource_show"
PACKAGE_SHOW     = f"{BASE_URL}/api/3/action/package_show"
PACKAGE_LIST     = f"{BASE_URL}/api/3/action/package_list"

DATASETS_PATH = Path(__file__).parent / "datasets.yaml"
RAW_DIR       = Path(__file__).parent.parent / "data" / "raw"


def _load_registry() -> dict:
    with open(DATASETS_PATH) as f:
        return yaml.safe_load(f)


class CTDataClient:
    """
    Downloads CTData CSV files via CKAN resource_show + direct URL.
    """

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        registry = _load_registry()
        self.datasets = {
            d["name"]: d
            for d in registry.get("datasets", [])
            if d.get("source") == "ctdata_ckan"
        }
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "ct-town-personas/0.1"})
        self._url_cache: dict = {}

    # ── Core fetch ────────────────────────────────────────────────────────────

    def fetch(self, dataset_name: str) -> pd.DataFrame:
        """
        Fetch a registered CTData dataset by name.
        Returns a standardized DataFrame.
        """
        if dataset_name not in self.datasets:
            raise KeyError(
                f"Dataset '{dataset_name}' not in registry. "
                f"Available: {sorted(self.datasets.keys())}"
            )

        cfg = self.datasets[dataset_name]
        resource_id = cfg["resource_id"]

        logger.info(f"Fetching '{dataset_name}' ({resource_id}) ...")

        url = self._get_download_url(resource_id)
        if not url:
            raise RuntimeError(f"Could not resolve download URL for '{dataset_name}'")

        df = self._download_csv(url)
        if df.empty:
            logger.warning(f"  Empty DataFrame for '{dataset_name}'")
            return df

        df = self._standardize(df, cfg)
        logger.info(f"  -> {len(df):,} rows | cols: {list(df.columns)}")
        return df

    def fetch_by_resource_id(self, resource_id: str) -> pd.DataFrame:
        """Direct fetch by resource ID — for exploration."""
        url = self._get_download_url(resource_id)
        if not url:
            raise RuntimeError(f"Could not resolve URL for resource {resource_id}")
        return self._download_csv(url)

    # ── Pivoting ──────────────────────────────────────────────────────────────

    def pivot_to_town_year(
        self,
        df: pd.DataFrame,
        value_col: str = "Value",
        variable_col: str = "Variable",
        measure_filter: Optional[str] = None,
        total_filters: Optional[dict] = None,
    ) -> pd.DataFrame:
        """
        Pivots CTData long-format data to wide format:
        one row per (town, year), one column per variable value.
        """
        df = df.copy()

        # Apply total_filters to select aggregate rows only
        if total_filters:
            for col, val in total_filters.items():
                if col in df.columns:
                    df = df[df[col].astype(str).str.strip() == str(val)]
                    if df.empty:
                        logger.warning(
                            f"  Filter {col}={val!r} returned 0 rows. "
                            f"Actual values: {df[col].unique().tolist() if col in df.columns else 'col missing'}"
                        )

        # Filter to specific measure type
        if measure_filter and "Measure Type" in df.columns:
            df = df[df["Measure Type"].astype(str).str.strip() == measure_filter]

        df[value_col] = pd.to_numeric(df[value_col], errors="coerce")

        town_col = "town" if "town" in df.columns else "Town"
        year_col = "year" if "year" in df.columns else "Year"

        if variable_col not in df.columns:
            logger.warning(f"  Column '{variable_col}' not found. Returning flat df.")
            return df

        if town_col not in df.columns or year_col not in df.columns:
            logger.warning(f"  Missing town/year columns. Returning flat df.")
            return df

        try:
            pivot = df.pivot_table(
                index=[town_col, year_col],
                columns=variable_col,
                values=value_col,
                aggfunc="first",
            ).reset_index()
            pivot.columns.name = None
            return pivot
        except Exception as e:
            logger.warning(f"  Pivot failed ({e}), returning flat df")
            return df

    # ── Schema inspection ─────────────────────────────────────────────────────

    def peek(self, resource_id: str, n: int = 5) -> pd.DataFrame:
        """Preview first n rows of any resource."""
        df = self.fetch_by_resource_id(resource_id)
        return df.head(n)

    def schema(self, resource_id: str) -> dict:
        """
        Returns column names and unique values for categorical columns.
        Use this to determine correct total_filters values.
        """
        df = self.fetch_by_resource_id(resource_id)
        result = {"columns": list(df.columns), "sample_values": {}}
        for col in ["Gender", "Race/Ethnicity", "Measure Type", "Variable", "Year"]:
            if col in df.columns:
                result["sample_values"][col] = sorted(df[col].dropna().unique().tolist())
        return result

    def save_raw(self, df: pd.DataFrame, name: str) -> Path:
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        path = RAW_DIR / f"{name}.parquet"
        df.to_parquet(path, index=False)
        logger.info(f"  Saved -> {path}")
        return path

    # ── Internal ──────────────────────────────────────────────────────────────

    def _get_download_url(self, resource_id: str) -> Optional[str]:
        """
        Calls resource_show to get the direct CSV download URL.
        Caches results to avoid repeat API calls.
        """
        if resource_id in self._url_cache:
            return self._url_cache[resource_id]

        try:
            resp = self.session.get(
                RESOURCE_SHOW,
                params={"id": resource_id},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success"):
                logger.error(f"  resource_show failed: {data.get('error')}")
                return None
            url = data["result"].get("url")
            self._url_cache[resource_id] = url
            return url
        except Exception as e:
            logger.error(f"  resource_show error: {e}")
            return None

    def _download_csv(self, url: str) -> pd.DataFrame:
        """Downloads a CSV from a direct URL and returns a DataFrame."""
        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            return pd.read_csv(StringIO(resp.text), engine='python', on_bad_lines='skip')
        except Exception as e:
            logger.error(f"  CSV download failed ({url}): {e}")
            return pd.DataFrame()

    def _standardize(self, df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
        """Normalize column names and types."""
        df.columns = [c.strip() for c in df.columns]

        if "field_renames" in cfg:
            df = df.rename(columns=cfg["field_renames"])

        # Normalize Town and Year to lowercase keys
        # Handle both "Town" and "Town/County" column names
        if "Town" in df.columns:
            df["Town"] = df["Town"].str.strip().str.title()
            df = df.rename(columns={"Town": "town"})
        elif "Town/County" in df.columns:
            df["Town/County"] = df["Town/County"].str.strip().str.title()
            df = df.rename(columns={"Town/County": "town"})
        if "Year" in df.columns:
            # Handle ACS vintage ranges like "2017-2021" → use end year (2021)
            yr = df["Year"].astype(str).str.strip()
            if yr.str.contains("-").any():
                df["year"] = pd.to_numeric(yr.str.split("-").str[-1], errors="coerce")
            else:
                df["year"] = pd.to_numeric(yr, errors="coerce")
            df = df.drop(columns=["Year"])

        return df
