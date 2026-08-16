# Codebase Refactor

This document describes the refactor on `features/refactor-codebase`. The goal was to
rename the service directories for clarity, split the backend into a pipeline and an
infrastructure layer, and replace the ad-hoc SQL/seed setup with proper Alembic migrations.

## Directory restructure

| Before               | After            | Notes                                        |
| -------------------- | ---------------- | -------------------------------------------- |
| `fn-extension-backend/` | `backend/`     | Single backend service, renamed.             |
| `sidepanel-src/`     | `extension-src/` | Extension source, renamed.                   |
| `de/`                | *(deleted)*      | Data-engineering service merged into `backend`. |

The old `de/` service (its `init.sql`, `seed.py`, Dockerfile, and API) is gone. Its
responsibilities — schema creation, seeding credibility data, and logging — moved into
the backend as Alembic migrations and the `app` package.

## Backend restructure

The backend is now split into two clearly-scoped packages:

- **`pipeline/`** — the fact-checking AI pipeline (the old `ai_core/`). This is the
  domain logic: normalize, search, filter, fetch, synthesize.
- **`app/`** — backend-local infrastructure: configuration, persistence, and caching.

```
backend/
├── main.py                    # FastAPI app + routes
├── alembic.ini                # Alembic configuration
├── pipeline/                  # (was ai_core/)
│   ├── __init__.py            #   public entry point: analyze()
│   ├── schema.py
│   ├── prefilter.py
│   ├── cache.py               #   compatibility façade over app.cache
│   └── steps/                 # (was ai_core/pipeline/)
│       ├── preprocessor.py
│       ├── query_builder.py
│       ├── searcher.py
│       ├── credibility_filter.py
│       ├── fetcher.py
│       └── synthesizer.py
└── app/
    ├── __init__.py
    ├── config.py              # Settings dataclass + get_settings()
    ├── db.py                  # psycopg2 connections and queries
    ├── services.py            # credibility service layer
    ├── cache.py               # Qdrant semantic cache
    ├── seed.py                # seeds the sources table
    └── migrations/            # Alembic environment and versions
        ├── env.py
        ├── script.py.mako
        └── versions/
            └── 0001_initial.py
```

Renames within the pipeline:

- `ai_core/` → `pipeline/`
- `ai_core/pipeline/` → `pipeline/steps/`
- `pipeline/cache.py` is now a thin façade that re-exports `app.cache.get` / `app.cache.set`,
  so the pipeline keeps importing `pipeline.cache` without knowing where the cache lives.

## Database migrations (new)

The backend now uses **Alembic** (SQLAlchemy migrations) instead of `de/init.sql`.

- `backend/alembic.ini` — Alembic entry config; points `script_location` at `app/migrations`.
- `backend/app/migrations/env.py` — migration runtime. Reads the DB URL from
  `get_settings().database_url` and runs migrations online.
- `backend/app/migrations/script.py.mako` — Mako template used to generate new version files
  on `alembic revision`.
- `backend/app/migrations/versions/0001_initial.py` — the initial migration. `upgrade()`
  creates two tables:
  - `sources` — `domain` (PK), `credibility_score`, `category`, `last_updated`.
  - `pipeline_logs` — `id` (PK), `input_hash`, `timestamp`, `steps_completed`, `verdict`,
    `error_stage`, `error_message`, `response_time_ms`.

### Seeding

`backend/app/seed.py` replaces `de/seed.py`. It upserts a hardcoded list of Vietnamese
domains and, when `MBFC_CREDIBILITY_PATH` points at a JSON file, bulk-inserts those
credibility scores as well.

## Configuration (new)

`backend/app/config.py` introduces a frozen `Settings` dataclass with a cached
`get_settings()` factory. Values come from environment variables with local defaults:

| Variable                  | Default                                                        |
| ------------------------- | -------------------------------------------------------------- |
| `DATABASE_URL`            | `postgresql://username:password@localhost:5432/fake_news_db`   |
| `QDRANT_HOST` / `QDRANT_PORT` | `localhost` / `6333`                                       |
| `SIMILARITY_THRESHOLD`    | `0.92`                                                         |
| `MBFC_CREDIBILITY_PATH`   | `<repo>/data/mbfc_credibility.json`                            |

`.env.example` was updated to match.

## Persistence helpers (new)

- `backend/app/db.py` — `psycopg2` connection context manager plus
  `credibility_for(domain)` (with subdomain fallback) and `write_log(log)`.
- `backend/app/services.py` — thin service layer over `db` exposing `credibility_score`
  and `credibility_response`. Keeps the route handlers free of SQL.
- `backend/app/cache.py` — the Qdrant semantic cache (`claim_cache` collection), moved out
  of `ai_core/cache.py`.

## Docker Compose

`docker-compose.yml` now:

- builds the backend from `./backend` (was `fn-extension-backend`),
- runs migrations and seeding on startup:

  ```yaml
  command: >
    sh -c "uv run alembic upgrade head && uv run python -m app.seed && uv run uvicorn main:app --host 0.0.0.0 --port 8000"
  ```

## Tests (new)

`backend/tests/test_services.py` adds `unittest` coverage for `app.services`
(known-domain vs unknown-domain responses), using `unittest.mock` to isolate the DB layer.

## Documentation

- Removed the loose top-level `PROGRESS.md` and `PROJECT_UPDATE.md`.
- Added `backend/README.md` (service overview, dev commands, routes).
- Added `backend/pipeline/README.md` (pipeline overview).

## Dependency changes

`backend/pyproject.toml` (renamed from `fn-extension-backend/pyproject.toml`) adds the
persistence stack: `alembic`, `sqlalchemy`, and `psycopg2-binary`.

## Running migrations locally

```bash
cd backend
uv run alembic upgrade head
uv run python -m app.seed
uv run uvicorn main:app --reload
```
