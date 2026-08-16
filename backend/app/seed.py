import json
from datetime import date

from psycopg2.extras import execute_values

from .config import get_settings
from .db import connection

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
            INSERT INTO sources (domain, credibility_score, category, last_updated) VALUES %s
            ON CONFLICT (domain) DO UPDATE SET credibility_score = EXCLUDED.credibility_score,
                category = EXCLUDED.category, last_updated = EXCLUDED.last_updated
        """, [(domain, score, category, today) for domain, score, category in VN_DOMAINS])
        path = get_settings().mbfc_credibility_path
        if path.exists():
            scores = json.loads(path.read_text(encoding="utf-8"))
            execute_values(cur, """
                INSERT INTO sources (domain, credibility_score, category, last_updated) VALUES %s
                ON CONFLICT (domain) DO NOTHING
            """, [(domain, score, "MBFC", today) for domain, score in scores.items()])
    print("[seed] Credibility data is ready.")


if __name__ == "__main__":
    main()
