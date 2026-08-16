from typing import Optional

from . import db


def credibility_score(domain: str) -> Optional[float]:
    record = db.credibility_for(domain)
    return record[0] if record else None


def credibility_response(domain: str) -> dict:
    record = db.credibility_for(domain)
    if record is None:
        return {"credibility_score": None, "category": "unknown", "status": "not_found"}
    score, category = record
    return {"credibility_score": score, "category": category, "status": "found"}
