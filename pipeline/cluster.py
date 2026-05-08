"""
cluster.py
Clusters CT towns into archetypes using KMeans and Gaussian Mixture Models.

KMeans   → hard assignment: each town belongs to one archetype
GMM      → soft assignment: town has probability distribution across archetypes

Both are useful:
- KMeans centroids describe the "typical" town in each cluster
- GMM probabilities let us say "this town is 70% archetype A, 30% archetype B"
  which feeds the multiple-persona-per-town output

Output: data/processed/town_clusters.parquet
        data/processed/cluster_centroids.parquet
"""

import logging
import json
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.mixture import GaussianMixture
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer
from sklearn.metrics import silhouette_score

logger = logging.getLogger(__name__)

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"

# Features used for clustering — numeric, town-level signals
# Excludes categorical (top_naics_*) and identifiers
CLUSTER_FEATURES = [
    "median_age",
    "median_household_income",
    "per_capita_income",
    "median_home_value",
    "median_rent",
    "gini_ratio",
    "poverty_status",
    "snap_recipients",
    "health_insurance",
    "educational_attainment",
    "english_proficiency",
    "housing_units_built_before_1950",
    "total_assisted_units",
    "housing_permits",
    "single_parent_families",
    "residential_mobility",
    "business_formations",
    "disengaged_youth",
    "veteran_status",
    "occupied_housing_units",
    "total_households",
    "population",
]

# Human-readable archetype labels — assigned after inspecting cluster centroids.
# These are placeholders; re-label after fitting on real data.
ARCHETYPE_LABELS = {
    0: "Affluent Suburban",
    1: "Working-Class Urban",
    2: "Rural / Small Town",
    3: "Young Professional",
    4: "Mixed-Income Transitional",
}


class TownClusterer:
    """
    Fits KMeans and GMM models on the town feature matrix.
    Produces per-town cluster assignments and per-archetype centroids.
    """

    def __init__(self, n_clusters: int = 5, random_state: int = 42):
        self.n_clusters = n_clusters
        self.random_state = random_state
        self.scaler = StandardScaler()
        self.imputer = SimpleImputer(strategy="median")
        self.kmeans: Optional[KMeans] = None
        self.gmm: Optional[GaussianMixture] = None
        self.pca: Optional[PCA] = None
        self.feature_cols: list[str] = []

    def fit_predict(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """
        Main entrypoint. Fits models and returns an enriched DataFrame with:
        - cluster_id (KMeans hard assignment)
        - archetype_label (human-readable)
        - persona_probs (GMM soft probabilities, JSON array)
        - pca_x, pca_y (for 2D scatter visualization)
        """
        logger.info(f"Fitting cluster models (k={self.n_clusters}) ...")

        # Select available features
        self.feature_cols = [c for c in CLUSTER_FEATURES if c in features_df.columns]
        missing = set(CLUSTER_FEATURES) - set(self.feature_cols)
        if missing:
            logger.warning(f"  Missing features (will be skipped): {missing}")

        X_raw = features_df[self.feature_cols].values

        # Impute → Scale
        X_imputed = self.imputer.fit_transform(X_raw)
        X_scaled = self.scaler.fit_transform(X_imputed)

        # ── KMeans ───────────────────────────────────────────────────────────
        self.kmeans = KMeans(
            n_clusters=self.n_clusters,
            random_state=self.random_state,
            n_init=20,
            max_iter=500,
        )
        kmeans_labels = self.kmeans.fit_predict(X_scaled)
        sil = silhouette_score(X_scaled, kmeans_labels)
        logger.info(f"  KMeans silhouette score: {sil:.3f}")

        # ── GMM ──────────────────────────────────────────────────────────────
        self.gmm = GaussianMixture(
            n_components=self.n_clusters,
            covariance_type="full",
            random_state=self.random_state,
            n_init=5,
            max_iter=200,
        )
        self.gmm.fit(X_scaled)
        gmm_probs = self.gmm.predict_proba(X_scaled)  # shape: (n_towns, n_clusters)

        # Align GMM components to KMeans labels by majority vote
        aligned_probs = self._align_gmm_to_kmeans(gmm_probs, kmeans_labels)

        # ── PCA for visualization (2D) ────────────────────────────────────────
        self.pca = PCA(n_components=2, random_state=self.random_state)
        coords = self.pca.fit_transform(X_scaled)
        explained = self.pca.explained_variance_ratio_.sum()
        logger.info(f"  PCA 2D explains {explained:.1%} of variance")

        # ── Assemble output ──────────────────────────────────────────────────
        result = features_df[["town", "year"]].copy()
        result["cluster_id"] = kmeans_labels
        result["archetype_label"] = result["cluster_id"].map(
            lambda i: ARCHETYPE_LABELS.get(i, f"Archetype {i}")
        )
        result["persona_probs"] = [
            json.dumps({
                ARCHETYPE_LABELS.get(i, f"Archetype {i}"): round(float(p), 3)
                for i, p in enumerate(row)
            })
            for row in aligned_probs
        ]
        result["dominant_persona_pct"] = aligned_probs.max(axis=1)
        result["pca_x"] = coords[:, 0]
        result["pca_y"] = coords[:, 1]

        path = PROCESSED_DIR / "town_clusters.parquet"
        result.to_parquet(path, index=False)
        logger.info(f"  Cluster assignments saved → {path}")

        # Save centroids
        centroids = self._build_centroids(features_df, result)
        centroids_path = PROCESSED_DIR / "cluster_centroids.parquet"
        centroids.to_parquet(centroids_path, index=False)
        logger.info(f"  Centroids saved → {centroids_path}")

        return result

    def tune_k(self, features_df: pd.DataFrame, k_range: range = range(3, 9)) -> dict:
        """
        Runs elbow + silhouette analysis across a range of k values.
        Use this in the notebook to pick the right n_clusters before production.
        Returns dict of {k: {"inertia": ..., "silhouette": ...}}
        """
        self.feature_cols = [c for c in CLUSTER_FEATURES if c in features_df.columns]
        X_raw = features_df[self.feature_cols].values
        X_imputed = self.imputer.fit_transform(X_raw)
        X_scaled = self.scaler.fit_transform(X_imputed)

        results = {}
        for k in k_range:
            km = KMeans(n_clusters=k, random_state=self.random_state, n_init=20)
            labels = km.fit_predict(X_scaled)
            sil = silhouette_score(X_scaled, labels) if k > 1 else 0
            results[k] = {"inertia": km.inertia_, "silhouette": round(sil, 3)}
            logger.info(f"  k={k}: inertia={km.inertia_:.0f}, silhouette={sil:.3f}")

        return results

    def _align_gmm_to_kmeans(
        self,
        gmm_probs: np.ndarray,
        kmeans_labels: np.ndarray,
    ) -> np.ndarray:
        """
        GMM component indices don't match KMeans cluster IDs by default.
        This reorders GMM columns so component i aligns with KMeans cluster i.
        Uses majority vote: for each KMeans cluster, find the GMM component
        where most towns in that cluster have highest probability.
        """
        n_components = gmm_probs.shape[1]
        gmm_labels = gmm_probs.argmax(axis=1)

        # Build mapping: kmeans_cluster → gmm_component
        mapping = {}
        for k in range(n_components):
            mask = kmeans_labels == k
            if mask.sum() == 0:
                mapping[k] = k
                continue
            gmm_counts = np.bincount(gmm_labels[mask], minlength=n_components)
            mapping[k] = int(gmm_counts.argmax())

        # Reorder columns
        col_order = [mapping.get(k, k) for k in range(n_components)]
        # Avoid duplicate columns if mapping is imperfect
        seen = set()
        safe_order = []
        for c in col_order:
            if c not in seen:
                safe_order.append(c)
                seen.add(c)
        # Pad with unmapped
        for c in range(n_components):
            if c not in seen:
                safe_order.append(c)

        return gmm_probs[:, safe_order[:n_components]]

    def _build_centroids(
        self,
        features_df: pd.DataFrame,
        cluster_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Computes mean of each feature per cluster for use in persona generation.
        Returns one row per cluster.
        """
        merged = features_df.merge(cluster_df[["town", "year", "cluster_id", "archetype_label"]], on=["town", "year"])
        numeric_cols = [c for c in self.feature_cols if c in merged.columns]
        centroids = (
            merged.groupby(["cluster_id", "archetype_label"])[numeric_cols]
            .mean()
            .reset_index()
        )
        # Also attach representative towns (3 closest to centroid per cluster)
        centroids["representative_towns"] = centroids["cluster_id"].map(
            lambda cid: json.dumps(
                cluster_df[cluster_df["cluster_id"] == cid]
                .sort_values("dominant_persona_pct", ascending=False)["town"]
                .head(3)
                .tolist()
            )
        )
        return centroids
