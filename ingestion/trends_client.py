"""
ingestion/trends_client.py
Google Trends interest data via pytrends.

Fetches search interest at DMA (Designated Market Area) level for
tourism-related keywords. CT spans four DMAs:

  533  Hartford & New Haven   (most of CT)
  501  New York               (Fairfield County)
  521  Providence-New Bedford (eastern CT)
  543  Springfield-Holyoke    (far northern CT)

Data is DMA-level, NOT town-level. The CLAUDE.md methodology explicitly
acknowledges this — do not present output as town-level interest.

Use: marketing intensity proxy for Post #3 (Under-marketed CT submarkets).
Compare opportunity scores (high demographic fit, accessible) against
observed search interest to surface where demand exists but marketing
presence is thin.

Caches raw results as Parquet to avoid repeated API calls. pytrends is
an unofficial API — expect occasional 429s; the client backs off and retries.

Serves: Post #3 — Under-marketed CT submarkets
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

import pandas as pd

log = logging.getLogger(__name__)

RAW_DIR = Path(__file__).parents[1] / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# CT DMAs: code → label
CT_DMAS = {
    533: "Hartford-New Haven",
    501: "New York",
    521: "Providence-New Bedford",
    543: "Springfield-Holyoke",
}

# Default tourism keywords. Override per-call for attraction-specific queries.
DEFAULT_KEYWORDS = [
    "Connecticut museums",
    "things to do Connecticut",
    "Connecticut family activities",
    "Connecticut science center",
    "Connecticut day trips",
]

_RETRY_WAIT = 60   # seconds to wait on 429
_MAX_RETRIES = 3


class TrendsClient:
    """Fetch Google Trends interest data for CT tourism keywords."""

    def __init__(self) -> None:
        try:
            from pytrends.request import TrendReq
            self._pytrends = TrendReq(hl="en-US", tz=300, timeout=(10, 25))
        except ImportError:
            raise ImportError(
                "pytrends is required: pip install pytrends"
            )

    # ── Public interface ──────────────────────────────────────────────────────

    def fetch_interest_over_time(
        self,
        keywords: Optional[list[str]] = None,
        timeframe: str = "today 12-m",
        geo: str = "US-CT",
        force: bool = False,
    ) -> pd.DataFrame:
        """
        Fetch interest-over-time for keywords in Connecticut.

        Returns a DataFrame indexed by date with one column per keyword (0–100).
        Cached to data/raw/trends_iot_{slug}.parquet.

        Args:
            keywords:  Up to 5 keywords (pytrends limit per request).
            timeframe: pytrends timeframe string, e.g. "today 12-m", "2022-01-01 2023-01-01".
            geo:       Geography — "US-CT" for statewide, or "" for global.
        """
        kws = keywords or DEFAULT_KEYWORDS[:5]
        slug = "_".join(k.lower().replace(" ", "-")[:15] for k in kws[:2])
        cache_path = RAW_DIR / f"trends_iot_{slug}.parquet"

        if cache_path.exists() and not force:
            log.info("Loading trends (interest over time) from cache: %s", cache_path)
            return pd.read_parquet(cache_path)

        self._build_payload(kws, timeframe=timeframe, geo=geo)
        df = self._retry(lambda: self._pytrends.interest_over_time())

        if df.empty:
            log.warning("Trends returned empty DataFrame for keywords: %s", kws)
            return df

        if "isPartial" in df.columns:
            df = df.drop(columns=["isPartial"])

        df.to_parquet(cache_path)
        log.info("Saved trends (interest over time) -> %s (%d rows)", cache_path, len(df))
        return df

    def fetch_interest_by_dma(
        self,
        keywords: Optional[list[str]] = None,
        timeframe: str = "today 12-m",
        force: bool = False,
    ) -> pd.DataFrame:
        """
        Fetch interest by DMA for CT-relevant DMAs.

        Returns a DataFrame with columns: dma_id, dma_name, keyword, interest (0–100).
        Cached to data/raw/trends_dma_{slug}.parquet.

        Note: pytrends returns all US DMAs — this method filters to the four
        CT-relevant DMAs defined in CT_DMAS.
        """
        kws = keywords or DEFAULT_KEYWORDS[:5]
        slug = "_".join(k.lower().replace(" ", "-")[:15] for k in kws[:2])
        cache_path = RAW_DIR / f"trends_dma_{slug}.parquet"

        if cache_path.exists() and not force:
            log.info("Loading trends (by DMA) from cache: %s", cache_path)
            return pd.read_parquet(cache_path)

        self._build_payload(kws, timeframe=timeframe, geo="US")
        raw = self._retry(lambda: self._pytrends.interest_by_region(resolution="DMA", inc_low_vol=True))

        if raw.empty:
            log.warning("Trends by DMA returned empty DataFrame")
            return raw

        # Reshape to long format and filter to CT DMAs
        raw = raw.reset_index()
        long = raw.melt(id_vars=["geoName"], var_name="keyword", value_name="interest")
        long = long.rename(columns={"geoName": "dma_name"})

        ct_dma_names = set(CT_DMAS.values())
        long = long[long["dma_name"].isin(ct_dma_names)].copy()

        dma_id_map = {v: k for k, v in CT_DMAS.items()}
        long["dma_id"] = long["dma_name"].map(dma_id_map)
        long = long[["dma_id", "dma_name", "keyword", "interest"]].reset_index(drop=True)

        long.to_parquet(cache_path, index=False)
        log.info(
            "Saved trends (by DMA) -> %s (%d DMA×keyword rows)", cache_path, len(long)
        )
        return long

    def fetch_related_queries(
        self,
        keywords: Optional[list[str]] = None,
        timeframe: str = "today 12-m",
        geo: str = "US-CT",
    ) -> dict[str, pd.DataFrame]:
        """
        Fetch rising and top related queries for each keyword.

        Returns {keyword: DataFrame with columns [query, value, type]}.
        Not cached — use sparingly for exploratory work.
        """
        kws = keywords or DEFAULT_KEYWORDS[:5]
        self._build_payload(kws, timeframe=timeframe, geo=geo)
        raw = self._retry(lambda: self._pytrends.related_queries())

        result = {}
        for kw, data in raw.items():
            frames = []
            for kind in ("top", "rising"):
                df = data.get(kind)
                if df is not None and not df.empty:
                    df = df.copy()
                    df["type"] = kind
                    frames.append(df)
            if frames:
                result[kw] = pd.concat(frames, ignore_index=True)

        return result

    # ── Internal ──────────────────────────────────────────────────────────────

    def _build_payload(self, kws: list[str], timeframe: str, geo: str) -> None:
        self._pytrends.build_payload(kws, timeframe=timeframe, geo=geo)

    def _retry(self, fn, retries: int = _MAX_RETRIES):
        """Call fn(), backing off on 429 responses."""
        from requests.exceptions import HTTPError
        for attempt in range(retries):
            try:
                return fn()
            except HTTPError as e:
                if "429" in str(e) and attempt < retries - 1:
                    wait = _RETRY_WAIT * (attempt + 1)
                    log.warning("pytrends rate-limited (429). Waiting %ds ...", wait)
                    time.sleep(wait)
                else:
                    raise
        return pd.DataFrame()
