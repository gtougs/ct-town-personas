"""
ingestion/tiger_client.py
Town centroid computation from LODES block coordinates.

The LODES geographic crosswalk (already downloaded by lodes_client.py) carries
blklatdd and blklondd for every census block. Aggregating these by town gives
centroid estimates that are more accurate than fixed town-hall coordinates,
because they reflect where population actually lives rather than where the
municipal building is.

Output: data/processed/town_centroids.parquet
  Columns: town, centroid_lat, centroid_lon, block_count

drive_time.add_drive_columns() prefers this file when present.

Serves: drive-time scoring accuracy, anchor opportunity scoring
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

RAW_DIR = Path(__file__).parents[1] / "data" / "raw"
PROCESSED_DIR = Path(__file__).parents[1] / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


class TIGERClient:
    """Compute town centroids from LODES block coordinates."""

    def fetch_town_centroids(self, force: bool = False) -> pd.DataFrame:
        """
        Aggregate LODES block coordinates to town-level centroids.

        Uses the xwalk cached by LODESClient. Raises FileNotFoundError if
        LODES data hasn't been downloaded yet — run lodes_client first.

        Returns DataFrame with columns: town, centroid_lat, centroid_lon, block_count
        """
        out_path = PROCESSED_DIR / "town_centroids.parquet"
        if out_path.exists() and not force:
            log.info("Loading town centroids from cache: %s", out_path)
            return pd.read_parquet(out_path)

        xwalk_path = RAW_DIR / "lehd_xwalk_ct.parquet"
        if not xwalk_path.exists():
            raise FileNotFoundError(
                f"LODES xwalk not found at {xwalk_path}. "
                "Run LODESClient().fetch_xwalk() first."
            )

        xwalk = pd.read_parquet(xwalk_path)

        # Drop blocks with missing coordinates (rare, Census privacy suppression)
        xwalk = xwalk.dropna(subset=["blklatdd", "blklondd"])
        xwalk = xwalk[
            (xwalk["blklatdd"] != 0) & (xwalk["blklondd"] != 0)
        ]

        centroids = (
            xwalk.groupby("town", as_index=False)
            .agg(
                centroid_lat=("blklatdd", "mean"),
                centroid_lon=("blklondd", "mean"),
                block_count=("tabblk2020", "count"),
            )
        )

        # Filter to plausible CT bounds (lat 40.9–42.1, lon -73.8 to -71.7)
        centroids = centroids[
            centroids["centroid_lat"].between(40.9, 42.1)
            & centroids["centroid_lon"].between(-73.8, -71.7)
        ]

        centroids.to_parquet(out_path, index=False)
        log.info(
            "Saved town centroids -> %s (%d towns)", out_path, len(centroids)
        )
        return centroids
