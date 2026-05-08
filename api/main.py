"""
api/main.py
FastAPI application. Loads processed Parquet data at startup into app.state
so routers can access it via request.app.state (no circular imports).
"""

import logging
from pathlib import Path
from contextlib import asynccontextmanager

import pandas as pd
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Loading processed data ...")
    try:
        app.state.features  = pd.read_parquet(PROCESSED_DIR / "town_features_all_years.parquet")
        app.state.clusters  = pd.read_parquet(PROCESSED_DIR / "town_clusters.parquet")
        app.state.centroids = pd.read_parquet(PROCESSED_DIR / "cluster_centroids.parquet")
        logger.info(f"  Loaded {len(app.state.features)} feature rows across "
                    f"{app.state.features['town'].nunique()} towns")
    except FileNotFoundError as e:
        logger.warning(f"Processed data not found ({e}). Run: make pipeline")
        app.state.features  = pd.DataFrame()
        app.state.clusters  = pd.DataFrame()
        app.state.centroids = pd.DataFrame()
    yield


app = FastAPI(
    title="CT Town Personas API",
    description="Town-level demographic, economic, and persona intelligence for Connecticut's 169 municipalities.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Routers imported after app is created to avoid circular imports
from api.routers import towns, personas, forecast  # noqa: E402

app.include_router(towns.router,    prefix="/towns",    tags=["Towns"])
app.include_router(personas.router, prefix="/personas", tags=["Personas"])
app.include_router(forecast.router, prefix="/forecast", tags=["Forecast"])


@app.get("/", tags=["Health"])
def root(request: Request):
    feat = getattr(request.app.state, "features", pd.DataFrame())
    return {
        "status": "ok",
        "towns_loaded": int(feat["town"].nunique()) if not feat.empty else 0,
        "message": "CT Town Personas API — visit /docs for Swagger UI",
    }


@app.get("/towns-list", tags=["Health"])
def list_towns(request: Request):
    feat = getattr(request.app.state, "features", pd.DataFrame())
    if feat.empty:
        raise HTTPException(503, "Data not loaded. Run: make pipeline")
    return {
        "towns": sorted(feat["town"].dropna().unique().tolist()),
        "years": sorted(int(y) for y in feat["year"].dropna().unique()),
    }
