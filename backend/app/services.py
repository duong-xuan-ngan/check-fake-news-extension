from typing import Optional

from . import db


def credibility_score(domain: str) -> Optional[float]:
    record = db.credibility_for(domain)
    return record[0] if record else None


def credibility_scores(sources: list[dict[str, str]]) -> dict[str, Optional[float]]:
    """Return normalized domain scores in one query and discover unknowns."""
    records = db.credibility_for_many(sources)
    return {
        domain: record[0] if record is not None else None
        for domain, record in records.items()
    }


def credibility_response(domain: str) -> dict:
    record = db.credibility_for(domain)
    if record is None:
        return {"credibility_score": None, "category": "unknown", "status": "not_found"}
    score, category = record
    return {"credibility_score": score, "category": category, "status": "found"}
