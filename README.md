# VeriFact

VeriFact is a Chrome extension that checks highlighted claims against web evidence.

## Architecture

The extension calls one FastAPI modular monolith in `backend/`. That service owns the
analysis pipeline (`pipeline/`), PostgreSQL credibility data and logs, and the Qdrant
semantic cache. Postgres and Qdrant are infrastructure containers; Caddy is the HTTPS
reverse proxy in production.

## Environments

- **Development** — `docker-compose.yml` at the repo root. Exposes Postgres/Qdrant/backend
  ports and runs the backend with `--reload`. Uses root `.env`.
- **Production** — everything lives in `production/` (its own `docker-compose.yml`,
  `Caddyfile`, and `.env`). No backend ports are exposed; Caddy serves HTTPS.

Both environments share one env file layout. The backend reads its server config from the
same file, and Vite reads `VITE_API_BASE` from it too (via `envDir` in
`extension-src/vite.config.js`), so there's a single source of truth per environment.
Only `VITE_`-prefixed variables are inlined into the extension bundle — server secrets are
never exposed to the client.

## Run locally (development)

1. Copy `.env.example` to `.env` and supply the API keys.
2. Run `docker compose up --build`.
3. In `extension-src/`, run `npm install && npm run build:dev`, then load `extension/` as an
   unpacked Chrome extension (Developer mode).

The extension targets `http://localhost:8000` in development (the `build:dev` build reads
`VITE_API_BASE` from the root `.env`).

## Run in production

1. `cp production/.env.example production/.env` and set real secrets.
2. `cd production && docker compose up -d --build`.
3. Build the extension for production: `cd extension-src && npm install && npm run build`
   (the production build reads `VITE_API_BASE` from `production/.env`).

On backend startup Compose applies migrations, seeds credibility records, then starts the
API.

## API

- `POST /analyze` with `{ "text": "claim" }` returns an `AnalysisResult`.
- `GET /credibility?domain=example.com` returns the stored domain score, if known.
- `POST /logs` stores an operational log record.
- `GET /health` reports service health.
