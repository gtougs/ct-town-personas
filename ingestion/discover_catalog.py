"""
ingestion/discover_catalog.py

Run this BEFORE the main pipeline to discover real CTData resource IDs
and verify which datasets are queryable.

Usage:
    python -m ingestion.discover_catalog                  # full catalog
    python -m ingestion.discover_catalog --search age     # filter by keyword
    python -m ingestion.discover_catalog --peek <resource_id>  # preview rows
    python -m ingestion.discover_catalog --package median-age-by-town

Output:
    data/raw/ctdata_catalog.json   — full catalog snapshot for reference
    Prints a ready-to-paste datasets.yaml block for any queryable dataset
"""

import sys
import json
import logging
import argparse
import time
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

BASE_URL    = "http://data.ctdata.org"
SEARCH_URL  = f"{BASE_URL}/api/action/datastore_search"
PACKAGE_URL = f"{BASE_URL}/api/3/action/package_show"
LIST_URL    = f"{BASE_URL}/api/3/action/package_list"
RAW_DIR     = Path(__file__).parent.parent / "data" / "raw"

# Keywords that flag a dataset as relevant for our town-level persona project
RELEVANT_KEYWORDS = [
    "town", "age", "income", "population", "race", "education",
    "housing", "employment", "poverty", "household", "migration",
    "commute", "health", "business", "disability", "veteran",
]


def list_packages(session) -> list:
    resp = session.get(LIST_URL, timeout=30)
    resp.raise_for_status()
    return resp.json()["result"]


def describe_package(session, name: str) -> dict:
    resp = session.get(PACKAGE_URL, params={"id": name}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success"):
        return {}
    pkg = data["result"]
    return {
        "name": pkg["name"],
        "title": pkg.get("title", ""),
        "notes": (pkg.get("notes") or "")[:150].replace("\n", " "),
        "resources": [
            {
                "resource_id": r["id"],
                "name": r.get("name", ""),
                "format": r.get("format", ""),
                "datastore_active": r.get("datastore_active", False),
            }
            for r in pkg.get("resources", [])
        ],
    }


def peek_resource(session, resource_id: str, n: int = 3) -> dict:
    """Returns first n rows + field list from a resource."""
    resp = session.get(SEARCH_URL, params={"resource_id": resource_id, "limit": n}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success"):
        return {"error": data.get("error")}
    result = data["result"]
    return {
        "fields": [f["id"] for f in result.get("fields", [])],
        "total":  result.get("total", 0),
        "sample": result.get("records", [])[:n],
    }


def is_relevant(pkg: dict) -> bool:
    text = (pkg.get("title", "") + " " + pkg.get("notes", "")).lower()
    return any(kw in text for kw in RELEVANT_KEYWORDS)


def yaml_block(pkg: dict, resource: dict) -> str:
    """Generates a ready-to-paste datasets.yaml entry."""
    name_slug = pkg["name"].replace("-", "_")
    return f"""
  - name: {name_slug}
    resource_id: {resource['resource_id']}
    source: ctdata_ckan
    domain: # TODO: demographics | housing | economy | education | health | business | migration
    frequency: annual
    description: "{pkg['title']}"
    total_filters: {{}}   # TODO: fill in e.g. {{Race/Ethnicity: All, Gender: Total}}
    measure_filter: ""   # TODO: fill in e.g. "Number" or "Percent"
    canonical_variable: "" # TODO: the Variable value to use as the feature column name"""


def main():
    parser = argparse.ArgumentParser(description="Discover CTData CKAN catalog")
    parser.add_argument("--search",  help="Filter packages by keyword")
    parser.add_argument("--package", help="Show details for one package by name")
    parser.add_argument("--peek",    help="Preview rows from a resource_id")
    parser.add_argument("--all",     action="store_true", help="Show all packages (not just relevant)")
    parser.add_argument("--save",    action="store_true", help="Save catalog to data/raw/ctdata_catalog.json")
    args = parser.parse_args()

    session = requests.Session()
    session.headers.update({"User-Agent": "ct-town-personas/0.1"})

    # ── Peek mode ──────────────────────────────────────────────────────────────
    if args.peek:
        logger.info(f"\nPeeking at resource: {args.peek}\n{'─'*60}")
        info = peek_resource(session, args.peek, n=5)
        if "error" in info:
            logger.error(f"Error: {info['error']}")
            sys.exit(1)
        logger.info(f"Total rows : {info['total']:,}")
        logger.info(f"Fields     : {info['fields']}")
        logger.info(f"\nSample rows:")
        for row in info["sample"]:
            logger.info(f"  {json.dumps(row, default=str)}")
        sys.exit(0)

    # ── Single package mode ────────────────────────────────────────────────────
    if args.package:
        pkg = describe_package(session, args.package)
        if not pkg:
            logger.error(f"Package '{args.package}' not found")
            sys.exit(1)
        logger.info(f"\n{'='*60}")
        logger.info(f"Package: {pkg['name']}")
        logger.info(f"Title  : {pkg['title']}")
        logger.info(f"Notes  : {pkg['notes']}")
        logger.info(f"\nResources ({len(pkg['resources'])}):")
        for r in pkg["resources"]:
            active = "✓ queryable" if r["datastore_active"] else "✗ not in DataStore"
            logger.info(f"  [{active}] {r['resource_id']}  {r['name']} ({r['format']})")
            if r["datastore_active"]:
                info = peek_resource(session, r["resource_id"], n=2)
                logger.info(f"    Fields: {info.get('fields', [])}")
                logger.info(f"    Total rows: {info.get('total', 0):,}")
                logger.info(f"    Sample: {info.get('sample', [])[:1]}")
                logger.info(yaml_block(pkg, r))
        sys.exit(0)

    # ── Full catalog mode ──────────────────────────────────────────────────────
    logger.info(f"\nDiscovering CTData catalog at {BASE_URL} ...\n")

    all_packages = list_packages(session)
    logger.info(f"Total packages: {len(all_packages)}")

    if args.search:
        all_packages = [p for p in all_packages if args.search.lower() in p.lower()]
        logger.info(f"Filtered to '{args.search}': {len(all_packages)} packages\n")

    catalog = []
    queryable = []

    for i, name in enumerate(all_packages):
        try:
            pkg = describe_package(session, name)
            if not pkg:
                continue

            relevant = is_relevant(pkg) or args.all
            if not relevant and not args.search:
                continue

            # Check which resources are DataStore-queryable
            has_queryable = any(r["datastore_active"] for r in pkg["resources"])
            if not has_queryable:
                continue

            catalog.append(pkg)

            logger.info(f"[{i+1}/{len(all_packages)}] {pkg['title']}")
            for r in pkg["resources"]:
                if r["datastore_active"]:
                    logger.info(f"  resource_id: {r['resource_id']}  ({r['name']})")
                    queryable.append({"package": name, "title": pkg["title"], **r})

            time.sleep(0.1)  # gentle rate limiting

        except Exception as e:
            logger.warning(f"  Skipping '{name}': {e}")

    # ── Summary ────────────────────────────────────────────────────────────────
    logger.info(f"\n{'='*60}")
    logger.info(f"SUMMARY: {len(queryable)} queryable resources across {len(catalog)} relevant packages")
    logger.info(f"{'='*60}\n")

    logger.info("Ready-to-use resource IDs (copy into datasets.yaml):\n")
    for item in queryable:
        logger.info(f"  {item['resource_id']}  # {item['title']}")

    # ── Save ───────────────────────────────────────────────────────────────────
    if args.save or True:  # always save — useful reference
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        out_path = RAW_DIR / "ctdata_catalog.json"
        with open(out_path, "w") as f:
            json.dump({"packages": catalog, "queryable": queryable}, f, indent=2, default=str)
        logger.info(f"\nCatalog saved to: {out_path}")
        logger.info("Use this file to find resource IDs to add to ingestion/datasets.yaml")

    logger.info(f"""
Next steps:
  1. Pick resource IDs from the list above that match the indicators you need
  2. Peek at a resource to see its schema:
       python -m ingestion.discover_catalog --peek <resource_id>
  3. Add the dataset to ingestion/datasets.yaml under source: ctdata_ckan
  4. Re-run the pipeline: make pipeline
""")


if __name__ == "__main__":
    main()
