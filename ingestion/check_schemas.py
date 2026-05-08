"""
Quick schema check across all registered CTData datasets.
Run from project root: python -m ingestion.check_schemas
Prints the real filter values for each dataset so datasets.yaml can be set correctly.
"""
import sys, logging
sys.path.insert(0, '.')
logging.basicConfig(level=logging.WARNING)  # suppress info during schema check

import requests
import pandas as pd
from io import StringIO
import yaml
from pathlib import Path

BASE_URL      = "http://data.ctdata.org"
RESOURCE_SHOW = f"{BASE_URL}/api/3/action/resource_show"

def get_url(rid):
    try:
        r = requests.get(RESOURCE_SHOW, params={"id": rid}, timeout=20)
        return r.json()["result"]["url"]
    except:
        return None

def get_df(url):
    try:
        r = requests.get(url, timeout=30)
        return pd.read_csv(StringIO(r.text), engine='python', on_bad_lines='skip')
    except:
        return pd.DataFrame()

registry = yaml.safe_load(open("ingestion/datasets.yaml"))
datasets = [d for d in registry["datasets"] if d.get("source") == "ctdata_ckan"]

print(f"{'Dataset':<45} {'Measure Type':<35} {'Variable (first 2)':<50} {'Gender':<20} {'Race/Ethnicity'}")
print("-" * 180)

for d in datasets:
    rid = d["resource_id"]
    url = get_url(rid)
    if not url:
        print(f"{d['name']:<45} URL FAILED")
        continue
    df = get_df(url)
    if df.empty:
        print(f"{d['name']:<45} DOWNLOAD FAILED")
        continue

    mt  = str(df["Measure Type"].unique().tolist())[:33] if "Measure Type" in df.columns else "—"
    var = str(df["Variable"].unique().tolist()[:2])[:48] if "Variable" in df.columns else "—"
    gen = str(df["Gender"].unique().tolist())[:18] if "Gender" in df.columns else "—"
    rac = str(df["Race/Ethnicity"].unique().tolist()[:3])[:40] if "Race/Ethnicity" in df.columns else "—"

    print(f"{d['name']:<45} {mt:<35} {var:<50} {gen:<20} {rac}")
