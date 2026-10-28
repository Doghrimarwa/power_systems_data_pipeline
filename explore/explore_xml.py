"""Explore the SMARD XML files with ElementTree.

Run from the project folder:
    python explore/explore_xml.py
"""

import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 10)

PROJECT_DIR = Path(__file__).resolve().parent.parent
XML_DIR = PROJECT_DIR / "data" / "raw" / "xml"


def print_tree(element: ET.Element, depth: int = 0, max_depth: int = 6) -> None:
    """Print the tree structure: each tag once, indented by level.

    Only the first child of each kind is followed, so the 2,880 values
    don't fill the screen.
    """
    if depth > max_depth:
        return
    text = (element.text or "").strip()
    print("  " * depth + element.tag + (f" = {text}" if text else ""))
    seen = set()
    for child in element:
        if child.tag not in seen:
            seen.add(child.tag)
            print_tree(child, depth + 1, max_depth)


def read_smard_xml(path: Path) -> pd.DataFrame:
    """Walk through the tree and collect one row per series and quarter hour."""
    root = ET.parse(path).getroot()

    rows = []
    # Each <Component> is one time series, e.g. "grid load"
    for component in root.iter("Component"):
        name = component.findtext("Component_name")
        unit = component.findtext("Unit")
        # Each <Value_detail> is one quarter hour
        for value in component.iter("Value_detail"):
            rows.append({
                "series": name,
                "unit": unit,
                "date": value.findtext("Date"),
                "time": value.findtext("Time_of_day"),
                "value": value.findtext("Value"),
            })

    df = pd.DataFrame(rows)

    # Everything in XML is text; convert it to real types
    df["start"] = pd.to_datetime(df["date"] + " " + df["time"], format="%b %d, %Y %I:%M %p")
    df["value"] = pd.to_numeric(df["value"].str.replace(",", ""), errors="coerce")  # "-" -> NaN
    return df[["start", "series", "unit", "value"]]


def explore(path: Path) -> pd.DataFrame:
    print("\n" + "=" * 70)
    print(path.name)
    print("=" * 70)

    root = ET.parse(path).getroot()

    # 1. Structure: what does the tree look like?
    print("\n1. Tree structure (first element of each kind)")
    print_tree(root)

    # 2. Header and category: period, data type, region
    print("\n2. Header and category")
    print("Period:", root.findtext("Header/Period/From"), "to", root.findtext("Header/Period/To"))
    print("Category:", root.findtext("Category/Category_name"))
    print("Region:", root.findtext("Category/Region"))

    # 3. Read all values into a long table (one row per series and quarter hour)
    df = read_smard_xml(path)
    print("\n3. Long table")
    print(df.head())
    print("Rows:", len(df))

    # 4. Per series: count, missing values, period
    print("\n4. Per series")
    summary = df.groupby("series").agg(
        values=("value", "size"),
        missing=("value", lambda s: s.isna().sum()),
        first=("start", "min"),
        last=("start", "max"),
        mean_mwh=("value", "mean"),
    )
    summary["mean_mwh"] = summary["mean_mwh"].round(1)
    print(summary)

    # 5. Timestamps outside the period in the header (SMARD adds an empty last one)
    period_end = pd.to_datetime(root.findtext("Header/Period/To"), format="%b %d, %Y %I:%M %p")
    outside = df[df["start"] >= period_end]
    print("\n5. Rows at or after the period end:", len(outside))
    print(outside)

    # 6. Wide table: one column per series, like the CSV
    wide = df[df["start"] < period_end].pivot(index="start", columns="series", values="value")
    print("\n6. Wide table (like the CSV)")
    print(wide.head())
    return wide


if __name__ == "__main__":
    for xml_file in sorted(XML_DIR.glob("*.xml")):
        explore(xml_file)