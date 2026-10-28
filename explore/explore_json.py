"""Download SMARD data from the API as JSON, save it unchanged, and explore it.

Run from the project folder:
    python explore/explore_json.py

Needs: pip install requests
"""

import json
from pathlib import Path

import pandas as pd
import requests

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 10)

PROJECT_DIR = Path(__file__).resolve().parent.parent
JSON_DIR = PROJECT_DIR / "data" / "raw" / "api_json"

# --- Settings: change these to explore other data -------------------------
BASE_URL = "https://www.smard.de/app/chart_data"
REGION = "50Hertz"
RESOLUTION = "quarterhour"
FILTERS = {"grid_load": 410, "residual_load": 4359}   # SMARD filter IDs
START = pd.Timestamp("2026-09-01", tz="Europe/Berlin")  # same month as your CSV
END = pd.Timestamp("2026-10-01", tz="Europe/Berlin")    # day after the last day
DOWNLOAD = True   # set to False to explore files you already saved
# ---------------------------------------------------------------------------


def download(name: str, filter_id: int) -> None:
    """Ask the API which blocks exist, download those for START-END, save them unchanged."""
    # Step 1: the index lists the start of each data block (milliseconds since 1970, UTC)
    index_url = f"{BASE_URL}/{filter_id}/{REGION}/index_{RESOLUTION}.json"
    timestamps = requests.get(index_url, timeout=30).json()["timestamps"]
    print(f"{name}: {len(timestamps)} blocks available in total")

    # Step 2: keep blocks that can contain our period (a block covers about one week)
    first = (START - pd.Timedelta(days=8)).timestamp() * 1000
    last = END.timestamp() * 1000
    wanted = [t for t in timestamps if first <= t < last]

    # Step 3: download each block and save the JSON exactly as received
    folder = JSON_DIR / name
    folder.mkdir(parents=True, exist_ok=True)
    for t in wanted:
        url = f"{BASE_URL}/{filter_id}/{REGION}/{filter_id}_{REGION}_{RESOLUTION}_{t}.json"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        path = folder / f"{filter_id}_{REGION}_{RESOLUTION}_{t}.json"
        path.write_text(response.text, encoding="utf-8")
        print("  saved", path.name)


def explore(name: str) -> pd.DataFrame:
    print("\n" + "=" * 70)
    print(name, "(JSON from the API)")
    print("=" * 70)

    files = sorted((JSON_DIR / name).glob("*.json"))

    # 1. Structure of one file: which keys, what does an entry look like?
    data = json.loads(files[0].read_text(encoding="utf-8"))
    print("\n1. Structure of one file")
    print("Top-level keys:", list(data.keys()))
    print("meta_data:", data.get("meta_data"))
    print("First entries of 'series':", data["series"][:3])

    # 2. Read all files: each entry is [timestamp_ms, value]
    pairs = []
    for f in files:
        pairs.extend(json.loads(f.read_text(encoding="utf-8"))["series"])
    df = pd.DataFrame(pairs, columns=["ts_ms", "value"])
    print("\n2. All files:", len(files), "files,", len(df), "entries")

    # 3. Timestamps: milliseconds (UTC) -> readable time; also German local time
    df["ts_utc"] = pd.to_datetime(df["ts_ms"], unit="ms", utc=True)
    df["ts_local"] = df["ts_utc"].dt.tz_convert("Europe/Berlin")

    # 4. Keep only our period (blocks are whole weeks, so they reach beyond it)
    df = df[(df["ts_local"] >= START) & (df["ts_local"] < END)].set_index("ts_local")
    print("\n3. Our period:", df.index.min(), "to", df.index.max(), "-", len(df), "quarter hours")

    # 5. Duplicates: neighbouring blocks can share a timestamp at their edges.
    #    Keep the entry that has a value; drop the empty copy.
    print("\n4. Time steps")
    print("Duplicate timestamps:", df.index.duplicated().sum())
    df = (df.reset_index()
            .sort_values(["ts_local", "value"], na_position="first")
            .drop_duplicates("ts_local", keep="last")
            .set_index("ts_local"))
    print("After removing duplicates:", len(df), "quarter hours")
    print(df.index.to_series().diff().value_counts())

    # 6. Missing values: the API sends null (None in Python) instead of "-"
    print("\n5. Missing values:", df["value"].isna().sum())
    print(df[df["value"].isna()])

    # 7. Statistics
    print("\n6. Statistics (MWh per quarter hour)")
    print(df["value"].describe().round(1))
    return df


if __name__ == "__main__":
    for name, filter_id in FILTERS.items():
        if DOWNLOAD:
            download(name, filter_id)
        explore(name)