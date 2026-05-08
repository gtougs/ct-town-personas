"""
discover.py
Run this ONCE to find the real resource IDs for every CTData dataset.
Outputs a ready-to-paste YAML block for datasets.yaml.

Usage:
    python -m ingestion.discover
    python -m ingestion.discover --slugs median-household-income-by-town major-employers

The output shows each dataset slug → resource_id → column names and sample row,
so you can verify what fields to use before wiring them into the pipeline.
"""

import sys
import json
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.ctdata_client import CTDataClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger("discover")

# Datasets we care about — these slugs come from the dataset page URLs at data.ctdata.org
TARGET_SLUGS = [
    "median-household-income-by-town",
    "per-capita-income-by-town",
    "population-by-race-by-town",
    "population-by-age-by-town",
    "dph-annual-population-estimates-by-town",
    "median-home-value-by-town",
    "median-rent-by-town",
    "total-housing-units-by-town",
    "housing-tenure-by-race-and-ethnicity-by-town",
    "educational-attainment",
    "poverty-status-by-town",
    "labor-force",
    "cost-burdened-households-by-town",
    "major-employers",
    "self-employment-by-business-type-by-town",
]


def discover(slugs: list[str], sample_rows: int = 2):
    client = CTDataClient()

    print("\n" + "=" * 70)
    print("CTData CKAN — Resource ID Discovery")
    print("=" * 70)

    yaml_lines = []
    errors = []

    for slug in slugs:
        print(f"\n── {slug}")
        try:
            pkg = client.describe_package(slug)
            title = pkg.get("title", slug)
            notes = (pkg.get("notes") or "")[:100].replace("\n", " ")

            resources = pkg.get("resources", [])
            if not resources:
                print(f"  ⚠ No resources found")
                errors.append(slug)
                continue

            # Prefer datastore-active resources
            active = [r for r in resources if r.get("datastore_active")]
            res = active[0] if active else resources[0]
            rid = res.get("id", "UNKNOWN")

            print(f"  Title:       {title}")
            print(f"  Resource ID: {rid}")
            print(f"  Format:      {res.get('format', '?')}")

            # Fetch a sample to show columns and data shape
            if rid != "UNKNOWN":
                try:
                    df = client.fetch(rid, limit=sample_rows)
                    if not df.empty:
                        print(f"  Columns:     {list(df.columns)}")
                        print(f"  Sample:")
                        for _, row in df.iterrows():
                            print(f"    {dict(row)}")

                        # Detect Town and Year columns
                        town_col = next((c for c in df.columns if "town" in c.lower()), None)
                        year_col = next((c for c in df.columns if "year" in c.lower()), None)
                        value_cols = [c for c in df.columns
                                      if c.lower() not in ("town", "year", "fips", "county",
                                                           "race", "race/ethnicity", "gender",
                                                           "measure type", "variable")]
                        print(f"  Town col:    {town_col}")
                        print(f"  Year col:    {year_col}")
                        print(f"  Value cols:  {value_cols}")
                except Exception as e:
                    print(f"  ⚠ Could not fetch sample: {e}")

            # Build YAML entry
            yaml_lines.append(f"""
  - name: {slug.replace("-", "_")}
    id: {rid}
    source: ctdata_ckan
    domain: # TODO: fill in
    frequency: annual
    geo_field: Town   # verify from columns above
    year_field: Year  # verify from columns above
    description: {title}""")

        except Exception as e:
            print(f"  ✗ Error: {e}")
            errors.append(slug)

        import time
        time.sleep(0.5)  # polite delay

    print("\n" + "=" * 70)
    print("YAML entries to add to ingestion/datasets.yaml:")
    print("=" * 70)
    for block in yaml_lines:
        print(block)

    if errors:
        print(f"\n⚠ Failed slugs: {errors}")
        print("  Check that these slugs match the URL at data.ctdata.org/dataset/SLUG")

    print("\n" + "=" * 70)
    print("Next steps:")
    print("  1. Copy the YAML entries above into ingestion/datasets.yaml")
    print("  2. Fill in the 'domain' field for each dataset")
    print("  3. Verify 'geo_field' and 'year_field' match the actual column names")
    print("  4. Run: python -m ingestion.validate")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Discover CTData resource IDs")
    parser.add_argument(
        "--slugs", nargs="*", default=None,
        help="Specific dataset slugs to discover (default: all target slugs)"
    )
    parser.add_argument(
        "--sample", type=int, default=2,
        help="Number of sample rows to fetch per dataset (default: 2)"
    )
    args = parser.parse_args()

    slugs = args.slugs or TARGET_SLUGS
    discover(slugs, sample_rows=args.sample)
