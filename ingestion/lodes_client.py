"""
ingestion/lodes_client.py
LEHD / LODES origin-destination ingestion for ct-town-personas.

Downloads CT LODES8 files from the Census LEHD server:
  - ct_xwalk.csv.gz              block → town name crosswalk
  - ct_od_main_JT00_YYYY.csv.gz  origin-destination job flows (all jobs)

Produces inbound commute flow counts from every CT town into each of the
four major CT economic anchors: Hartford, New Haven, Stamford, Bridgeport.

The resulting wide table (town × inbound_to_<city>) feeds two uses:
  1. Accessibility scoring — commute flow as a directional-travel proxy
  2. Post #5 (Commuter arbitrage) — latent leisure demand analysis

Serves: Post #5 — Commuter Arbitrage
"""

from __future__ import annotations

import gzip
import io
import logging
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

log = logging.getLogger(__name__)

RAW_DIR = Path(__file__).parents[1] / "data" / "raw"
PROCESSED_DIR = Path(__file__).parents[1] / "data" / "processed"
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

LEHD_BASE = "https://lehd.ces.census.gov/data/lodes/LODES8"
TIMEOUT = 120  # full OD file is ~20 MB compressed

# The four anchor cities whose inbound flows we compute.
# These are the primary CT economic hubs referenced in the data spine.
ANCHOR_CITIES = ["Hartford", "New Haven", "Stamford", "Bridgeport"]


class LODESClient:
    """Fetch LODES OD flow data and aggregate to CT town pairs."""

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "ct-town-personas/0.1"})
        self._xwalk_cache: Optional[pd.DataFrame] = None

    # ── Public interface ──────────────────────────────────────────────────────

    def fetch_xwalk(self, state: str = "ct") -> pd.DataFrame:
        """
        Download and parse the LODES geographic crosswalk for a state.

        Returns DataFrame with columns: tabblk2020, town, blklatdd, blklondd
        where `town` is parsed from ctycsubname ("Hartford town (...)" → "Hartford").
        Cached to data/raw/ after first download.
        """
        cached_path = RAW_DIR / f"lehd_xwalk_{state}.parquet"
        if cached_path.exists():
            log.info("Loading xwalk from cache: %s", cached_path)
            self._xwalk_cache = pd.read_parquet(cached_path)
            return self._xwalk_cache

        url = f"{LEHD_BASE}/{state}/{state}_xwalk.csv.gz"
        log.info("Downloading LODES xwalk from %s ...", url)
        df = self._download_gz_csv(url)

        # Parse town name: "Hartford town (Capital Region, CT)" → "Hartford"
        df["town"] = (
            df["ctycsubname"]
            .str.split(" town").str[0]
            .str.split(" city").str[0]
            .str.split(" borough").str[0]
            .str.strip()
            .str.title()
        )

        keep = ["tabblk2020", "town", "blklatdd", "blklondd"]
        df = df[keep].copy()
        df["tabblk2020"] = df["tabblk2020"].astype(str).str.zfill(15)
        df.to_parquet(cached_path, index=False)

        log.info(
            "  -> %d blocks, %d unique towns | saved to %s",
            len(df), df["town"].nunique(), cached_path,
        )
        self._xwalk_cache = df
        return df

    def fetch_od(self, state: str = "ct", year: int = 2021, job_type: str = "JT00") -> pd.DataFrame:
        """
        Download the LODES OD main file for a state and year.

        Returns DataFrame with columns: w_geocode, h_geocode, S000 (all jobs).
        Cached to data/raw/ after first download — the file is ~20 MB compressed.
        """
        cached_path = RAW_DIR / f"lehd_od_{state}_{year}.parquet"
        if cached_path.exists():
            log.info("Loading OD from cache: %s", cached_path)
            return pd.read_parquet(cached_path)

        url = f"{LEHD_BASE}/{state}/od/{state}_od_main_{job_type}_{year}.csv.gz"
        log.info("Downloading LODES OD file from %s ...", url)
        df = self._download_gz_csv(url)

        df["w_geocode"] = df["w_geocode"].astype(str).str.zfill(15)
        df["h_geocode"] = df["h_geocode"].astype(str).str.zfill(15)
        df["S000"] = pd.to_numeric(df["S000"], errors="coerce").fillna(0).astype(int)

        df = df[["w_geocode", "h_geocode", "S000"]].copy()
        df.to_parquet(cached_path, index=False)
        log.info("  -> %d OD pairs | saved to %s", len(df), cached_path)
        return df

    def inbound_flows_to_town(
        self,
        od_df: pd.DataFrame,
        xwalk_df: pd.DataFrame,
        target_town: str,
    ) -> pd.DataFrame:
        """
        Return inbound worker counts from every CT origin town into target_town.

        Returns DataFrame with columns: town (origin), inbound_workers,
        sorted descending by inbound_workers.
        """
        target_blocks = set(
            xwalk_df.loc[xwalk_df["town"] == target_town, "tabblk2020"]
        )
        if not target_blocks:
            log.warning("No blocks found for target town '%s' in xwalk", target_town)
            return pd.DataFrame(columns=["town", "inbound_workers"])

        log.info("Target '%s': %d work blocks found", target_town, len(target_blocks))

        od_to_target = od_df[od_df["w_geocode"].isin(target_blocks)].copy()
        log.info("  -> %d OD pairs with work in %s", len(od_to_target), target_town)

        blk_to_town = xwalk_df.set_index("tabblk2020")["town"]
        od_to_target["home_town"] = od_to_target["h_geocode"].map(blk_to_town)

        result = (
            od_to_target
            .groupby("home_town", dropna=True)["S000"]
            .sum()
            .reset_index()
            .rename(columns={"home_town": "town", "S000": "inbound_workers"})
            .sort_values("inbound_workers", ascending=False)
            .reset_index(drop=True)
        )

        if len(result):
            log.info(
                "  -> %d origin towns | top: %s (%d workers)",
                len(result), result.iloc[0]["town"], result.iloc[0]["inbound_workers"],
            )
        return result

    def fetch_anchor_flows(self, year: int = 2021) -> pd.DataFrame:
        """
        Compute inbound commute flows from every CT town into each anchor city.

        Returns a wide DataFrame indexed by town with columns:
          inbound_to_hartford, inbound_to_new_haven,
          inbound_to_stamford, inbound_to_bridgeport

        Saved to data/processed/lodes_anchor_flows_{year}.parquet.
        This is the primary output consumed by the pipeline and Post #5 analysis.
        """
        out_path = PROCESSED_DIR / f"lodes_anchor_flows_{year}.parquet"
        if out_path.exists():
            log.info("Loading anchor flows from cache: %s", out_path)
            return pd.read_parquet(out_path)

        xwalk = self.fetch_xwalk()
        od = self.fetch_od(year=year)

        all_towns = sorted(xwalk["town"].dropna().unique())
        wide = pd.DataFrame({"town": all_towns})

        for city in ANCHOR_CITIES:
            col = f"inbound_to_{city.lower().replace(' ', '_')}"
            flows = self.inbound_flows_to_town(od, xwalk, city)
            flows = flows.rename(columns={"inbound_workers": col})
            wide = wide.merge(flows[["town", col]], on="town", how="left")
            wide[col] = wide[col].fillna(0).astype(int)

        wide["lodes_year"] = year
        wide.to_parquet(out_path, index=False)
        log.info(
            "Saved anchor flows -> %s (%d towns × %d anchor cities)",
            out_path, len(wide), len(ANCHOR_CITIES),
        )
        return wide

    # ── Internal ──────────────────────────────────────────────────────────────

    def _download_gz_csv(self, url: str) -> pd.DataFrame:
        resp = self.session.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        buf = io.BytesIO(resp.content)
        return pd.read_csv(gzip.open(buf))
