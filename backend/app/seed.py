import json
from datetime import date

from psycopg2.extras import execute_values

from .config import get_settings
from .db import connection

CRED1_VERSION = "v2026-07-28"
CRED1_CATEGORIES = {
    "c": "Conspiracy",
    "f": "Fake",
    "m": "Mixed",
    "r": "Reliable",
    "s": "Satire",
    "u": "Unreliable",
}

VN_DOMAINS = [
    ("vnexpress.net", 0.85, "National News"), ("tuoitre.vn", 0.85, "National News"),
    ("thanhnien.vn", 0.82, "National News"), ("dantri.com.vn", 0.78, "National News"),
    ("tienphong.vn", 0.76, "National News"), ("laodong.vn", 0.74, "National News"),
    ("vietnamnet.vn", 0.78, "National News"), ("zingnews.vn", 0.72, "National News"),
    ("kenh14.vn", 0.60, "Entertainment"), ("baomoi.com", 0.65, "Aggregator"),
    ("nhandan.vn", 0.75, "State Media"), ("nhandan.com.vn", 0.75, "State Media"),
    ("vtv.vn", 0.80, "State Broadcast"), ("vov.vn", 0.78, "State Broadcast"),
    ("baochinhphu.vn", 0.72, "Government"), ("qdnd.vn", 0.70, "State Media"),
    ("plo.vn", 0.74, "National News"), ("nld.com.vn", 0.74, "National News"),
    ("sggp.org.vn", 0.72, "National News"), ("baogiaothong.vn", 0.68, "Specialized"),
    ("anninhthudo.vn", 0.65, "Regional"), ("congan.com.vn", 0.65, "Regional"),
    ("tinhhoa.net", 0.20, "Low Credibility"), ("danviet.vn", 0.45, "Tabloid"),
    ("baodatviet.vn", 0.45, "Tabloid"),
]


def main() -> None:
    today = date.today()
    with connection() as conn, conn.cursor() as cur:
        execute_values(cur, """
            INSERT INTO sources
                (domain, credibility_score, category, last_updated, rating_source, source_count, source_version)
            VALUES %s
            ON CONFLICT (domain) DO UPDATE SET credibility_score = EXCLUDED.credibility_score,
                category = EXCLUDED.category,
                last_updated = EXCLUDED.last_updated,
                rating_source = EXCLUDED.rating_source,
                source_count = EXCLUDED.source_count,
                source_version = EXCLUDED.source_version
        """, [
            (domain, score, category, today, "MANUAL", 1, None)
            for domain, score, category in VN_DOMAINS
        ])

        # MBFC is no longer a runtime input. Remove rows left by older seeds,
        # while preserving manually reviewed sources.
        cur.execute("DELETE FROM sources WHERE category = 'MBFC' OR rating_source = 'MBFC'")

        path = get_settings().cred1_path
        if path.exists():
            dataset = json.loads(path.read_text(encoding="utf-8"))
            rows = []
            for domain, metadata in dataset.items():
                if not isinstance(metadata, dict):
                    continue
                category = CRED1_CATEGORIES.get(str(metadata.get("c", "")).lower())
                score = metadata.get("s")
                source_count = metadata.get("n")
                if category is None or not isinstance(score, (int, float)):
                    continue
                rows.append((
                    domain,
                    float(score),
                    category,
                    today,
                    "CRED-1",
                    int(source_count) if isinstance(source_count, int) else 1,
                    CRED1_VERSION,
                ))

            cur.execute("DELETE FROM sources WHERE rating_source = 'CRED-1'")
            execute_values(cur, """
                INSERT INTO sources
                    (domain, credibility_score, category, last_updated, rating_source, source_count, source_version)
                VALUES %s
                ON CONFLICT (domain) DO UPDATE SET
                    credibility_score = EXCLUDED.credibility_score,
                    category = EXCLUDED.category,
                    last_updated = EXCLUDED.last_updated,
                    rating_source = EXCLUDED.rating_source,
                    source_count = EXCLUDED.source_count,
                    source_version = EXCLUDED.source_version
                WHERE sources.rating_source = 'CRED-1' OR sources.category = 'MBFC'
            """, rows)
            print(f"[seed] Loaded {len(rows)} CRED-1 domains ({CRED1_VERSION}).")
        else:
            print(f"[seed] CRED-1 dataset not found at {path}; manual sources only.")
    print("[seed] Credibility data is ready (CRED-1 + manual reviews).")


if __name__ == "__main__":
    main()
