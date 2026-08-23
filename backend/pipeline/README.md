# AI core

`analyze(text)` is the backend's fact-checking façade. It normalizes a claim, looks up the backend-local Qdrant cache, requests up to 20 web results, applies CRED-1/manual domain ratings through PostgreSQL, fetches up to 10 article bodies, synthesizes a verdict, and caches successful evidence-backed results.

CRED-1 is used as a negative/risk signal, not a whitelist. A domain absent from CRED-1 remains eligible as `UNRATED` evidence, is queued in `source_candidates`, and cannot by itself produce a high-confidence verdict. Explicitly rated sources below `0.5` are excluded.

All external failures degrade to a valid `NOT_SURE` result; cache failures are treated as misses.
