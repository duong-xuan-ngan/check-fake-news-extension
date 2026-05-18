"""One-time conversion: MBFC raw CSV -> domain -> credibility score JSON.

Run once after placing mbfc_raw.csv in data/. Produces data/mbfc_credibility.json
which credibility_filter.py loads at import time.

When DE delivers their Postgres /credibility endpoint, this script and the
generated JSON can be deleted, and credibility_filter.py switches to the API.
"""
import json
import re
from pathlib import Path

import pandas as pd

# factual_reporting label -> credibility score
# High = source consistently fact-checks and corrects. Low = known for misinformation.
SCORE_MAP = {
    "high": 0.9,
    "mostly factual": 0.75,  # MBFC sometimes uses this label
    "mixed": 0.5,
    "low": 0.1,
    "very low": 0.05,
}


def clean_domain(source: str) -> str:
    """Normalize 'https://www.bbc.com/' -> 'bbc.com'. Match searcher.py's output."""
    source = str(source).strip().lower()
    source = re.sub(r"^https?://", "", source)
    source = re.sub(r"^www\.", "", source)
    return source.rstrip("/").split("/")[0]


def main():
    project_root = Path(__file__).resolve().parent.parent
    csv_path = project_root / "data" / "mbfc_raw.csv"
    out_path = project_root / "data" / "mbfc_credibility.json"

    print(f"Loading {csv_path}")
    df = pd.read_csv(csv_path)
    print(f"  {len(df)} rows, columns: {list(df.columns)}")

    df["domain"] = df["source"].apply(clean_domain)
    df["score"] = df["factual_reporting"].astype(str).str.lower().str.strip().map(SCORE_MAP)

    unmapped = df[df["score"].isna()]["factual_reporting"].value_counts()
    if len(unmapped) > 0:
        print(f"  WARNING: dropped {unmapped.sum()} rows with unmapped labels:")
        for label, count in unmapped.items():
            print(f"    {label!r}: {count}")

    df = df.dropna(subset=["score"])
    df = df.drop_duplicates(subset=["domain"], keep="first")

    result = dict(zip(df["domain"], df["score"]))
    out_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote {len(result)} domains to {out_path}")


if __name__ == "__main__":
    main()
