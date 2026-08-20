# Team Run Guide

This guide walks you through running **SnapCheck** (the Chrome extension + FastAPI
backend) locally using the shared credentials posted in the group chat. You do not need
to create any API keys yourself — just drop in the shared `.env` and follow the steps.

## Prerequisites

- **Docker** (with Docker Compose) — runs Postgres, Qdrant, and the backend.
- **Node.js + npm** — builds the extension bundle.
- **Google Chrome** — to load the unpacked extension.

You do **not** need Python/uv locally; the backend runs inside Docker.

---

## 1. Get the shared credentials

1. Copy the `.env` file shared in the group chat.
2. Paste it into the **repo root** as `.env` (i.e. `check-fake-news-extension/.env`).

   ```bash
   # from the repo root
   cp /path/to/shared/.env .env
   ```

The shared `.env` contains the LLM/search keys, the Google OAuth client, and the signing
secret. For reference, the variables it should include are:

| Variable | What it's for |
| --- | --- |
| `OPENROUTER_API_KEY` | AI synthesis (LLM) |
| `SERPER_API_KEY` | Web search |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google Sign-In (server-side token exchange) |
| `VITE_GOOGLE_CLIENT_ID` | Google Sign-In (inlined into the extension build) |
| `VITE_API_BASE` | Backend URL the extension calls |
| `JWT_SECRET` | Signs session tokens |
| `DATABASE_URL`, `POSTGRES_*`, `QDRANT_*` | Local infra (defaults are fine) |
| `DAILY_CHECK_LIMIT` | Checks per account per day |

> **Important:** `GOOGLE_CLIENT_ID` and `VITE_GOOGLE_CLIENT_ID` must be **identical**.

---

## 2. Run the backend

From the repo root:

```bash
docker compose up --build
```

On startup the backend container automatically:

1. applies database migrations (`alembic upgrade head`),
2. seeds the credibility data (`app.seed`),
3. starts the API on `http://localhost:8000`.

Wait a minute, then confirm it's healthy:

```bash
curl http://localhost:8000/health
# -> {"status":"ok"}
```

Keep this terminal running. Stop it later with `Ctrl+C` (or run `docker compose up --build -d`
to detach).

---

## 3. Build and load the extension

```bash
cd extension-src
npm install
npm run build:dev
```

`build:dev` reads `VITE_API_BASE` / `VITE_GOOGLE_CLIENT_ID` from the root `.env` and outputs
the bundle into the `extension/` folder.

Then, in Chrome:

1. Open `chrome://extensions/`.
2. Toggle **Developer mode** (top-right).
3. Click **Load unpacked**.
4. Select the **`extension/`** folder from the repo root.

---

## 4. Sign in and verify

1. Open the extension's **options page**: right-click the SnapCheck icon → **Options**
   (or click the "Sign in" prompt that appears when you select text).
2. Click **Sign in with Google** and approve the consent screen.
3. Go to any news page, **highlight a claim**, and confirm the result card appears.

The options page shows your remaining daily checks and account info.

---

## Google Sign-In note (read this if sign-in fails)

Google sign-in uses a **"Web application"** OAuth client whose authorized redirect URI is
tied to the extension ID:

```
https://<extension-id>.chromiumapp.org/
```

This matters because **each machine can get a different extension ID** for an unpacked
extension (unless it's pinned). If sign-in fails with `redirect_uri_mismatch`:

- The shared OAuth client only accepts the redirect URI it was configured with.
- Check your extension ID at `chrome://extensions` (the long string on the card).

To make the **same shared client work for everyone**, the team lead should pin a stable
extension ID by adding a `"key"` field to `extension/manifest.json` (a base64 public key).
Then every teammate's unpacked extension gets the **same ID**, matching the shared
client's redirect URI. Without this, each teammate needs their own OAuth client.

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `Failed to connect to server` | Backend isn't running — check `docker compose up --build` and `/health`. |
| `401` / sign-in loops | Extension was built with a different `VITE_GOOGLE_CLIENT_ID` than `GOOGLE_CLIENT_ID`, or the JWT secret changed. Rebuild with `npm run build:dev` and sign in again. |
| `redirect_uri_mismatch` | See the Google Sign-In note above — extension ID doesn't match the OAuth client's redirect URI. |
| `daily limit reached` | Each account gets `DAILY_CHECK_LIMIT` checks/day (UTC). Use a different account or wait for reset. |
| Ports already in use | Postgres (`5432`), Qdrant (`6333`), backend (`8000`) — free them or edit `docker-compose.yml`. |

## Useful endpoints

- `GET /health` — service health.
- `GET /usage` — remaining daily checks (requires auth).
- Qdrant dashboard: `http://localhost:6333/dashboard`
