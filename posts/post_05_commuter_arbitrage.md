# Post #5 — Commuter Arbitrage: The Hidden Visitor Markets in CT's Commuter Belt

*Part of the CT Town Personas data spine. Analysis notebook: `post_05_commuter_arbitrage.ipynb`.*

---

## The Insight

Connecticut's four major economic anchors — Hartford, New Haven, Stamford, and Bridgeport — draw tens of thousands of workers every weekday from surrounding towns. Those commuters don't live in the anchor city. They live in high-income, high-education suburban towns with shorter drive times to those anchors than most destination marketers realize.

This is the arbitrage: **attractions market to visitors by proximity to *them*, but the highest-value potential audiences are the commuter towns that already have established travel patterns toward the region.**

A Hartford-area attraction shouldn't just think about who lives within 45 minutes — it should think about who *travels through the region* every day and might redirect that motion on a weekend.

---

## What the Data Shows

Using LODES 2021 origin-destination flow data (Census LEHD), we can count exactly how many workers commute from each CT town into each of the four anchors.

### Top Commuter-Belt Towns by Anchor

**Hartford corridor** (inbound_to_hartford):

| Town | Inbound Workers | Median HH Income |
|------|----------------|-----------------|
| West Hartford | 6,412 | $123,077 |
| Manchester | 4,451 | ~$72,000 |
| East Hartford | 4,164 | ~$60,000 |
| New Britain | 3,187 | ~$50,000 |
| Glastonbury | ~1,800 | ~$118,000 |

**New Haven corridor** (inbound_to_new_haven):

| Town | Inbound Workers | Median HH Income |
|------|----------------|-----------------|
| Hamden | 7,739 | ~$77,000 |
| West Haven | 4,433 | ~$62,000 |
| Milford | 2,738 | ~$80,000 |
| Wallingford | 2,539 | ~$85,000 |
| East Haven | 2,982 | ~$66,000 |

**Stamford corridor** (inbound_to_stamford):

| Town | Inbound Workers | Median HH Income |
|------|----------------|-----------------|
| Norwalk | 5,929 | ~$95,000 |
| Fairfield | 2,429 | ~$135,000 |
| Trumbull | 1,412 | ~$114,000 |
| Shelton | 871 | ~$87,000 |
| Stratford | 1,348 | ~$71,000 |

**Bridgeport corridor** (inbound_to_bridgeport):

| Town | Inbound Workers | Median HH Income |
|------|----------------|-----------------|
| Stratford | 3,209 | ~$71,000 |
| Trumbull | 1,617 | ~$114,000 |
| Shelton | 1,774 | ~$87,000 |
| Fairfield | 1,595 | ~$135,000 |
| Milford | 1,682 | ~$80,000 |

---

## The Arbitrage Frame

**Standard marketing logic**: Target towns within X miles of an attraction.

**Commuter arbitrage logic**: Target towns whose residents already *travel toward your attraction's region* every weekday — they've already internalized the drive, they just haven't redirected it on weekends yet.

The highest-value arbitrage candidates share three traits:
1. High total inbound commute flow into one or more anchor cities
2. Above-median household income (disposable leisure budget)
3. Drive time to the attraction falls in the Day-Tripper band (≤90 min)

Towns like **West Hartford** (6,400 Hartford commuters, $123K median income, walkable retail district), **Fairfield** (2,400+ Stamford/Bridgeport commuters, $135K income), and **Hamden** (7,700 New Haven commuters, suburban families) sit at this intersection.

---

## Behavioral Implications

Because these towns sit in the Day-Tripper band (≤90 min) for their respective anchor-region attractions, the right activation is **low-friction, repeatable experiences** — not the "big trip" framing that works for tourists arriving from New York or Boston.

| Behavior Segment | Drive Band | Right Message |
|-----------------|------------|---------------|
| Local Repeat Visitor | ≤20 min | Membership, loyalty, off-peak access |
| Day-Tripper | 20–90 min | Saturday itinerary, add-on dining |
| Weekender | 90–180 min | Overnight + bundled experience |

Commuter-belt towns are almost exclusively Day-Tripper territory. That means high visit frequency, lower per-visit spend, but strong word-of-mouth and membership conversion potential.

---

## What This Means for CT Attractions

1. **Audience segmentation should start from commute flows, not rings.** A 30-mile radius around Hartford captures very different income and employment profiles than the actual top-10 Hartford inbound towns.

2. **The income gradient matters.** West Hartford and Glastonbury feed Hartford's workforce *and* carry household incomes north of $110K — that's a different audience than East Hartford or New Britain commuters who also feed Hartford but at lower income levels.

3. **Cross-anchor towns are the highest-value targets.** Towns like Stratford (3,209 Bridgeport + 1,348 Stamford + 1,454 New Haven inbound) or Trumbull (1,617 Bridgeport + 1,412 Stamford) are embedded in multiple commuter corridors — familiar with multi-directional travel in the region.

---

## Data Notes

- LODES data is from 2021 (most recent available LODES8 vintage at time of analysis)
- Income figures from ACS 5-year estimates (2019–2023 vintage, CTData)
- Commute flows count all jobs (LODES JT00), not just primary jobs
- Self-commute (Hartford → Hartford) excluded from arbitrage analysis
- Full methodology in `ingestion/lodes_client.py`
