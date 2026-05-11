# CLAUDE.md — ct-town-personas

Persistent context for Claude Code. Read fully before non-trivial work. Conflicts with in-the-moment user instructions: ask, don't silently override.

For project narrative, README.md is canonical. This file is for working rules.

---

## What this is

A public, open-source data product producing town-level decision intelligence for Connecticut. Built on ACS, LODES, Census TIGER, CT Open Data (Socrata), and Google Trends. Lead use case is **CT tourism** — source-market analysis, persona modeling, and accessibility scoring for cultural attractions, DMOs, and the CT Office of Tourism. Healthcare marketing and state economic development are adjacent use cases preserved as optionality, not built now.

The strategy is **build in public**. Posts (1000-word analytical pieces, ~monthly) are the product surface. The repo + API + frontend are the credibility layer and the "go play with the data" lever. There is no paid SaaS, no marketplace, no booking platform.

---

## Repo map

```
ingestion/       Socrata + Census + LODES + TIGER + Google Trends clients
pipeline/        Feature engineering, clustering, persona, forecast, anchors
api/             FastAPI app, routers for towns/personas/forecast/anchors
frontend/        React/Vite — town selector, anchor selector, persona viewer
data/            raw/ and processed/ — gitignored Parquet outputs
posts/           Markdown drafts for each published analytical post
.github/workflows/  Monthly automated pipeline refresh
```

New modules being added (from the now-archived ct-tourism-intelligence work, ported in):
- `ingestion/lodes_client.py` — LODES OD flows for Hartford, New Haven, Stamford, Bridgeport
- `ingestion/tiger_client.py` — block centroids for drive-time
- `ingestion/trends_client.py` — Google Trends via pytrends, DMA-level
- `pipeline/drive_time.py` — haversine × road factor, configurable
- `pipeline/anchors.py` — attraction config + opportunity scoring
- `pipeline/behavior_overlay.py` — Day-Tripper / Weekender / Local Repeat assignment

---

## Build & run

```
make install         # Python + npm deps
make discover        # Resolve Socrata resource IDs (run when datasets.yaml has placeholders)
make pipeline        # End-to-end: ingest → features → cluster → personas → forecast
make api             # FastAPI on :8000
make frontend        # Vite on :5173
make dev             # Both
```

Pipeline is monthly via `.github/workflows/pipeline.yml`. **Do not change to daily** — ACS is annual, LODES is annual, Socrata feeds are mostly monthly. Daily wastes compute and creates editorial drift across posts.

---

## Locked architectural decisions

These are settled; do not re-litigate without explicit user instruction.

1. **Foundation is `ct-town-personas`** — the (now-private) `ct-tourism-intelligence` repo is reference-only; port logic, do not depend on it.
2. **Clustering: KMeans + GMM** for soft persona assignment. Five archetypes, locked names: `Affluent Suburban`, `Working-Class Urban`, `Rural/Small Town`, `Young Professional`, `Mixed-Income Transitional`. **Do not rename** — they are referenced by name in published posts.
3. **Race/ethnicity composition is a descriptor, not a clustering feature.** Clusters are trained on income, education, age, household, business, housing, commute features. Each persona output **must** include the racial/ethnic composition of the cluster centroid (% non-Hispanic white, Black, Hispanic/Latino, Asian, multiracial). This keeps personas from defaulting to majority-population characteristics without essentializing race into the labels themselves.
4. **Scoring: 60% demographic, 40% accessibility.** Accessibility = 70% drive-band tier, 15% within-band proximity, 15% LODES inbound flow. These weights are public methodology and stable across posts.
5. **Anchor concept:** an attraction is `(name, lat, lng, persona_weights, behavior_profile)`. Opportunity scoring is `f(town_features, anchor)`. The Science Center is one anchor among many — do not hardcode it.
6. **Refresh cadence: monthly.** Show a "Data last refreshed: YYYY-MM-DD" indicator in the frontend.
7. **License: MIT, fully public from now on.** No private code paths.

---

## Out of scope (do not build, do not propose)

- Real-time data of any kind (mobility, transactions, weather, event)
- Daily or sub-monthly refresh
- A booking platform or three-sided marketplace
- Any product depending on private bus-company data (e.g. Dattco quote feeds)
- Pricing-elasticity, sentiment analysis, ad-spend attribution, CRM integration
- LLM-generated narrative copy in API responses (rule-based templates only; LLM enrichment is a separate, manual post-authoring step)
- Live dashboards beyond what the existing FastAPI + React layer provides
- Methodology changes that would break already-published posts

If a request points toward any of the above, ask the user before proceeding.

---

## Data spine

| Source | Vintage | Used for |
|---|---|---|
| ACS 5-year | 2022 | Demographics, income, education, race composition, household |
| LODES OD | 2021 | Inbound commute flows to Hartford / New Haven / Stamford / Bridgeport |
| TIGER block centroids | 2020 | Drive-time origins |
| CT SOTS Business Master + Filings | Monthly | Business density, formation velocity |
| CT Education Attendance | Annual | District-level signals (post #4 use case) |
| Population Projections | Periodic | Prophet forecasting inputs |
| Google Trends (pytrends) | Weekly pull, DMA-level | Marketing intensity proxy (post #3) |

**Data caveats Claude should never let slide:**
- Town suppression: ~162/169 towns survive Census privacy thresholds. Note in any output.
- Google Trends is DMA-level, not town-level. Post #3 framing must respect this.
- LODES has a 2-year publication lag. Always cite the data vintage.
- Race composition has small-population reliability issues; surface margin of error where possible.

---

## Active post pipeline

In priority order. The architecture should support these in this sequence:

1. **Post #5 — Commuter arbitrage** (LODES-driven). Requires: anchor concept, LODES flows for 4 cities, multi-anchor support in API.
2. **Post #3 — Under-marketed CT submarkets** (Trends + opportunity scoring). Requires: trends_client, marketing intensity layer, opportunity-vs-intensity comparison view.
3. **Post #1 — Closest-affluent-town fallacy** (multi-attraction comparison). Requires: 5+ configured anchors, persona-weighted scoring.
4. Future posts in `posts/` directory; each gets a markdown draft + a notebook that's reproducible from `data/processed/`.

Every post must cite raw data vintage, summary stats, and methodology. Reproducible from public data only.

---

## Editorial guardrails (apply to any output that feeds a post)

- Race/ethnicity composition is surfaced as descriptive context, not as a marketing-targeting axis. Do not generate copy that suggests targeting communities by race.
- When persona output references a specific community (e.g. "Hispanic working-class") it must include within-group heterogeneity caveats and the data's limits.
- Methodological choices (drive-band cutoffs, weight splits, cluster k) are named explicitly in any post; alternatives the user could have chosen are acknowledged.
- Do not generate marketing copy that names specific towns as "underperforming" without paired methodological caveats.

---

## Ask before acting

Before doing any of these, surface to user and wait:
- Adding a new data source not in the spine table above
- Changing locked archetype names, scoring weights, or refresh cadence
- Renaming or restructuring modules in `pipeline/` or `api/`
- Anything that would require backfilling already-published post data
- Methodology changes that would shift town rankings by more than ~10%

Routine work (bug fixes, new endpoints that compose existing data, frontend polish, test additions, README updates) — proceed without asking.

---

## Conventions Claude can't infer

- Parquet, not CSV, for all `data/processed/` outputs.
- Town names are the canonical join key. Normalize on ingest (title case, strip whitespace, handle "Borough of X" edge cases).
- ACS suppression returns NaN, not 0. Never `.fillna(0)` on demographic features.
- All new modules need a docstring describing the post(s) they serve.
- Test the API endpoints with `pytest` against known towns (Westport → Affluent Suburban, Hartford → Working-Class Urban) — this catches cluster-shuffle bugs.
