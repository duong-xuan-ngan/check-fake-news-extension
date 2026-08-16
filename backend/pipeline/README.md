# AI core

`analyze(text)` is the backend's fact-checking façade. It normalizes a claim, looks up the backend-local Qdrant cache, searches the web, filters sources through the local PostgreSQL credibility service, fetches articles, synthesizes a verdict, and caches successful evidence-backed results.

All external failures degrade to a valid `NOT_SURE` result; cache failures are treated as misses.
