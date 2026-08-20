# SnapCheck

SnapCheck is a Chrome extension that checks highlighted claims against web evidence.
Select a claim on any page and it shows an AI verdict, confidence, and the sources it
was checked against — before you trust it.

## Architecture

The extension calls one FastAPI modular monolith in `backend/`. That service owns the
analysis pipeline (`pipeline/`), PostgreSQL (credibility data, users, logs, usage, and
refresh tokens), and the Qdrant semantic cache. Postgres and Qdrant are infrastructure
containers; Caddy is the HTTPS reverse proxy in production.

Authentication is Google Sign-In via `chrome.identity.launchWebAuthFlow` + PKCE. The
backend exchanges the OAuth code for an identity, then issues a short-lived JWT **access
token** plus a rotating **refresh token**. Each account is limited to a daily number of
checks (`DAILY_CHECK_LIMIT`, UTC-reset).

## Environments

- **Development** — `docker-compose.yml` at the repo root. Exposes Postgres/Qdrant/backend
  ports and runs the backend with `--reload`. Uses root `.env`.
- **Production** — everything lives in `production/` (its own `docker-compose.yml`,
  `Caddyfile`, and `.env`). No backend ports are exposed; Caddy serves HTTPS.

Both environments share one env file layout. The backend reads its server config from the
same file, and Vite reads `VITE_API_BASE` and `VITE_GOOGLE_CLIENT_ID` from it too (via
`envDir` in `extension-src/vite.config.js`), so there's a single source of truth per
environment. Only `VITE_`-prefixed variables are inlined into the extension bundle —
server secrets are never exposed to the client.

## Run locally (development)

1. Copy `.env.example` to `.env` and supply the keys (LLM, search, and Google OAuth).
2. Run `docker compose up --build`. On startup it applies migrations, seeds credibility
   records, then starts the API.
3. In `extension-src/`, run `npm install && npm run build:dev`, then load `extension/` as an
   unpacked Chrome extension (Developer mode).
4. Open the extension's **Options** page and sign in with Google.

The extension targets `http://localhost:8000` in development (the `build:dev` build reads
`VITE_API_BASE` from the root `.env`).

## Run in production

1. `cp production/.env.example production/.env` and set real secrets.
2. `cd production && docker compose up -d --build`.
3. Build the extension for production: `cd extension-src && npm install && npm run build`
   (the production build reads `VITE_API_BASE` from `production/.env`).

## Google Sign-In setup

Sign-in uses a Google Cloud OAuth client of type **Web application**:

1. In Google Cloud Console → **APIs & Services → Credentials**, create an OAuth client.
   - **Application type**: Web application.
   - **Authorized redirect URIs**: `https://<extension-id>.chromiumapp.org/`
     (the extension ID from `chrome://extensions`).
2. Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `VITE_GOOGLE_CLIENT_ID` in your env
   file — `GOOGLE_CLIENT_ID` and `VITE_GOOGLE_CLIENT_ID` must match.

See `docs/team-run-guide.md` for a teammate-friendly walkthrough.

## Environment variables

| Variable | Description |
| --- | --- |
| `OPENROUTER_API_KEY` | AI synthesis (LLM) |
| `SERPER_API_KEY` | Web search |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google OAuth (server-side token exchange) |
| `VITE_GOOGLE_CLIENT_ID` | Google OAuth client id inlined into the extension build |
| `VITE_API_BASE` | Backend URL the extension calls |
| `JWT_SECRET` | Signs session tokens (`openssl rand -hex 32`) |
| `JWT_EXPIRES_MINUTES` | Access token lifetime (default `60`) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifetime (default `30`) |
| `DAILY_CHECK_LIMIT` | Checks per account per day (default `5`) |
| `DATABASE_URL`, `POSTGRES_*`, `QDRANT_*` | Persistence / cache infra |

## API

All analysis and usage routes require a bearer token from Google Sign-In.

- `POST /auth/google` — exchange an OAuth code for `{access_token, refresh_token, user}`.
- `POST /auth/refresh` — rotate the refresh token for a new token pair.
- `POST /auth/logout` — revoke the refresh token.
- `GET /auth/me` — the current user.
- `GET /usage` — `{limit, used, remaining}` checks for today (UTC).
- `POST /analyze` — `{ "text": "claim" }` returns an `AnalysisResult` (consumes one check).
- `GET /credibility?domain=example.com` — stored domain score, if known.
- `POST /logs` — operational log record.
- `GET /health` — service health.
