.PHONY: install discover validate pipeline pipeline-tune api frontend dev clean lint help

# ── Config ────────────────────────────────────────────────────────────────────
YEAR        ?= 2022
API_HOST    ?= 0.0.0.0
API_PORT    ?= 8000
FRONTEND_DIR = frontend

# ── Setup ────────────────────────────────────────────────────────────────────
install:
	@echo "→ Installing Python dependencies..."
	pip install -e ".[dev]" || pip install -r requirements.txt
	@echo "→ Installing frontend dependencies..."
	cd $(FRONTEND_DIR) && npm install
	@echo "✓ All dependencies installed"

install-python:
	pip install -r requirements.txt

install-frontend:
	cd $(FRONTEND_DIR) && npm install

# ── Pipeline ─────────────────────────────────────────────────────────────────
pipeline:
	@echo "→ Running full data pipeline for vintage $(YEAR)..."
	PYTHONPATH=. python -m pipeline.run_all --year $(YEAR)
	@echo "✓ Pipeline complete — data in data/processed/"


mock:
	@echo "→ Generating mock data for all 169 CT towns (no API keys needed)..."
	PYTHONPATH=. python -m pipeline.generate_mock
	@echo "✓ Mock data ready — run: make api"

discover:
	@echo "→ Discovering CTData resource IDs..."
	@echo "   Queries data.ctdata.org CKAN API for real resource_ids."
	PYTHONPATH=. python -m ingestion.discover

validate:
	@echo "→ Checking datasets.yaml for placeholder IDs..."
	@python3 -c "import yaml, sys; reg = yaml.safe_load(open('ingestion/datasets.yaml')); missing = [d['name'] for d in reg['datasets'] if d.get('id') == 'RUN_DISCOVER']; [print(f'  MISSING: {n}') for n in missing]; sys.exit(1) if missing else print('  All IDs filled in') "

pipeline-tune:
	@echo "→ Running cluster tuning (elbow + silhouette)..."
	PYTHONPATH=. python -c "import pandas as pd; from pipeline.cluster import TownClusterer; df = pd.read_parquet('data/processed/town_features_all_years.parquet'); TownClusterer().tune_k(df)"

# ── API ───────────────────────────────────────────────────────────────────────
api:
	@echo "→ Starting FastAPI on http://$(API_HOST):$(API_PORT)"
	@echo "   Swagger UI: http://localhost:$(API_PORT)/docs"
	PYTHONPATH=. uvicorn api.main:app \
		--host $(API_HOST) \
		--port $(API_PORT) \
		--reload

api-prod:
	PYTHONPATH=. uvicorn api.main:app \
		--host $(API_HOST) \
		--port $(API_PORT) \
		--workers 2

# ── Frontend ─────────────────────────────────────────────────────────────────
frontend:
	@echo "→ Starting React dev server..."
	cd $(FRONTEND_DIR) && npm run dev

frontend-build:
	@echo "→ Building React for production..."
	cd $(FRONTEND_DIR) && npm run build

# ── Dev (both API + frontend concurrently) ────────────────────────────────────
dev:
	@echo "→ Starting API + frontend concurrently..."
	@command -v concurrently >/dev/null 2>&1 || npm install -g concurrently
	PYTHONPATH=. concurrently \
		--names "API,FRONTEND" \
		--prefix-colors "cyan,magenta" \
		"uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload" \
		"cd frontend && npm run dev"

# ── Lint / Test ───────────────────────────────────────────────────────────────
lint:
	ruff check ingestion/ pipeline/ api/

test:
	PYTHONPATH=. pytest tests/ -v

# ── Utilities ─────────────────────────────────────────────────────────────────
clean:
	@echo "→ Cleaning generated data (raw + processed)..."
	rm -rf data/raw/* data/processed/*
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
	@echo "✓ Clean"

clean-all: clean
	cd $(FRONTEND_DIR) && rm -rf node_modules dist

# ── Help ─────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  CT Town Personas — available commands"
	@echo "  ──────────────────────────────────────"
	@echo "  make install          Install all Python + frontend deps"
	@echo "  make pipeline         Run full ETL + ML pipeline"
	@echo "  make pipeline YEAR=2021  Run for a specific ACS vintage"
	@echo "  make mock              Generate mock data (no API keys)"
	@echo "  make pipeline-tune    Tune number of clusters (elbow analysis)"
	@echo "  make api              Start FastAPI dev server"
	@echo "  make frontend         Start React dev server"
	@echo "  make dev              Start both concurrently"
	@echo "  make lint             Run ruff linter"
	@echo "  make test             Run pytest"
	@echo "  make clean            Remove generated data files"
	@echo ""
