import csv
import json
import os
import re
from datetime import date
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

# ── Connection ────────────────────────────────────────────────
conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

# ── Helpers ───────────────────────────────────────────────────
def clean_domain(source: str) -> str:
    """Normalize a URL or source value to the domain format stored in Postgres."""
    domain = str(source or "").strip().lower()
    domain = re.sub(r"^https?://", "", domain)
    domain = re.sub(r"^www\.", "", domain)
    domain = domain.rstrip("/").split("/")[0]
    return "" if domain in {"", "nan", "none", "null"} else domain


def clean_country(country: str) -> str:
    """Normalize country values and remove MBFC press-freedom annotations."""
    value = str(country or "").strip().lower()
    value = re.sub(r"\s*\([^)]*press freedom[^)]*\)\s*$", "", value).strip()
    return value or "unknown"


# Used only for valid CSV domains that are absent from the generated JSON.
# JSON remains the authoritative source whenever it contains the domain.
FACTUAL_REPORTING_SCORES = {
    "very high": 0.95,
    "high": 0.9,
    "mostly factual": 0.75,
    "mixed": 0.5,
    "low": 0.1,
    "very low": 0.05,
}


# ── 1. Vietnamese domains (manual, you own these scores) ──────
VN_DOMAINS = [
    # (domain, credibility_score, category, country)
    ("vnexpress.net",    0.85, "National News", "vietnam"),
    ("tuoitre.vn",       0.85, "National News", "vietnam"),
    ("thanhnien.vn",     0.82, "National News", "vietnam"),
    ("dantri.com.vn",    0.78, "National News", "vietnam"),
    ("tienphong.vn",     0.76, "National News", "vietnam"),
    ("laodong.vn",       0.74, "National News", "vietnam"),
    ("vietnamnet.vn",    0.78, "National News", "vietnam"),
    ("zingnews.vn",      0.72, "National News", "vietnam"),
    ("kenh14.vn",        0.60, "Entertainment", "vietnam"),
    ("baomoi.com",       0.65, "Aggregator", "vietnam"),
    ("nhandan.vn",       0.75, "State Media", "vietnam"),
    ("nhandan.com.vn",   0.75, "State Media", "vietnam"),
    ("vtv.vn",           0.80, "State Broadcast", "vietnam"),
    ("vov.vn",           0.78, "State Broadcast", "vietnam"),
    ("baochinhphu.vn",   0.72, "Government", "vietnam"),
    ("qdnd.vn",          0.70, "State Media", "vietnam"),
    ("plo.vn",           0.74, "National News", "vietnam"),
    ("nld.com.vn",       0.74, "National News", "vietnam"),
    ("sggp.org.vn",      0.72, "National News", "vietnam"),
    ("baogiaothong.vn",  0.68, "Specialized", "vietnam"),
    ("anninhthudo.vn",   0.65, "Regional", "vietnam"),
    ("congan.com.vn",    0.65, "Regional", "vietnam"),
    ("tinhhoa.net",      0.20, "Low Credibility", "vietnam"),
    ("danviet.vn",       0.45, "Tabloid", "vietnam"),
    ("baodatviet.vn",    0.45, "Tabloid", "vietnam"),
]

today = date.today()
vn_rows = [(d, s, c, country, today) for d, s, c, country in VN_DOMAINS]

execute_values(cur, """
    INSERT INTO sources
        (domain, credibility_score, category, country, last_updated)
    VALUES %s
    ON CONFLICT (domain) DO UPDATE SET
        credibility_score = EXCLUDED.credibility_score,
        category          = EXCLUDED.category,
        country           = EXCLUDED.country,
        last_updated      = EXCLUDED.last_updated
""", vn_rows)
print(f"[seed] Inserted/updated {len(vn_rows)} Vietnamese domains.")

# ── 2. MBFC domains (JSON scores + CSV countries) ─────────────
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MBFC_JSON_PATH = DATA_DIR / "mbfc_credibility.json"
MBFC_CSV_PATH = DATA_DIR / "mbfc_raw.csv"

if MBFC_JSON_PATH.exists() and MBFC_CSV_PATH.exists():
    raw_scores = json.loads(MBFC_JSON_PATH.read_text(encoding="utf-8"))
    json_scores = {
        domain: float(score)
        for raw_domain, score in raw_scores.items()
        if (domain := clean_domain(raw_domain))
    }

    csv_by_domain = {}
    with MBFC_CSV_PATH.open(newline="", encoding="utf-8-sig") as csv_file:
        for row in csv.DictReader(csv_file):
            domain = clean_domain(row.get("source", ""))
            if domain and domain not in csv_by_domain:
                csv_by_domain[domain] = row

    mbfc_rows = []
    skipped_without_score = 0
    all_domains = sorted(set(json_scores) | set(csv_by_domain))
    for domain in all_domains:
        csv_row = csv_by_domain.get(domain, {})
        score = json_scores.get(domain)
        if score is None:
            factual_label = str(csv_row.get("factual_reporting", "")).strip().lower()
            score = FACTUAL_REPORTING_SCORES.get(factual_label)
        if score is None:
            skipped_without_score += 1
            continue

        country = clean_country(csv_row.get("country", "unknown"))
        mbfc_rows.append((domain, score, "MBFC", country, today))

    execute_values(cur, """
        INSERT INTO sources
            (domain, credibility_score, category, country, last_updated)
        VALUES %s
        ON CONFLICT (domain) DO UPDATE SET
            credibility_score = EXCLUDED.credibility_score,
            country           = EXCLUDED.country,
            last_updated      = EXCLUDED.last_updated
        WHERE sources.category = 'MBFC'
    """, mbfc_rows)
    # The WHERE clause updates previously seeded MBFC records while preserving
    # manually curated Vietnamese credibility scores and categories.
    print(
        f"[seed] Inserted/updated {len(mbfc_rows)} MBFC domains "
        f"(skipped {skipped_without_score} without a supported score)."
    )
else:
    missing = [
        str(path)
        for path in (MBFC_JSON_PATH, MBFC_CSV_PATH)
        if not path.exists()
    ]
    print(f"[seed] Missing MBFC file(s), skipping MBFC import: {missing}")

conn.commit()
cur.close()
conn.close()
print("[seed] Done.")
