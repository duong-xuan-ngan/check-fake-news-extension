# SnapCheck backend

This is the application's single backend service. It owns FastAPI routes, the AI pipeline,
PostgreSQL migrations/seeding, Google Sign-In, daily usage quota, refresh tokens,
credibility lookup, pipeline logs, and the Qdrant semantic cache.

## Development

From this directory, install dependencies with `uv sync`. With Postgres and Qdrant
available, run:

```bash
uv run alembic upgrade head
uv run python -m app.seed
uv run uvicorn main:app --reload
```

`DATABASE_URL`, `QDRANT_HOST`, `QDRANT_PORT`, `SIMILARITY_THRESHOLD`, and
`CRED1_PATH` configure persistence and the pinned CRED-1 dataset. Search and LLM credentials are read from
`OPENROUTER_API_KEY` and `SERPER_API_KEY`. Auth is configured with `GOOGLE_CLIENT_ID`,
`GOOGLE_CLIENT_SECRET`, `JWT_SECRET`, `JWT_EXPIRES_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`,
and `DAILY_CHECK_LIMIT`.

## Routes

- `POST /auth/google` — exchange an OAuth code for `{access_token, refresh_token, user}`.
- `POST /auth/refresh` — rotate the refresh token for a new token pair.
- `POST /auth/logout` — revoke the refresh token.
- `GET /auth/me` — the current user.
- `GET /usage` — `{limit, used, remaining}` checks for today (UTC).
- `POST /analyze` — `{ "text": "claim" }` → `AnalysisResult` (requires auth; consumes one check).
- `GET /credibility?domain=...`
- `POST /logs`
- `GET /health`

The extension-facing `POST /analyze` response is an `AnalysisResult` with `verdict`,
`explanation`, `sources`, `confidence`, and `cached`.

Successful analysis results are cached in Qdrant for 24 hours. Older entries,
including legacy entries without a creation timestamp, are ignored and removed on access.
