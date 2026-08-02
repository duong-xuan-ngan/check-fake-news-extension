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


CRED1_VERSION = "v2026-07-28"
CRED1_CATEGORIES = {
    "c": "Conspiracy",
    "f": "Fake",
    "m": "Mixed",
    "r": "Reliable",
    "s": "Satire",
    "u": "Unreliable",
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
vn_rows = [
    (d, s, c, country, "manual", 1, "local-v1", today)
    for d, s, c, country in VN_DOMAINS
]

execute_values(cur, """
    INSERT INTO sources
        (domain, credibility_score, category, country, rating_source,
         source_count, source_version, last_updated)
    VALUES %s
    ON CONFLICT (domain) DO UPDATE SET
        credibility_score = EXCLUDED.credibility_score,
        category          = EXCLUDED.category,
        country           = EXCLUDED.country,
        rating_source     = EXCLUDED.rating_source,
        source_count      = EXCLUDED.source_count,
        source_version    = EXCLUDED.source_version,
        last_updated      = EXCLUDED.last_updated
""", vn_rows)
print(f"[seed] Inserted/updated {len(vn_rows)} Vietnamese domains.")

# ── 2. CRED-1 negative-signal domains ─────────────────────────
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CRED1_PATH = DATA_DIR / "cred1_compact.json"

if CRED1_PATH.exists():
    raw_domains = json.loads(CRED1_PATH.read_text(encoding="utf-8"))
    cred1_rows = []
    for raw_domain, metadata in raw_domains.items():
        domain = clean_domain(raw_domain)
        category_code = str(metadata.get("c", ""))
        score = metadata.get("s")
        source_count = metadata.get("n")
        if not domain or category_code not in CRED1_CATEGORIES or score is None:
            continue
        cred1_rows.append((
            domain,
            float(score),
            f"CRED-1 / {CRED1_CATEGORIES[category_code]}",
            "unknown",
            "CRED-1",
            int(source_count) if source_count is not None else None,
            CRED1_VERSION,
            today,
        ))

    # The previous MBFC-only import is intentionally retired. Manually curated
    # rows are preserved because they use their own category and rating source.
    cur.execute("DELETE FROM sources WHERE category = 'MBFC'")
    retired_mbfc_count = cur.rowcount

    execute_values(cur, """
        INSERT INTO sources
            (domain, credibility_score, category, country, rating_source,
             source_count, source_version, last_updated)
        VALUES %s
        ON CONFLICT (domain) DO UPDATE SET
            credibility_score = EXCLUDED.credibility_score,
            category          = EXCLUDED.category,
            country           = EXCLUDED.country,
            rating_source     = EXCLUDED.rating_source,
            source_count      = EXCLUDED.source_count,
            source_version    = EXCLUDED.source_version,
            last_updated      = EXCLUDED.last_updated
        WHERE sources.rating_source = 'CRED-1'
           OR sources.category = 'MBFC'
    """, cred1_rows)
    print(
        f"[seed] Inserted/updated {len(cred1_rows)} CRED-1 domains "
        f"and retired {retired_mbfc_count} MBFC-only rows."
    )
else:
    print(f"[seed] Missing CRED-1 file, skipping import: {CRED1_PATH}")

conn.commit()
cur.close()
conn.close()
print("[seed] Done.")
