# CT Town Personas

> **Who will you meet there?**  
> ML-generated audience profiles, market intelligence, and demographic trend forecasts for every town in Connecticut — built on public data, designed for public benefit.

---

## The Business Case

Connecticut has 169 towns. Every one of them is different in ways that matter — economically, demographically, culturally. Yet the tools available to understand those differences are mostly static PDFs, pivot tables, and point-in-time dashboards. The people who need this intelligence the most — a small business owner deciding where to open, a nonprofit designing an outreach campaign, a marketer trying to reach the right audience — typically can't afford the research firms that serve Fortune 500 companies.

**CT Town Personas changes that equation.**

By applying machine learning to the wealth of public data that CTData.org and the CT Open Data Portal already maintain, this project generates something new: *narrative intelligence at town level* — the kind of insight you'd normally get from a $30,000 market research engagement, made freely available to any Connecticut resident.

### Who benefits

| User | What they get |
|---|---|
| **Small business owner** | Which towns have underserved markets in their category, buying power indices, business formation rates, survival rates — before signing a lease |
| **Marketer / agency** | Audience persona cards with channel guidance, psychographic proxies, messaging angles, and new-resident targeting opportunities |
| **Nonprofit / policy** | Town archetypes that reveal structural similarities across geographies — "Waterbury and Bridgeport cluster together because..." |
| **CTData** | A next-generation evolution of the Town Profiles product that already exists — now with ML-generated insight and predictive forecasting |

### Why now

CTData already publishes [Town Profiles](https://www.ctdata.org/regional) — two-page PDFs of demographic and economic snapshots. This project takes that concept to its logical next level:

- **From static → dynamic**: profiles refresh automatically as data updates
- **From descriptive → predictive**: Prophet time-series forecasting on 10 key indicators
- **From single snapshot → multi-persona**: each town gets multiple weighted archetypes (via Gaussian Mixture Models) because a town is rarely one thing
- **From data export → intelligence product**: narrative persona cards that translate census statistics into human-readable business and marketing insight

---

## What Makes This Different

Most data portals show you *what is*. This shows you *who's there and where things are going*.

```
Standard town profile                CT Town Personas
─────────────────────────────        ─────────────────────────────────────────────
Median household income: $94,200     ↳ "Affluent Suburban" archetype (71%)
Bachelor's degree or higher: 54%        → Premium buyer segment (high)
Owner-occupied units: 68%               → High research intent — long buying cycles
Businesses: 847                         → Homeowner majority — home services gap
                                         → Direct mail: HIGH | Digital: HIGH
                                         → LinkedIn recommended
                                      Trend: median income ↑ moderate through 2028
                                      Similar towns: Simsbury, Glastonbury, Madison
```

---

## Data Architecture

### Sources

| Source | Dataset | Update cadence | What it contributes |
|---|---|---|---|
| **Census ACS 5-yr** | via Census API | Annual | Demographics, income, housing, education, commute, migration |
| **CT SOTS Business Master** | `n7gp-d28j` on data.ct.gov | **Monthly** | Active business counts, status, NAICS classification |
| **CT SOTS Filing History** | `ah3s-bes7` on data.ct.gov | **Monthly** | Business formation and dissolution events (velocity) |
| **CT Education — Attendance** | `udsn-sgpn` on data.ct.gov | Annual | Chronic absenteeism by district |
| **CT Housing Hub** | `djxj-q6c8` on data.ct.gov | Annual | Building permits, new units |
| **Population Projections** | `p6hp-fnp7` on data.ct.gov | Periodic | 2015–2040 projections by town |

All Socrata datasets are pulled via the [SODA API](https://dev.socrata.com/) using `sodapy`. The Census ACS data is fetched directly from `api.census.gov`.

### ML Pipeline

```
Raw data (Socrata + Census ACS)
        │
        ▼
Feature Engineering (pandas)
  169 towns × ~40 indicators per year
        │
        ├──▶  KMeans clustering → hard town archetype assignment
        │
        └──▶  Gaussian Mixture Model → soft probability distribution
                 "This town is 68% Affluent Suburban, 32% Young Professional"
                         │
                         ▼
              Persona card generation
              (centroid → narrative intelligence)
                         │
                         ▼
              Prophet time-series forecasting
              (10 key indicators × 169 towns × 5-yr horizon)
```

### Town archetypes (5 clusters, tunable)

| Archetype | Typical profile |
|---|---|
| **Affluent Suburban** | High income, high homeownership, graduate degrees, long commutes |
| **Working-Class Urban** | Moderate income, renter-heavy, service sector dominant |
| **Rural / Small Town** | Low business density, high stability, aging population |
| **Young Professional** | High WFH %, bachelor's degrees, high in-migration, formation rate |
| **Mixed-Income Transitional** | Bifurcated income distribution, gentrification signals |

> **Note:** These labels are assigned after fitting on real data. Run `make pipeline-tune` to inspect silhouette scores and rename archetypes to match what you observe in the clusters.

### API endpoints

```
GET /                          Health check + rows loaded
GET /towns-list                All 169 towns + available years
GET /personas/{town}           Full persona payload (both views)
GET /personas/{town}/marketer  Marketer-only persona cards
GET /personas/{town}/business  Business owner-only persona cards
GET /personas/similar/{town}   N most similar towns by PCA distance
GET /towns/archetypes/all      All cluster centroids + representative towns
GET /towns/{town}              Raw feature indicators for a town
GET /towns/{town}/compare      Side-by-side two towns
GET /forecast/{town}/{indicator}  Prophet forecast for one indicator
GET /forecast/{town}           All indicator forecasts for a town
```

Full interactive docs at `http://localhost:8000/docs` once running.

---

## Getting Started

### What you need

- **Python 3.11+** — check with `python3 --version`
- **Node.js 18+** — check with `node --version`
- **A Census API key** (free, takes 30 seconds) — [register here](https://api.census.gov/data/key_signup.html). Without it you'll get rate-limited after a few requests.
- **A Socrata app token** (optional but recommended) — [register here](https://dev.socrata.com/register). Without it you share a throttled pool with other anonymous users.

### Step 1 — Clone and configure

```bash
git clone https://github.com/YOUR_USERNAME/ct-town-personas.git
cd ct-town-personas

cp .env.example .env
```

Open `.env` and fill in your keys:

```
SOCRATA_APP_TOKEN=your_token_here
CENSUS_API_KEY=your_key_here
```

### Step 2 — Install dependencies

```bash
make install
```

This runs `pip install -r requirements.txt` and `npm install` inside `frontend/`. Expect it to take 2–3 minutes the first time (Prophet and scikit-learn are large).

**If `make` isn't available on Windows**, run manually:

```bash
pip install -r requirements.txt
cd frontend && npm install
```

### Step 3 — Discover real resource IDs

Before the pipeline can run, it needs the real `resource_id` UUIDs from CTData's CKAN API. These are not hardcoded because they can change — instead, a discovery script fetches them live.

```bash
make discover
```

This queries `data.ctdata.org` for every dataset we use, prints its `resource_id`, and shows you a sample row so you can verify the column names. Output looks like:

```
── median-household-income-by-town
  Title:       Median Household Income by Town
  Resource ID: 50f596eb-b0dc-4a9c-96f4-b8cfd653b103   ← copy this
  Columns:     ['Town', 'Year', 'Race/Ethnicity', 'Measure Type', 'Value']
  Town col:    Town
  Year col:    Year
  Value cols:  ['Value']

── major-employers
  Title:       Major Employers
  Resource ID: a1b2c3d4-...                            ← copy this
  Columns:     ['Town', 'Year', 'Rank', 'Employer']
```

Copy the resource IDs into `ingestion/datasets.yaml`, replacing each `RUN_DISCOVER` placeholder. Then confirm all IDs are filled in:

```bash
make validate
# Expected output: ✓ All dataset IDs are filled in
```

> **Note:** One resource ID is already confirmed — `50f596eb-b0dc-4a9c-96f4-b8cfd653b103` for Median Household Income. You can verify it works right now: `curl "http://data.ctdata.org/api/action/datastore_search?resource_id=50f596eb-b0dc-4a9c-96f4-b8cfd653b103&limit=2"`

### Step 4 — Run the pipeline

```bash
make pipeline
# Or for a specific year:
make pipeline YEAR=2021
```

This runs five sequential steps. Expect **5–10 minutes** depending on your connection.

**What you'll see:**

```
2024-01-15 10:23:01 | INFO | run_all | ============================================================
2024-01-15 10:23:01 | INFO | run_all | CT Town Personas Pipeline — ACS vintage 2022
2024-01-15 10:23:01 | INFO | run_all | ============================================================

[1/4] Ingesting data ...
2024-01-15 10:23:04 | INFO | census_client | ✓ population_by_race (169 towns)
2024-01-15 10:23:11 | INFO | census_client | ✓ housing_characteristics (169 towns)
  ...
2024-01-15 10:24:30 | INFO | socrata_client | Fetching 'business_master' (n7gp-d28j) ...
2024-01-15 10:25:10 | INFO | socrata_client |   → 312,847 rows, ['town', 'filing_date', ...]

[2/4] Building feature matrix ...
2024-01-15 10:25:15 | INFO | feature_builder | Feature matrix saved → data/processed/town_features_2022.parquet (162 rows × 41 cols)

[3/4] Clustering towns (k=5) ...
2024-01-15 10:25:17 | INFO | cluster | KMeans silhouette score: 0.341
2024-01-15 10:25:18 | INFO | cluster | PCA 2D explains 71.3% of variance

[4/4] Building persona cards ...
  Built personas for Andover ... Woodstock

✓ Pipeline complete. Output → data/processed/
```

### Step 5 — Start the API

```bash
make api
```

You should see:

```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Loaded 162 feature rows across 162 towns
```

**Validate the API is working:**

```bash
# Health check
curl http://localhost:8000/

# List all towns
curl http://localhost:8000/towns-list | python3 -m json.tool | head -20

# Pull personas for one town
curl http://localhost:8000/personas/Greenwich | python3 -m json.tool
```

Expected response for `/`:
```json
{
  "status": "ok",
  "towns_loaded": 162,
  "message": "CT Town Personas API — visit /docs for Swagger UI"
}
```

> **If `towns_loaded` is 0**: the pipeline hasn't run yet or failed. Check `data/processed/` — it should contain `town_features_all_years.parquet`, `town_clusters.parquet`, and `cluster_centroids.parquet`. Re-run `make pipeline` and check logs for errors.

### Step 6 — Start the frontend

In a second terminal:

```bash
make frontend
```

Open **http://localhost:5173** in your browser. You should see the CT Town Personas interface. Search for any Connecticut town to see its persona cards.

**Or run both simultaneously:**

```bash
make dev
```

---

## Validating the Results

Once the pipeline has run, here's how to check that the output is meaningful — not just that it ran without errors, but that the clusters and personas make sense.

### 1. Sanity-check the cluster assignments

```bash
python3 - << 'EOF'
import pandas as pd
df = pd.read_parquet("data/processed/town_clusters.parquet")
print(df.groupby("archetype_label")["town"].apply(list).to_string())
EOF
```

**What to look for:** Do towns group sensibly? Greenwich, Westport, Darien, and New Canaan should all land in the same high-income cluster. Hartford, Bridgeport, and New Haven should cluster together. Andover, Bozrah, and Canaan should form a rural cluster. If the groupings look wrong, try tuning k:

```bash
make pipeline-tune
```

This prints silhouette scores for k=3 through k=8. Pick the k where the silhouette score peaks and re-run:

```bash
make pipeline YEAR=2022 && python3 -m pipeline.run_all --n-clusters 6
```

### 2. Inspect the feature matrix

```bash
python3 - << 'EOF'
import pandas as pd
df = pd.read_parquet("data/processed/town_features_all_years.parquet")
print(f"Shape: {df.shape}")
print(f"Towns: {df['town'].nunique()}")
print(f"Years: {sorted(df['year'].unique())}")
print("\nMissing values by column:")
print(df.isnull().sum()[df.isnull().sum() > 0].sort_values(ascending=False))
EOF
```

**What to look for:**
- You want **~162–169 towns** (some small towns get suppressed by Census for privacy)
- `businesses_per_1k` will be null for towns with no business data — this is expected for very small towns
- If more than 20 columns have >50% nulls, something went wrong in the ACS fetch — re-run with your Census API key set

### 3. Test the API against known towns

```bash
# Westport should be "Affluent Suburban" dominant
curl -s "http://localhost:8000/personas/Westport" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('Dominant:', d['dominant_archetype'])
print('Top persona weight:', max(p['weight'] for p in d['personas']))
print('Personas:', [p['archetype'] for p in d['personas']])
"

# Hartford should be "Working-Class Urban" dominant
curl -s "http://localhost:8000/personas/Hartford" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('Dominant:', d['dominant_archetype'])
"

# Windham (rural, lower-income) should differ clearly from both
curl -s "http://localhost:8000/personas/Windham" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('Dominant:', d['dominant_archetype'])
"
```

### 4. Verify forecast is directionally sensible

```bash
curl -s "http://localhost:8000/forecast/Greenwich/median_household_income" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('Trend:', d['trend_direction'], '/', d['trend_magnitude'])
print('Last historical:', d['historical'][-1])
print('5yr forecast end:', d['forecast'][-1])
"
```

**What to look for:** Greenwich median household income should trend increasing. If it shows strongly decreasing, there's likely a data issue in the historical series — check the raw ACS pull.

### 5. Check the Similar Towns endpoint makes geographic sense

```bash
curl -s "http://localhost:8000/personas/similar/Simsbury?n=5" | python3 -m json.tool
```

Simsbury's similar towns should include Glastonbury, South Windsor, Tolland — other affluent Hartford-area suburbs. If it returns towns from opposite ends of the state with different profiles, the PCA coordinates may need re-examination.

---

## Running Multiple Vintages

To build a multi-year history for forecasting, run the pipeline for each available ACS vintage. The `all_years` file appends automatically:

```bash
make pipeline YEAR=2019
make pipeline YEAR=2020
make pipeline YEAR=2021
make pipeline YEAR=2022
```

More historical years = better Prophet forecasts. With 4+ years, the trend lines become meaningful. The API always serves the most recent vintage for persona cards but uses all years for forecasting.

---

## Project Structure

```
ct-town-personas/
├── ingestion/
│   ├── socrata_client.py     Socrata/SODA API wrapper (data.ct.gov)
│   ├── census_client.py      Census ACS API client
│   └── datasets.yaml         Master registry of all dataset IDs + field maps
├── pipeline/
│   ├── feature_builder.py    Pandas feature engineering (raw → indicators)
│   ├── cluster.py            KMeans + GMM town clustering
│   ├── persona.py            Centroid → narrative persona card generation
│   ├── forecast.py           Prophet time-series forecasting
│   └── run_all.py            Pipeline orchestrator
├── api/
│   ├── main.py               FastAPI app + startup data loading
│   ├── models.py             Pydantic response schemas
│   └── routers/
│       ├── towns.py          /towns/* endpoints
│       ├── personas.py       /personas/* endpoints
│       └── forecast.py       /forecast/* endpoints
├── frontend/
│   └── src/
│       ├── App.jsx           Main layout + town selector
│       ├── api.js            All fetch calls in one place
│       ├── components/
│       │   ├── MarketerView.jsx
│       │   ├── BusinessView.jsx
│       │   ├── ForecastPanel.jsx
│       │   ├── SimilarTowns.jsx
│       │   └── ui.jsx        Shared design system components
│       └── hooks/
│           └── useFetch.js
├── data/
│   ├── raw/                  Gitignored — raw API pulls (Parquet)
│   └── processed/            Gitignored — pipeline outputs (Parquet)
├── Makefile                  Developer commands
└── .github/workflows/
    └── pipeline.yml          Monthly automated refresh
```

---

## Roadmap

- [ ] **Neighborhood-level data** for Hartford via the Hartford Data Collaborative integration
- [ ] **Map view** — choropleth of CT towns colored by archetype
- [ ] **Compare mode** — side-by-side two towns across all indicators
- [ ] **Export** — persona card PDF/PNG for presentations and pitches
- [ ] **LLM-enhanced narratives** — replace rule-based persona descriptions with Claude-generated summaries from cluster centroids
- [ ] **Real-time SOTS refresh** — webhook or nightly job to update business data monthly without re-running ACS

---

## Data Sources & Acknowledgments

Built on data maintained by:
- [CTData Collaborative](https://www.ctdata.org/) — Connecticut's State Data Center
- [CT Open Data Portal](https://data.ct.gov/) — powered by Socrata / Tyler Technologies
- [US Census Bureau](https://www.census.gov/) — American Community Survey 5-year estimates
- [CT Secretary of the State](https://portal.ct.gov/SOTS) — Business Registry (SOTS)

All data is public domain. This project does not collect or store any personally identifiable information.

---

## License

MIT — use it, fork it, build on it.

*Built as a pitch to CTData Collaborative to demonstrate what's possible when public data meets modern ML tooling.*
