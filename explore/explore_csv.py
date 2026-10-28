"""Explore the SMARD CSV files (actual and forecasted consumption).

Run from the project folder:
    python explore/explore_csv.py
"""

from pathlib import Path

import pandas as pd

# Show all columns when printing tables
pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 10)

# Folder with the CSV files, found relative to this script
PROJECT_DIR = Path(__file__).resolve().parent.parent
CSV_DIR = PROJECT_DIR / "data" / "raw" / "csv"


def read_smard_csv(path: Path) -> pd.DataFrame:
    """Read one SMARD CSV file into a table indexed by time."""
    # Step 1: read the text file into a table
    df = pd.read_csv(
        path,
        sep=";",               # SMARD separates columns with ;
        encoding="utf-8-sig",  # the file starts with an invisible BOM character
        thousands=",",         # 2,258.63 -> 2258.63
        na_values="-",         # "-" means missing
    )

    # Step 2: turn the date text into real timestamps
    # "Sep 1, 2026 12:00 AM" -> 2026-09-01 00:00
    df["start"] = pd.to_datetime(df["Start date"], format="%b %d, %Y %I:%M %p")

    # Step 3: time becomes the index; "End date" is always start + 15 min
    df = df.drop(columns=["Start date", "End date"]).set_index("start")

    # Step 4: short column names, e.g. "grid load [MWh] Original resolutions" -> "grid_load"
    df.columns = [
        c.replace(" [MWh] Original resolutions", "").lower().replace(".", "").replace(" ", "_")
        for c in df.columns
    ]
    return df


def explore(name: str, df: pd.DataFrame) -> None:
    """Print the basic facts every time series needs checking for."""
    print("\n" + "=" * 70)
    print(name)
    print("=" * 70)

    # 1. Structure: how many rows and columns, which data types?
    print("\n1. Structure")
    print("Rows, columns:", df.shape)
    print(df.dtypes)
    print(df.head(3))

    # 2. Period: first and last quarter hour
    print("\n2. Period")
    print("From", df.index.min(), "to", df.index.max())

    # 3. Regular interval: the gap between two rows should always be 15 minutes
    print("\n3. Time steps (gap between rows -> how often)")
    print(df.index.to_series().diff().value_counts())
    print("Duplicate timestamps:", df.index.duplicated().sum())
    rows_per_day = df.groupby(df.index.date).size()
    print("Quarter hours per day -> number of days:", rows_per_day.value_counts().to_dict())

    # 4. Missing values: how many, and where?
    print("\n4. Missing values")
    print(df.isna().sum())
    print(df[df.isna().any(axis=1)])

    # 5. Value ranges
    print("\n5. Statistics (MWh per quarter hour)")
    print(df.describe().round(1))

    # 6. Daily pattern: average per hour of the day
    print("\n6. Average per hour of the day")
    print(df.groupby(df.index.hour).mean().round(0))


def compare(actual: pd.DataFrame, forecast: pd.DataFrame) -> None:
    """Put actual and forecast side by side for the quarter hours both have."""
    print("\n" + "=" * 70)
    print("Actual vs. forecast: grid load")
    print("=" * 70)

    # Rename first so both columns have different names, then join on time
    both = actual[["grid_load"]].rename(columns={"grid_load": "grid_load_actual"}).join(
        forecast[["grid_load"]].rename(columns={"grid_load": "grid_load_forecast"}),
        how="inner",  # keep only quarter hours that exist in both
    )
    both["error"] = both["grid_load_forecast"] - both["grid_load_actual"]

    print("Quarter hours in both files:", len(both))
    print("Mean error (bias):", round(both["error"].mean(), 1), "MWh")
    print("Mean absolute error:", round(both["error"].abs().mean(), 1), "MWh")
    print("Largest miss:", round(both["error"].abs().max(), 1), "MWh at",
          both["error"].abs().idxmax())
    print("\nMean absolute error per hour of the day:")
    print(both["error"].abs().groupby(both.index.hour).mean().round(0))


if __name__ == "__main__":
    actual = read_smard_csv(next(CSV_DIR.glob("Actual_consumption_*.csv")))
    forecast = read_smard_csv(next(CSV_DIR.glob("Forecasted_consumption_*.csv")))

    explore("ACTUAL consumption (CSV)", actual)
    explore("FORECASTED consumption (CSV)", forecast)
    compare(actual, forecast)