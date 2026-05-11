"""
ingestion/gtfs_client.py
GTFS static feed ingestion for Connecticut transit agencies.

Downloads and parses GTFS zips (stops, routes, trips, stop_times) for:
  - CTtransit   — Hartford, New Haven, Stamford/New Canaan, Southeastern CT
  - CTfastrak   — BRT corridor, included in CTtransit feed
  - CTrail Hartford Line  — commuter rail, Hartford ↔ Springfield / New Haven
  - CTrail Shore Line East — commuter rail, New Haven ↔ New London

Primary outputs:
  data/raw/gtfs_stops_{agency}.parquet      raw stops with lat/lon per agency
  data/processed/gtfs_town_transit.parquet  per-town stop count + has_transit flag

The town assignment uses nearest-centroid matching (haversine), which is fast
enough at CT scale (~2 000 stops × 169 towns) and requires no spatial index.

Feed URLs are class-level constants — update here if publishers move files.
CTrail feeds are listed separately because they are published independently
of CTtransit and may have different availability.

Serves: transit accessibility layer in anchor scoring, Post #5
"""

from __future__ import annotations

import io
import logging
import math
import zipfile
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

log = logging.getLogger(__name__)

RAW_DIR = Path(__file__).parents[1] / "data" / "raw"
PROCESSED_DIR = Path(__file__).parents[1] / "data" / "processed"
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

TIMEOUT = 60


class GTFSClient:
    """Download and parse CT GTFS static feeds."""

    # Feed URLs — update here if publishers move files.
    # CTtransit feed covers all divisions including CTfastrak BRT.
    # CTrail feeds are published separately by CT DOT.
    FEED_URLS: dict[str, str] = {
        "cttransit": (
            "https://www.cttransit.com/sites/default/files/gtfs/googlect_transit.zip"
        ),
        "ctail_hartford": (
            "https://www.hartfordline.com/files/PDF/Hartford-Line-GTFS.zip"
        ),
        "ctail_shoreline": (
            "https://www.shorelineeast.com/files/PDF/SLE-GTFS.zip"
        ),
    }

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "ct-town-personas/0.1"})

    # ── Public interface ──────────────────────────────────────────────────────

    def fetch_all_stops(self, force: bool = False) -> pd.DataFrame:
        """
        Download all configured CT feeds and return a combined stops DataFrame.

        Columns: stop_id, stop_name, stop_lat, stop_lon, agency
        Cached per agency in data/raw/; re-downloads only when force=True.
        Feeds that fail to download are skipped with a warning.
        """
        all_stops = []
        for agency, url in self.FEED_URLS.items():
            try:
                stops = self._fetch_stops(agency, url, force=force)
                all_stops.append(stops)
                log.info("  %s: %d stops", agency, len(stops))
            except Exception as e:
                log.warning("  Skipping %s (%s: %s)", agency, type(e).__name__, e)

        if not all_stops:
            log.error("No GTFS feeds downloaded successfully.")
            return pd.DataFrame(columns=["stop_id", "stop_name", "stop_lat", "stop_lon", "agency"])

        return pd.concat(all_stops, ignore_index=True)

    def fetch_feed(self, url: str, agency: str) -> dict[str, pd.DataFrame]:
        """
        Download a GTFS zip and return its text files as a dict of DataFrames.
        Keys are filenames without .txt (e.g. "stops", "routes", "trips").
        """
        log.info("Downloading GTFS feed for %s from %s ...", agency, url)
        resp = self.session.get(url, timeout=TIMEOUT)
        resp.raise_for_status()

        tables: dict[str, pd.DataFrame] = {}
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            for name in zf.namelist():
                if name.endswith(".txt"):
                    key = name.replace(".txt", "").split("/")[-1]
                    with zf.open(name) as f:
                        try:
                            tables[key] = pd.read_csv(f, dtype=str, low_memory=False)
                        except Exception as e:
                            log.warning("  Could not parse %s: %s", name, e)
        return tables

    def stops_near_point(
        self,
        lat: float,
        lon: float,
        radius_km: float,
        stops_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Return all stops within radius_km of a lat/lon point.

        Expects stops_df to have stop_lat and stop_lon columns (numeric).
        """
        df = stops_df.copy()
        df["dist_km"] = df.apply(
            lambda row: _haversine_km(lat, lon, row["stop_lat"], row["stop_lon"]),
            axis=1,
        )
        return df[df["dist_km"] <= radius_km].sort_values("dist_km").reset_index(drop=True)

    def assign_stops_to_towns(
        self,
        stops_df: pd.DataFrame,
        centroids_df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        Assign each stop to the nearest CT town centroid.

        Returns stops_df with an added `town` column.
        Uses town_centroids.parquet if available, otherwise the hardcoded table.
        """
        centroids = centroids_df if centroids_df is not None else _load_centroids()

        stops = stops_df.copy()
        stops["stop_lat"] = pd.to_numeric(stops["stop_lat"], errors="coerce")
        stops["stop_lon"] = pd.to_numeric(stops["stop_lon"], errors="coerce")
        stops = stops.dropna(subset=["stop_lat", "stop_lon"])

        # For each stop, find nearest town centroid
        towns = centroids[["town", "centroid_lat", "centroid_lon"]].values
        assigned = []
        for _, row in stops.iterrows():
            nearest = min(
                towns,
                key=lambda t: _haversine_km(row["stop_lat"], row["stop_lon"], t[1], t[2]),
            )
            assigned.append(nearest[0])

        stops["town"] = assigned
        return stops

    def town_transit_summary(
        self,
        stops_with_towns: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Aggregate stop-level data to per-town transit metrics.

        Returns DataFrame with columns:
          town, stop_count, has_transit, agency_count, agencies
        Saved to data/processed/gtfs_town_transit.parquet.
        """
        summary = (
            stops_with_towns.groupby("town")
            .agg(
                stop_count=("stop_id", "count"),
                agency_count=("agency", "nunique"),
                agencies=("agency", lambda x: ",".join(sorted(x.unique()))),
            )
            .reset_index()
        )
        summary["has_transit"] = True

        # Ensure all CT towns appear (fill towns with no stops)
        all_towns = pd.DataFrame({"town": _load_centroids()["town"].tolist()})
        summary = all_towns.merge(summary, on="town", how="left")
        summary["stop_count"] = summary["stop_count"].fillna(0).astype(int)
        summary["has_transit"] = summary["has_transit"].fillna(False).astype(bool)
        summary["agency_count"] = summary["agency_count"].fillna(0).astype(int)
        summary["agencies"] = summary["agencies"].fillna("")

        out = PROCESSED_DIR / "gtfs_town_transit.parquet"
        summary.to_parquet(out, index=False)
        log.info("Saved town transit summary -> %s (%d towns)", out, len(summary))
        return summary

    def build_town_transit(self, force: bool = False) -> pd.DataFrame:
        """
        Convenience method: fetch all feeds, assign stops to towns, summarize.

        This is the main entry point called from run_all.py.
        Returns the per-town summary DataFrame.
        """
        out = PROCESSED_DIR / "gtfs_town_transit.parquet"
        if out.exists() and not force:
            log.info("Loading town transit summary from cache: %s", out)
            return pd.read_parquet(out)

        stops = self.fetch_all_stops(force=force)
        if stops.empty:
            return pd.DataFrame()

        stops_with_towns = self.assign_stops_to_towns(stops)
        return self.town_transit_summary(stops_with_towns)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _fetch_stops(self, agency: str, url: str, force: bool = False) -> pd.DataFrame:
        """Download a single feed and return its stops table with agency column."""
        cache_path = RAW_DIR / f"gtfs_stops_{agency}.parquet"
        if cache_path.exists() and not force:
            log.info("Loading %s stops from cache: %s", agency, cache_path)
            return pd.read_parquet(cache_path)

        feed = self.fetch_feed(url, agency)
        if "stops" not in feed:
            raise ValueError(f"No stops.txt found in {agency} GTFS feed")

        stops = feed["stops"][["stop_id", "stop_name", "stop_lat", "stop_lon"]].copy()
        stops["stop_lat"] = pd.to_numeric(stops["stop_lat"], errors="coerce")
        stops["stop_lon"] = pd.to_numeric(stops["stop_lon"], errors="coerce")
        stops = stops.dropna(subset=["stop_lat", "stop_lon"])
        stops["agency"] = agency

        stops.to_parquet(cache_path, index=False)
        return stops


# ── Helpers ───────────────────────────────────────────────────────────────────

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    if any(math.isnan(x) for x in [lat1, lon1, lat2, lon2]):
        return float("inf")
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _load_centroids() -> pd.DataFrame:
    """Load town centroids, preferring the computed Parquet over the hardcoded table."""
    computed = PROCESSED_DIR / "town_centroids.parquet"
    if computed.exists():
        df = pd.read_parquet(computed)
        # Normalize column names to centroid_lat/centroid_lon
        if "town_lat" in df.columns:
            df = df.rename(columns={"town_lat": "centroid_lat", "town_lon": "centroid_lon"})
        return df

    # Fall back to drive_time's hardcoded table
    from pipeline.drive_time import ct_town_centroids
    df = ct_town_centroids()
    return df.rename(columns={"town_lat": "centroid_lat", "town_lon": "centroid_lon"})
