# VeriFact backend

This is the application's single backend service. It owns FastAPI routes, the AI pipeline, PostgreSQL migrations/seeding, credibility lookup, pipeline logs, and the Qdrant semantic cache.

## Development

From this directory, install dependencies with `uv sync`. With Postgres and Qdrant available, run:

```bash
uv run alembic upgrade head
uv run python -m app.seed
uv run uvicorn main:app --reload
```

`DATABASE_URL`, `QDRANT_HOST`, `QDRANT_PORT`, `SIMILARITY_THRESHOLD`, and `MBFC_CREDIBILITY_PATH` configure persistence. Search and LLM credentials are read from `OPENROUTER_API_KEY` and `SERPER_API_KEY`.

## Routes

- `POST /analyze`
- `GET /credibility?domain=...`
- `POST /logs`
- `GET /health`

The extension-facing `POST /analyze` response is an `AnalysisResult` with `verdict`, `explanation`, `sources`, `confidence`, and `cached`.
