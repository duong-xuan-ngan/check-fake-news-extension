import json
import os
from datetime import date
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

# ── Connection ────────────────────────────────────────────────
conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

# ── 1. Vietnamese domains (manual, you own these scores) ──────
VN_DOMAINS = [
    # (domain, credibility_score, category)
    ("vnexpress.net",    0.85, "National News"),
    ("tuoitre.vn",       0.85, "National News"),
    ("thanhnien.vn",     0.82, "National News"),
    ("dantri.com.vn",    0.78, "National News"),
    ("tienphong.vn",     0.76, "National News"),
    ("laodong.vn",       0.74, "National News"),
    ("vietnamnet.vn",    0.78, "National News"),
    ("zingnews.vn",      0.72, "National News"),
    ("kenh14.vn",        0.60, "Entertainment"),
    ("baomoi.com",       0.65, "Aggregator"),
    ("nhandan.vn",       0.75, "State Media"),
    ("nhandan.com.vn",   0.75, "State Media"),
    ("vtv.vn",           0.80, "State Broadcast"),
    ("vov.vn",           0.78, "State Broadcast"),
    ("baochinhphu.vn",   0.72, "Government"),
    ("qdnd.vn",          0.70, "State Media"),
    ("plo.vn",           0.74, "National News"),
    ("nld.com.vn",       0.74, "National News"),
    ("sggp.org.vn",      0.72, "National News"),
    ("baogiaothong.vn",  0.68, "Specialized"),
    ("anninhthudo.vn",   0.65, "Regional"),
    ("congan.com.vn",    0.65, "Regional"),
    ("tinhhoa.net",      0.20, "Low Credibility"),
    ("danviet.vn",       0.45, "Tabloid"),
    ("baodatviet.vn",    0.45, "Tabloid"),
]

today = date.today()
vn_rows = [(d, s, c, today) for d, s, c in VN_DOMAINS]

execute_values(cur, """
    INSERT INTO sources (domain, credibility_score, category, last_updated)
    VALUES %s
    ON CONFLICT (domain) DO UPDATE SET
        credibility_score = EXCLUDED.credibility_score,
        category          = EXCLUDED.category,
        last_updated      = EXCLUDED.last_updated
""", vn_rows)
print(f"[seed] Inserted/updated {len(vn_rows)} Vietnamese domains.")

# ── 2. MBFC domains (from the existing JSON file) ─────────────
MBFC_PATH = Path(__file__).resolve().parent.parent / "data" / "mbfc_credibility.json"

if MBFC_PATH.exists():
    mbfc = json.loads(MBFC_PATH.read_text(encoding="utf-8"))
    mbfc_rows = [
        (domain, score, "MBFC", today)
        for domain, score in mbfc.items()
    ]
    execute_values(cur, """
        INSERT INTO sources (domain, credibility_score, category, last_updated)
        VALUES %s
        ON CONFLICT (domain) DO NOTHING
    """, mbfc_rows)
    # ON CONFLICT DO NOTHING means Vietnamese domains you set above
    # are never overwritten by MBFC data
    print(f"[seed] Inserted {len(mbfc_rows)} MBFC domains (skipped existing).")
else:
    print("[seed] mbfc_credibility.json not found, skipping MBFC import.")

conn.commit()
cur.close()
conn.close()
print("[seed] Done.")