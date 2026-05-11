# CT Town Personas

**Town-level decision intelligence for Connecticut tourism.**

Source-market analysis, audience persona modeling, and accessibility scoring for any Connecticut cultural attraction — built on public data, fully open source, methodology in the open.

---

## What this is

Connecticut has 169 towns and dozens of cultural attractions competing for the same audiences. The institutions that make smart marketing decisions about where to spend, who to target, and which programming to invest in usually do it on intuition plus a few demographic facts they half-remember from the last research project. The serious analytical alternatives are typically gated, opaque, or built for markets much bigger than Connecticut — none of which serve a CT museum director trying to plan next quarter's outreach.

This project is an attempt at something different: a public, reproducible, methodologically transparent intelligence layer for CT tourism. You feed it an attraction's location and audience profile. It tells you which towns are your best source markets, how those audiences break down by persona, what their accessibility looks like from your front door, and where the underserved demand is hiding.

It is built primarily for marketing directors at Connecticut museums, science centers, historical sites, aquariums, and the regional and state tourism organizations that support them. It works for any CT attraction, not just the ones it was originally designed against.

The methodology is in the open. The code is MIT-licensed. The data is public. Fork it, audit it, argue with it.

---

## What it does

For any configured attraction (an "anchor" with coordinates and audience profile), the system produces:

**Top source markets.** Ranked list of CT towns scored on a 60% demographic, 40% accessibility composite. Demographic fit is computed against the attraction's specific persona weights — a science center weights families with children differently than a historical site weighting affluent retirees. Accessibility combines drive-time band, within-band proximity, and existing commuter flow.

**Persona archetypes per town.** Five-archetype taxonomy assigned via Gaussian Mixture Model, giving soft probabilistic assignment instead of hard cluster labels. A town is not "Affluent Suburban" — it is 68% Affluent Suburban, 24% Young Professional, 8% Mixed-Income Transitional. Every archetype output includes the racial and ethnic composition of the underlying population so personas don't default to majority-population characteristics.

**Tourism behavior overlay.** Each town gets a behavioral tag derived from drive-time and existing commute flow: Day-Tripper (within 90 minutes), Weekender (90 minutes to 3 hours), Local Repeat Visitor (under 20 minutes), Special-Event Seeker (beyond 3 hours, high demographic fit). Different behaviors imply different marketing approaches.

**Multi-attraction comparison.** Configure several attractions and the system reveals where audiences overlap, where they don't, and where co-op marketing makes sense versus where attractions are competing for the same households.

**Time-series forecasting.** Prophet-based five-year forward projections on key demographic indicators, so source-market analysis isn't a one-time snapshot.

**Public API + interactive frontend.** Everything above is queryable via FastAPI endpoints and explorable via a React frontend. Readers of published posts can verify findings and slice the data on their own questions.

---

## Why this exists

I am building this in public — publishing analytical posts using the system, iterating on the methodology based on what the data reveals, and releasing each new module as I go. The posts argue specific things about CT tourism that the underlying data supports. The code lets readers verify the arguments and ask their own questions.

The narrower goal is the posts. The broader goal is to show that rigorous, transparent, reproducible analytical work on Connecticut's tourism economy can live in the open — methodology visible, data public, every claim auditable.

If you're a CT tourism professional, a DMO analyst, a museum marketing director, or a state economic-development staffer and you find the work useful, that's the point.

---

## The five archetypes

Assigned post-clustering. Stable; referenced by name in published work.

| Archetype | Typical profile | Marketing implication |
|---|---|---|
| **Affluent Suburban** | High income, high homeownership, bachelor's+ majority, long commutes, families with school-age children | Premium messaging, direct mail viable, membership conversion targets |
| **Working-Class Urban** | Moderate income, renter-heavy, dense, diverse, younger | Price-sensitive, community programming, multilingual outreach |
| **Rural/Small Town** | Low business density, aging population, high stability, lower educational attainment | Long-tail audiences, special-event campaigns, regional partnerships |
| **Young Professional** | High WFH share, bachelor's+ majority, high in-migration, no/young children | Digital-first, experiential marketing, evening programming |
| **Mixed-Income Transitional** | Bifurcated income distribution, gentrification signals, demographic flux | Bridge audiences, careful framing, opportunity for inclusive programming |

Every persona output reports the racial and ethnic composition of the cluster centroid. CT is more demographically complex than statewide averages suggest — Hartford, Bridgeport, New Haven, Waterbury, and parts of Stamford have substantially different population mixes than the state's 63% non-Hispanic white average. Persona descriptions that ignore this would be misleading.

---

## Data spine

Every quantitative claim in published work is traceable to one of these sources.

| Source | Vintage | Used for |
|---|---|---|
| ACS 5-Year Estimates (Census API) | 2022 | Demographics, income, education, race, household, commute |
| LODES Origin-Destination (Census LEHD) | 2021 | Inbound commute flows to Hartford, New Haven, Stamford, Bridgeport |
| TIGER/Line Block Centroids | 2020 | Drive-time geographic anchors |
| CT SOTS Business Master + Filings (Socrata) | Monthly | Business density, formation/dissolution velocity |
| CT Education Attendance (Socrata) | Annual | District-level signals |
| Population Projections (Socrata) | Periodic | Forecasting inputs |
| Google Trends (pytrends) | Weekly pull, DMA-level | Marketing intensity proxy |
| CT Open Data POI / Attractions (data.ct.gov) | Periodic | Attraction universe, comparable destination benchmarking |
| GTFS static feeds (CTtransit, CTfastrak, CTrail Hartford Line, Shore Line East) | Periodic | Transit accessibility, stop proximity, corridor reachability |
| CT DOT Traffic Counts / AADT (data.ct.gov) | Annual | Road accessibility proxy, corridor weighting |
| Disproportionately Impacted Areas tract list (data.ct.gov) | Periodic | Equity context layer |
| State Tourism Tracker / VISIONS | Published reports | Benchmark context only — reference, not a feed |

No paid feeds. No proprietary visitor data. No location-intelligence subscriptions.

---

## Methodology

**Scoring.** Each town receives an opportunity score (0–100) per configured anchor:

- **Demographic score (60% weight):** normalized weighted sum of income, family share, education, age, and population, with weights calibrated to the anchor's audience profile.
- **Accessibility score (40% weight):** 70% drive-band tier, 15% proximity within band, 15% LODES inbound commute flow.

**Drive-time estimation.** Haversine distance × 1.35 road factor at 66 km/h average speed. This is a deliberate simplification — it's accurate enough for ranking and band assignment, and it keeps the entire pipeline reproducible from public data with no external API dependencies. For analyses requiring tighter accuracy, the road-factor and speed parameters are configurable.

**Clustering.** KMeans for hard assignment, Gaussian Mixture Model for soft probability distribution across the five archetypes. Trained on income, education, age, household, business, housing, and commute features. Race and ethnicity are **not** clustering features — they are reported as descriptive composition of each cluster's centroid, so personas don't essentialize race into the archetype labels themselves.

**Forecasting.** Prophet time-series, fit per-town per-indicator across all available ACS vintages. Five-year horizon. Useful for directional reads, not point predictions.

**Refresh cadence.** Monthly. ACS is annual, LODES is annual with lag, Google Trends is updated weekly. Daily refresh would be operationally wasteful and editorially risky.

---

## API

Endpoints currently shipped are unmarked. Anchor-related endpoints (🚧) are in active development as part of porting the source-market analysis work into the unified pipeline.

```
GET /                                        Health check
GET /towns                                   All 169 towns + available years
GET /towns/{town}                            Raw features for a town
GET /towns/{town}/compare?with={other}       Side-by-side two towns
GET /personas/{town}                         Full persona payload
GET /personas/{town}/composition             Racial/ethnic composition of dominant archetype
GET /personas/similar/{town}?n=5             N most similar towns by PCA distance
GET /anchors                              🚧 All configured attractions
GET /anchors/{id}/top-markets?n=15        🚧 Top-N source towns for an anchor
GET /anchors/{id}/personas                🚧 Persona distribution across the anchor's catchment
GET /anchors/{id}/compare?with={other_id} 🚧 Two-anchor source-market overlap
GET /forecast/{town}/{indicator}             Prophet forecast for one indicator
GET /forecast/{town}                         All indicator forecasts for a town
```

Interactive docs at `http://localhost:8000/docs`.

---

## Getting started

### What you need

- Python 3.11+
- Node.js 18+
- A free Census API key — [register here](https://api.census.gov/data/key_signup.html)
- A free Socrata app token — [register here](https://dev.socrata.com/register)

### Setup

```bash
git clone https://github.com/gtougs/ct-town-personas.git
cd ct-town-personas
cp .env.example .env
# Fill in CENSUS_API_KEY and SOCRATA_APP_TOKEN
make install
make discover         # Resolve Socrata resource IDs
make pipeline         # Ingest → features → cluster → forecast
make dev              # API on :8000, frontend on :5173
```

The pipeline takes 5–10 minutes on first run, less on refresh.

### Validating the output

```bash
# Cluster sanity check
python3 -c "
import pandas as pd
df = pd.read_parquet('data/processed/town_clusters.parquet')
print(df.groupby('archetype_label')['town'].apply(list).to_string())
"
```

Greenwich, Westport, Darien, and New Canaan should cluster together. Hartford, Bridgeport, and New Haven should cluster together. If they don't, retune k:

```bash
make pipeline-tune
```

This prints silhouette scores for k=3 through k=8.

---

## Project structure

```
ct-town-personas/
├── ingestion/
│   ├── socrata_client.py        Socrata/SODA API wrapper
│   ├── census_client.py         Census ACS client
│   ├── lodes_client.py          LODES Origin-Destination client
│   ├── tiger_client.py          TIGER block centroid client
│   ├── trends_client.py         Google Trends via pytrends
│   ├── gtfs_client.py           GTFS static feeds (CTtransit, CTfastrak, CTrail lines)
│   └── datasets.yaml            Dataset registry + field maps
├── pipeline/
│   ├── feature_builder.py       Raw → indicator matrix
│   ├── cluster.py               KMeans + GMM
│   ├── persona.py               Centroid → narrative persona
│   ├── drive_time.py            Haversine × road-factor engine
│   ├── anchors.py               Anchor config + opportunity scoring
│   ├── behavior_overlay.py      Day-Tripper / Weekender / Local Repeat
│   ├── forecast.py              Prophet forecasting
│   └── run_all.py               Orchestrator
├── api/
│   ├── main.py                  FastAPI app
│   ├── models.py                Pydantic schemas
│   └── routers/
│       ├── towns.py
│       ├── personas.py
│       ├── anchors.py
│       └── forecast.py
├── frontend/
│   └── src/                     React/Vite app
├── posts/                       Published post drafts + companion notebooks
├── data/
│   ├── raw/                     Gitignored — raw API pulls
│   └── processed/               Gitignored — pipeline outputs
└── .github/workflows/
    └── pipeline.yml             Monthly automated refresh
```

---

## Posts and analytical work

Each published post lives in `posts/` as a markdown draft plus a reproducible notebook. The first three planned posts:

1. **Commuter arbitrage.** Where existing daily commute flows tell us about latent leisure-visit demand for CT attractions. (LODES-driven; the analytical foundation.)
2. **Under-marketed CT submarkets.** Where demographic opportunity outruns visible tourism marketing presence. (Google Trends interest × CTvisit.com co-op presence × DMO coverage.)
3. **The closest-affluent-town fallacy.** A five-attraction comparison testing whether the highest-ranked source town actually wins on persona fit, or whether proximity is doing more work than it should.

Posts will appear on a roughly monthly cadence. Each cites raw data, summary stats, and methodology, and is reproducible from the code in this repo.

---

## Contributing

Issues and pull requests welcome. Particularly useful contributions:

- Additional public CT data sources that fit the spine (no paid feeds, no proprietary visitor data)
- Methodology critiques with worked counter-examples
- Frontend improvements that help readers slice the data more usefully
- Documentation fixes

For substantial methodology changes — new clustering features, weight adjustments, archetype renaming — open an issue first. The taxonomy is referenced by name in published posts, so changes have downstream cost.

---

## Sources and acknowledgments

Built on data maintained by:

- [US Census Bureau](https://www.census.gov/) — American Community Survey 5-year estimates
- [Census LEHD](https://lehd.ces.census.gov/) — LODES Origin-Destination employment statistics
- [CTData Collaborative](https://www.ctdata.org/) — Connecticut's State Data Center
- [CT Open Data Portal](https://data.ct.gov/) — powered by Socrata / Tyler Technologies
- [CT Secretary of the State](https://portal.ct.gov/SOTS) — Business Registry

All data is public domain. This project does not collect or store any personally identifiable information.

---

## License

MIT.

---

## A note on the work

The methodology is in the open because public-data analysis is more valuable when it can be audited, extended, and built upon. The repo, the API, and the published posts are all free to use, fork, and critique. Methodology challenges, additional data sources, and use cases from people working in CT tourism are welcome — open an issue or reach out directly.
