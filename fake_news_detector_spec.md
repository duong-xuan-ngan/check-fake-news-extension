# Fake News Detector — System Specification & Team Execution Plan

> **Document type:** Pre-implementation specification with implementation notes
> **Status:** AI Pipeline implemented (Step 8). Other roles pending.
> **Note:** Numeric thresholds (similarity, credibility, latency) are initial proposals and must be confirmed by the team in Phase 0. Implementation notes for the AI Pipeline reflect the state after Step 8 (May 2026); other stages remain as designed.

---

## Table of Contents

1. [System Specification](#1-system-specification)
   - [Stage 0 — User Input](#stage-0--user-input-frontend--backend)
   - [Stage 1 — Cache Check](#stage-1--cache-check-backend--de--qdrant)
   - [Stage 2 — AI Pipeline](#stage-2--ai-pipeline-core-analysis)
   - [Stage 3 — Result Return](#stage-3--result-return-backend--frontend)
2. [Team Responsibilities](#2-team-responsibilities)
   - [Data Engineering](#21-data-engineering-de)
   - [Backend](#22-backend)
   - [Frontend](#23-frontend-chrome-extension)
   - [AI Pipeline](#24-ai-pipeline)
3. [Cross-Role Dependencies](#3-cross-role-dependencies)
4. [Execution Order & Timeline](#4-execution-order--timeline)
5. [Appendix — Data Models](#5-appendix--data-models)

---

# 1. System Specification

Each stage below defines the agreed contract before any code is written. Every field is a team agreement, not a suggestion.

---

## Stage 0 — User Input (Frontend → Backend)

### 1. Input Data

| Field  | Type   | Constraints                                         |
| ------ | ------ | --------------------------------------------------- |
| `text` | string | Non-empty · max 2,000 chars · UTF-8 · whitespace-stripped |

**Source:** Text highlighted by the user on any webpage, captured on `mouseup` by the content script.

### 2. Output Data

`POST /analyze` payload sent over HTTPS to the Backend:

```json
{ "text": "<highlighted text>" }
```

### 3. Internal State

- The extension must retain the DOM bounding rect of the selection so the result panel can be anchored correctly even if the user scrolls slightly.

### 4. Dependencies on Other Stages

- None upstream. Frontend is the entry point.

### 5. Main Failure Cases

| Failure                  | Expected Behavior                                                  |
| ------------------------ | ------------------------------------------------------------------ |
| Empty selection          | Do not show the icon; do not send request                          |
| Selection > 2,000 chars  | Show inline warning: "Please select a shorter passage"             |
| Backend unreachable      | Show panel with error: "Could not connect to the analysis server"  |

### 6. Performance / Latency Expectations

- Icon must appear within **100 ms** of `mouseup`.
- Panel skeleton (loading state) must appear within **200 ms** of icon click.

---

## Stage 1 — Cache Check (Backend → DE / Qdrant)

### 1. Input Data

| Field       | Type     | Notes                                                                |
| ----------- | -------- | -------------------------------------------------------------------- |
| `text`      | string   | Raw text from Frontend                                               |
| `embedding` | float[]  | Vector generated from `text`; dimension matches Qdrant collection    |

> Backend generates the embedding **before** querying the cache. Embedding model must be agreed upon between Backend and DE before implementation.

### 2. Output Data

**On cache hit:**

| Field         | Type    | Notes                                                          |
| ------------- | ------- | -------------------------------------------------------------- |
| `verdict`     | string  | `TRUE` / `FALSE` / `UNVERIFIED` / `NOT_SURE`                   |
| `explanation` | string  | Free text, max 500 chars                                       |
| `sources`     | array   | Each: `{ url, domain, credibility_score, title, stance, published_at }` |
| `cached`      | boolean | Always `true` on cache hit                                     |

**On cache miss:** `null` — Backend proceeds to AI Pipeline.

### 3. Internal State

- Similarity threshold for cache hit: agreed constant (proposed: **0.92 cosine similarity**).
- Threshold must be stored in DE config, not hardcoded in Backend.

### 4. Dependencies on Other Stages

- DE must have Qdrant running and the lookup API exposed **before** Backend can implement cache check.
- Embedding model selection must be agreed between Backend and DE (same model used for both storing and querying).

> **Implementation note (Step 8):** AI Pipeline currently ships an interim **hash-based disk cache** (`data/cache.json`, 24h TTL) keyed on SHA-256 of the lowercased English claim. This lives inside `ai_core/cache.py` and is wired into `analyze()` itself, not exposed to Backend. It is functionally correct for English inputs and pure happy-coincidence hits across languages, but does not survive LLM translation jitter for the same non-English input across runs. **It will be replaced by the Qdrant vector cache described in this stage** when DE delivers — at that point, caching moves from inside the pipeline to the Backend layer where it belongs architecturally.

### 5. Main Failure Cases

| Failure                     | Expected Behavior                                       |
| --------------------------- | ------------------------------------------------------- |
| Qdrant unreachable          | Log error; treat as cache miss; proceed to pipeline     |
| Embedding generation fails  | Return 500 to Frontend with structured error            |
| Malformed cache record      | Log and discard; treat as cache miss                    |

### 6. Performance / Latency Expectations

- Cache lookup (including embedding generation): **< 300 ms**.

---

## Stage 2 — AI Pipeline (Core Analysis)

The pipeline executes sequentially in v1. Each sub-step is specified below.

> **Implementation status (Step 8):** All sub-stages below are implemented in `ai_core/`. The public entry point is `ai_core.analyze(text: str) -> AnalysisResult`. The pipeline never raises — every failure mode maps to `NOT_SURE`.

---

### Sub-step 2.0 — Preprocessing (Language Normalization)

> **Added during Step 8** — translation responsibility was lifted out of `query_builder` into its own pipeline stage so that all downstream stages always see English input.

**1. Input Data:** Raw `text` string in any language.

**2. Output Data:** A cleaned, English-language claim string (`english_claim`), max 1,500 chars.

**3. Internal State:** None persisted.

**4. Dependencies:** `OPENROUTER_API_KEY` for the translation LLM call.

**5. Processing logic:**
- Strip and collapse whitespace, truncate to 1,500 chars.
- **Cheap heuristic first:** if every char is in basic Latin + common punctuation, treat as English and skip the LLM call entirely.
- **Otherwise:** call OpenRouter to translate. The translation prompt is narrow: preserve named entities, numbers, and dates verbatim; return only the translated text.

**6. Failure Cases:**

| Failure                          | Expected Behavior                                              |
| -------------------------------- | -------------------------------------------------------------- |
| Translation LLM fails or times out | Fall back to the cleaned original text (graceful degradation; downstream stages may then return `NOT_SURE`) |
| LLM returns empty translation    | Fall back to the cleaned original text                         |
| Input is empty after cleaning    | `analyze()` short-circuits and returns `NOT_SURE` immediately  |

**7. Latency:** < 100 ms for English (no LLM); 1–7 seconds for non-English (one LLM call).

---

### Sub-step 2.1 — Query Generation

**1. Input Data:** The `english_claim` string from 2.0.

**2. Output Data:** A search query string, max ~15 words, preserving names, numbers, and dates.

**3. Internal State:** None persisted.

**4. Dependencies:** `OPENROUTER_API_KEY`.

**5. Processing logic:** Three-layer fallback in `query_builder.build_search_query()`:
- **Layer 1:** if the claim is already ≤ 10 words, use it directly (no LLM call).
- **Layer 2:** LLM rewrite — turn the claim into a keyword-focused query, strip filler/stop words, keep entities/numbers/dates.
- **Layer 3:** regex entity extraction — capitalized tokens + numbers, as a last resort if the LLM fails.

**6. Failure Cases:** Never raises. If all three layers degrade to an empty string, downstream search will return zero results and the pipeline will return `NOT_SURE`.

**7. Latency:** < 100 ms for short claims (Layer 1); 1–3 seconds when the LLM is invoked.

---

### Sub-step 2.2 — Web Search (Serper API)

**1. Input Data:** Query string from 2.1.

**2. Output Data:** List of up to 10 result objects:

| Field     | Type   |
| --------- | ------ |
| `url`     | string |
| `domain`  | string |
| `title`   | string |
| `snippet` | string |

**3. Internal State:** None persisted.

**4. Dependencies:** `SERPER_API_KEY` as environment variable.

**5. Failure Cases:**

| Failure                        | Expected Behavior                                              |
| ------------------------------ | -------------------------------------------------------------- |
| Serper API rate limit exceeded | Return `NOT_SURE`; log with reason `"search_rate_limit"`       |
| Serper returns 0 results       | Return `NOT_SURE`; log with reason `"no_search_results"`       |
| Serper timeout (> 5s)          | Abort; return `NOT_SURE`; log with reason `"search_timeout"`   |

**6. Latency:** < 2 seconds.

---

### Sub-step 2.3 — Source Credibility Filtering

**1. Input Data:** List of result objects from 2.2 (each with `domain` field).

**2. Output Data:** Filtered list — only results where `credibility_score >= 0.50` are retained. Output is **deduplicated by domain** (first occurrence wins).

**3. Internal State:** None persisted in the running process. Credibility data lives in DE's PostgreSQL — see implementation note below.

**4. Dependencies:** DE must expose `GET /credibility?domain=<domain>` returning `{ credibility_score, category }`.

> **Implementation note (Step 5):** Until DE delivers the credibility endpoint, AI Pipeline ships a static `data/mbfc_credibility.json` (built one-time by `scripts/build_mbfc.py` from MBFC raw CSV) and loads it at module import. When DE delivers the live endpoint, only `credibility_filter._load_db()` needs to change. The JSON file can then be deleted.
>
> **Subdomain fallback:** If the exact domain is not in the DB, the filter strips the subdomain and retries (e.g. `en.wikipedia.org` → `wikipedia.org`).
>
> **Known MBFC quirk:** `facebook.com` and `youtube.com` score 0.9 in MBFC because they are rated as platforms, not publishers. The fetcher (Step 2.4) typically fails to extract usable bodies from these domains anyway, so they self-exclude downstream.

**5. Failure Cases:**

| Failure                          | Expected Behavior                                                   |
| -------------------------------- | ------------------------------------------------------------------- |
| DE credibility API unreachable   | (Future) Fall back to bundled MBFC JSON                             |
| Domain not found in DB           | Drop the result (current behavior — does not pass the threshold)    |
| All results filtered out         | Return `NOT_SURE`; log with reason `"no_credible_sources"`          |

**6. Latency:** < 100 ms (in-memory JSON lookup); < 500 ms when DE endpoint is in use.

---

### Sub-step 2.4 — Content Fetching (newspaper3k + BeautifulSoup fallback)

**1. Input Data:** Deduplicated, filtered list of URLs from 2.3 — currently up to ~10 URLs (the filter caps via deduplication, not a hard URL count).

**2. Output Data:** List of fetched article objects:

| Field               | Type                          |
| ------------------- | ----------------------------- |
| `url`               | string                        |
| `domain`            | string                        |
| `title`             | string                        |
| `body`              | string (max 3,000 chars)      |
| `credibility_score` | float (passed through from 2.3) |
| `published_at`      | `Optional[datetime]` — UTC; `None` if not extractable (added in Step 7.5) |

**3. Internal State:** None persisted.

**4. Dependencies:** Filtered URL list from 2.3.

**5. Processing logic:**
- **Primary parser:** newspaper3k.
- **Fallback parser:** `requests` + BeautifulSoup `<p>` extraction.
- **Skip rule:** body < 150 chars (`MIN_BODY_LENGTH`) → skip; don't pass to synthesizer.
- **Date extraction (Step 7.5):** three strategies tried in order — (1) standard meta tags like `article:published_time`, (2) JSON-LD `datePublished` inside `<script type="application/ld+json">` (used by ESPN, NYT, etc.), (3) `<time datetime="...">` element. Articles without parseable dates are kept; `published_at` defaults to `None`.

**6. Failure Cases:**

| Failure                     | Expected Behavior                                              |
| --------------------------- | -------------------------------------------------------------- |
| Fetch blocked (403/429)     | Skip URL; continue with remaining                              |
| JavaScript-rendered page    | Skip; v2 candidate for Playwright                              |
| Fetch timeout (> 5s/URL)    | Skip URL                                                       |
| All fetches fail            | Synthesizer receives empty list → returns `NOT_SURE`           |

**7. Latency:** Sequential in v1; total fetch budget **< 8 seconds** for typical 3–5 successful fetches. Parallel fetch is a v2 optimization.

---

### Sub-step 2.5 — LLM Analysis / Verdict Synthesis

> **Provider change (Step 7.5):** This sub-step originally specified Gemini. It now uses **OpenRouter** (`https://openrouter.ai/api/v1`, OpenAI-compatible SDK, model `openrouter/auto`). The change brought consistency with the preprocessor and query_builder, and gave us free-tier model availability across multiple providers behind a single API.

**1. Input Data:**

| Field              | Type                       | Notes                              |
| ------------------ | -------------------------- | ---------------------------------- |
| `english_claim`    | string                     | The normalized claim from Step 2.0 (NOT the raw user text — cross-language reasoning happens upstream of the synthesizer) |
| `fetched_articles` | `List[FetchedArticle]`     | From 2.4                           |

**2. Output Data (Pydantic `AnalysisResult`):**

```json
{
  "verdict": "TRUE | FALSE | UNVERIFIED | NOT_SURE",
  "explanation": "string, max 500 chars",
  "sources": [
    {
      "url": "string",
      "domain": "string",
      "title": "string",
      "credibility_score": 0.0,
      "stance": "SUPPORTS | CONTRADICTS | NEUTRAL",
      "published_at": "ISO 8601 datetime or null"
    }
  ],
  "confidence": "HIGH | MEDIUM | LOW",
  "cached": false
}
```

**Anti-hallucination pattern (critical):** The LLM only returns `article_index` (the index into the `fetched_articles` array we passed it), stance, verdict, explanation, and confidence. The synthesizer fills in URLs, titles, domains, credibility scores, and `published_at` from our own `FetchedArticle` data. **The LLM is never asked to echo back data we already have.** This eliminates a major hallucination surface with zero benefit.

**Structured chain-of-thought pattern:** The prompt forces the LLM to write `claim_in_article` (what the article actually says) and `user_claim` (what the user claimed) as required JSON fields *before* picking a `stance` label. This makes the stance comparison explicit and reduces label confusion.

**Temporal rule:** When two sources directly contradict each other, the synthesizer prefers the more recent `published_at`. Sources without dates cannot override sources with dates. The rule is intentionally narrow — no broad "is this claim time-sensitive?" judgment, which would itself be a hallucination surface.

**3. Internal State:** None persisted.

**4. Dependencies:** `OPENROUTER_API_KEY` (environment variable). Articles from 2.4.

**5. Failure Cases:**

| Failure                         | Expected Behavior                                                |
| ------------------------------- | ---------------------------------------------------------------- |
| OpenRouter rate limit           | Return `NOT_SURE`; log reason `"llm_rate_limit"`                 |
| LLM returns malformed JSON      | `response_format={"type": "json_object"}` enforced; on parse fail still, return `NOT_SURE` |
| LLM timeout (> 10s)             | Abort; return `NOT_SURE`; log reason                             |
| LLM outputs forbidden enum value | Pydantic validation rejects; default to `NOT_SURE`              |
| Reasoning model `<think>...</think>` blocks in output | Stripped via regex before JSON parsing |
| Empty `fetched_articles`        | Short-circuit: return `NOT_SURE` with explanation "Could not retrieve enough evidence", confidence `LOW`, sources `[]` |

**6. Latency:** 5–15 seconds (varies with `openrouter/auto` model selection).

---

## Stage 3 — Result Return (Backend → Frontend)

### 1. Input Data

The full `AnalysisResult` from Sub-step 2.5.

### 2. Output Data

**Success response:**

```json
{
  "verdict": "TRUE | FALSE | UNVERIFIED | NOT_SURE",
  "explanation": "string",
  "sources": [
    {
      "url": "string",
      "domain": "string",
      "title": "string",
      "credibility_score": 0.0,
      "stance": "SUPPORTS | CONTRADICTS | NEUTRAL",
      "published_at": "ISO 8601 datetime or null"
    }
  ],
  "confidence": "HIGH | MEDIUM | LOW",
  "cached": false,
  "response_time_ms": 0
}
```

**Error response:**

```json
{
  "error": "string",
  "failed_at_stage": "preprocess | search | filter | fetch | llm | cache",
  "verdict": "NOT_SURE"
}
```

### 3. Internal State

After a successful pipeline run, Backend triggers DE's cache store API with the result + embedding. This is **fire-and-forget** — it must not block the response to Frontend.

### 4. Dependencies on Other Stages

- Verdict from Stage 2.5.
- DE's cache store endpoint (asynchronous call after response).

### 5. Main Failure Cases

| Failure                              | Expected Behavior                                              |
| ------------------------------------ | -------------------------------------------------------------- |
| Pipeline returns malformed verdict   | (Cannot happen — Pydantic validates enums.) Falls under generic exception handling. |
| Cache store fails                    | Log error; do not affect Frontend response (fire-and-forget)   |

### 6. Performance / Latency Expectations

| Path                            | Target                |
| ------------------------------- | --------------------- |
| Cache miss — full pipeline      | **< 25 seconds** end-to-end (loosened from 15s based on observed LLM latency on free-tier OpenRouter routing) |
| Cache hit                       | **< 1 second**        |

---

# 2. Team Responsibilities

This section converts the specification into concrete, assigned tasks with clear definitions of done.

---

## 2.1 Data Engineering (DE)

### Task 1 — Set up Qdrant (Vector Cache)

**Exact tasks:**
- Install and configure Qdrant via Docker.
- Create a collection with the agreed embedding dimension.
- Implement the lookup endpoint: accepts an embedding vector, returns the closest cached record if similarity ≥ threshold, else null.
- Implement the store endpoint: accepts `{ embedding, verdict, explanation, sources }`, writes to Qdrant.
- Document the threshold value and collection schema in `de/README.md`.

**Deliverable:** A running Qdrant instance accessible at `http://qdrant:6333` inside the Docker network, with both endpoints tested via `curl` or Postman.

**Definition of Done:** Backend can call the lookup endpoint with a test embedding and receive either a valid cached record or null. Store endpoint writes a record that is subsequently retrievable by lookup.

---

### Task 2 — Set up PostgreSQL: Source Credibility Database

**Exact tasks:**
- Create a `sources` table with fields: `domain`, `credibility_score`, `category`, `last_updated`.
- Seed it with at least 50 Vietnamese news domains (VnExpress, Tuổi Trẻ, Thanh Niên, Dân Trí, etc.) with manually assigned credibility scores.
- Supplement with MBFC data where available for international domains. (**Reference:** AI Pipeline currently ships `data/mbfc_credibility.json` built by `scripts/build_mbfc.py`. DE can reuse this as the international seed and add Vietnamese domains on top.)
- Expose a REST endpoint: `GET /credibility?domain=<domain>` → `{ credibility_score, category }`.
- Handle the "domain not found" case explicitly (return neutral score 0.5).

**Deliverable:** PostgreSQL running in Docker, seeded database, endpoint accessible at `http://db-api:8001/credibility` inside Docker network.

**Definition of Done:** AI Pipeline can query any Vietnamese news domain and receive a score. At least 50 domains covered at launch.

---

### Task 3 — Set up PostgreSQL: Behavior Logging Table

**Exact tasks:**
- Create a `pipeline_logs` table: `id`, `input_hash`, `timestamp`, `steps_completed`, `verdict`, `error_stage`, `error_message`, `response_time_ms`.
- Expose a write endpoint for Backend to POST a log entry after each request.
- No read endpoint needed for v1.

**Deliverable:** Table created and reachable. Backend can POST a log entry and it persists.

**Definition of Done:** After 10 test requests, 10 log rows are present in the table with correct data.

---

### Task 4 — Docker Compose Setup

**Exact tasks:**
- Write a single `docker-compose.yml` that brings up: Qdrant, PostgreSQL, the DE API service, Backend, and AI Pipeline.
- Define a shared internal Docker network.
- Use environment variable files (`.env`) for all secrets — never hardcode keys.
- Write a `README.md` with the single command to start the whole system: `docker compose up`.

**Deliverable:** `docker-compose.yml` committed to the repository root.

**Definition of Done:** Running `docker compose up` on a clean machine (no pre-existing volumes) brings all services to healthy state within 2 minutes.

---

### Task 5 — Logging Infrastructure

**Exact tasks:**
- Implement structured JSON logging across DE's own services (Qdrant API wrapper, PostgreSQL API).
- Define the log schema and share it with Backend and AI Pipeline so all roles log consistently.
- Set up log output to stdout (captured by Docker) for v1.

**Deliverable:** Log schema document (`de/log_schema.md`). All DE services emit structured JSON logs.

**Definition of Done:** Running the system end-to-end produces parseable JSON log lines for every request.

---

## 2.2 Backend

### Task 1 — Implement `POST /analyze` Endpoint

**Exact tasks:**
- Set up a FastAPI application with a single route: `POST /analyze`.
- Validate incoming request: reject empty text, text > 2,000 chars.
- Wire the cache check → AI pipeline → cache store flow.
- Return the standardized success or error JSON defined in Stage 3 of this spec.

**Deliverable:** Running FastAPI app, endpoint reachable at `http://backend:8000/analyze` inside Docker network.

**Definition of Done:** Sending `POST /analyze` with a test text returns a valid JSON response matching the spec schema in < 25 seconds. Invalid inputs return 400 with a descriptive error.

---

### Task 2 — Cache Check Integration

**Exact tasks:**
- Generate an embedding for the input text using the agreed embedding model.
- Call DE's Qdrant lookup endpoint.
- If cache hit: return result immediately to Frontend, skip AI pipeline.
- If cache miss: proceed to AI Pipeline.

**Deliverable:** Cache check logic implemented and tested with a pre-seeded Qdrant record.

**Definition of Done:** A request for a previously cached claim returns in < 1 second with `"cached": true` in the response.

> **Note:** AI Pipeline currently has an in-process hash cache as a stand-in (see Stage 1 implementation note). When the Qdrant cache lands, the in-process cache should be removed from `ai_core.analyze()` — caching is properly a Backend responsibility.

---

### Task 3 — AI Pipeline Orchestration

**Exact tasks:**
- Import `from ai_core import analyze` and call `analyze(text)` — single function call, no API keys passed in (the pipeline loads its own keys from `.env`).
- Receive `AnalysisResult` (Pydantic model — convert via `.model_dump()` for JSON response).
- Fire-and-forget: call DE's cache store endpoint asynchronously (do not await before responding to Frontend).
- Log the request via DE's logging endpoint.

**Deliverable:** Orchestration logic that ties cache miss → pipeline → store → respond in the correct order.

**Definition of Done:** Full end-to-end request (cache miss) completes and produces a correct response with `"cached": false`. Qdrant contains the new cached record after the request.

---

### Task 4 — API Key Management

**Exact tasks:**
- AI Pipeline loads `SERPER_API_KEY` and `OPENROUTER_API_KEY` from `.env` itself — Backend does not pass them.
- Verify at startup that required keys are present; crash with a clear error if missing.
- Add keys to `.env.example` (with placeholder values) for documentation.

**Deliverable:** Keys never appear in source code or logs. `.env.example` documents all required variables.

**Definition of Done:** Running the Backend with a missing key produces a startup error naming the missing variable, not a silent crash during a request.

---

### Task 5 — Error Handling & Response Normalization

**Exact tasks:**
- `ai_core.analyze()` is guaranteed never to raise — any internal failure returns an `AnalysisResult` with `verdict=NOT_SURE`. Backend should still wrap the call in try/except as defensive programming, but the expected failure path is a `NOT_SURE` result, not an exception.
- For unexpected exceptions (network, malformed request), return the standardized error response JSON (see Stage 3 spec) with `failed_at_stage` populated.
- Log all errors to DE's logging endpoint.
- Never expose raw stack traces to Frontend.

**Deliverable:** Error handling middleware in FastAPI.

**Definition of Done:** Simulating a Serper API failure returns `{ verdict: "NOT_SURE", ... }` (graceful — preferred path) to the caller, not a 500 with a Python traceback.

---

## 2.3 Frontend (Chrome Extension)

### Task 1 — Text Highlight Detection

**Exact tasks:**
- Inject a content script that listens for `mouseup`.
- On `mouseup`, check `window.getSelection()` — if non-empty and length > 0, proceed.
- Extract the selection bounding rect using `getBoundingClientRect()` for panel positioning.
- Ignore selections inside the extension's own panel.

**Deliverable:** Content script that reliably detects text selections on any standard webpage.

**Definition of Done:** Highlighting text on VnExpress, Facebook, and a plain HTML page all trigger detection. Highlighting nothing does not trigger.

---

### Task 2 — Icon Display

**Exact tasks:**
- Inject a small SVG icon element into the DOM near the selection end point.
- Position using `position: absolute` relative to `document.body`, offset from bounding rect.
- Remove the icon on `mousedown` anywhere outside the icon and panel.
- Icon must not interfere with page layout (use `z-index` and `pointer-events` carefully).

**Deliverable:** Icon that appears and disappears correctly across test pages.

**Definition of Done:** Icon appears within 100 ms of highlight, is positioned within 20px of the selection endpoint, and disappears when the user clicks elsewhere.

---

### Task 3 — Backend Request

**Exact tasks:**
- On icon click, send `POST /analyze` with `{ "text": "<selection>" }` to the configured Backend URL.
- Backend URL must be configurable (stored in `chrome.storage.sync` or a config file), not hardcoded.
- Handle network errors explicitly (no Backend connection = show error panel, not a silent failure).

**Deliverable:** Fetch call with correct headers (`Content-Type: application/json`) and body.

**Definition of Done:** Extension successfully sends a request to a locally running Backend and receives a response. Network errors surface as a visible panel message, not a console error.

---

### Task 4 — Loading State

**Exact tasks:**
- Show the panel immediately on icon click with a loading skeleton.
- Panel must remain visible while the Backend processes (up to 25 seconds).
- Show a spinner or animated placeholder — not a blank panel.

**Deliverable:** Panel component with loading state distinct from result state.

**Definition of Done:** Clicking the icon always produces an immediate panel (< 200 ms). The panel remains visible for the full Backend response time.

---

### Task 5 — Result Display Panel

**Exact tasks:**
- Parse the Backend response JSON.
- Render Section 1: verdict label (color-coded: green/red/grey), confidence badge, explanation text.
- Render Section 2: sources list — each source shows domain, credibility score (as a bar or percentage), stance label, and **publication date** (if `published_at` is present).
- Render the `NOT_SURE` state with neutral styling and text: "Insufficient evidence to determine credibility."
- Render the error state with a friendly message (no raw JSON shown to user).
- Panel must be dismissible (close button or click-outside).

**Deliverable:** Fully styled panel component covering success, not-sure, and error states.

**Definition of Done:** Given mock JSON for each of the four verdicts, the panel renders correctly. Panel is dismissible. No raw JSON or error codes visible to the user.

---

## 2.4 AI Pipeline

> **Status (Step 8 complete):** All tasks in this section are implemented. The notes below have been updated to reflect what was actually built. Open items (Qdrant cache migration, parallel fetch, atomic claim decomposition) are listed under "Future work" at the end.

### Task 1 — Preprocessing (Language Normalization) — *added during Step 8*

**Exact tasks:**
- Write `preprocessor.normalize(text: str) -> str` that returns a cleaned English claim.
- Use a regex heuristic (`is_english`) to skip the LLM for pure-ASCII input.
- Call OpenRouter to translate non-English input; the translation prompt is narrow (preserve entities/numbers/dates, return text only).
- Fall back to the cleaned original on any translation failure (graceful degradation).

**Deliverable:** `ai_core/pipeline/preprocessor.py` with `is_english`, `translate_to_english`, and `normalize` functions.

**Definition of Done:** Vietnamese input is translated correctly; English input bypasses the LLM (verified in REPL tests). Empty input returns empty string. Translation timeout returns the cleaned original.

---

### Task 2 — Search Query Generation

**Exact tasks:**
- Write `build_search_query(english_claim: str) -> str` in `query_builder.py`.
- Three-layer fallback: short claims pass through (no LLM); medium claims are LLM-rewritten; LLM failure falls back to regex entity extraction.
- Cap output at ~15 words. Preserve entities, numbers, dates.

**Deliverable:** `ai_core/pipeline/query_builder.py`.

**Definition of Done:** Given "Florentino Perez is the president of FC Barcelona" (already short — Layer 1 passes through). Given a 50-word Vietnamese-translated claim, the LLM produces a focused English keyword query.

---

### Task 3 — Web Search Integration

**Exact tasks:**
- Write `search(query: str) -> List[SearchResult]` calling Serper API.
- Parse response into `SearchResult` Pydantic models with `url`, `domain`, `title`, `snippet`.
- Extract domain using `urllib.parse.urlparse(url).netloc.removeprefix("www.")`.
- Implement timeout and handle rate limit / empty results per the spec.

**Deliverable:** `ai_core/pipeline/searcher.py`.

**Definition of Done:** Function returns a non-empty list of results for a test query. Rate limit and timeout scenarios return an empty list with a logged reason, not an exception.

---

### Task 4 — Source Credibility Filtering

**Exact tasks:**
- Write `filter_credible(results) -> List[ScoredResult]` in `credibility_filter.py`.
- Load credibility DB at module import (interim: `data/mbfc_credibility.json`; future: HTTP call to DE).
- Apply threshold (`CREDIBILITY_THRESHOLD = 0.5`).
- **Deduplicate by domain** (first occurrence wins).
- Subdomain fallback: `en.wikipedia.org` → look up `wikipedia.org` if the exact match fails.

**Deliverable:** `ai_core/pipeline/credibility_filter.py` + `data/mbfc_credibility.json` + `scripts/build_mbfc.py`.

**Definition of Done:** Filter retains credible domains, drops uncredible, deduplicates. When DE delivers the endpoint, only `_load_db()` needs to change.

---

### Task 5 — Content Fetching

**Exact tasks:**
- Write `fetch_all(scored: List[ScoredResult]) -> List[FetchedArticle]` in `fetcher.py`.
- Primary parser: newspaper3k. Fallback: `requests` + BeautifulSoup.
- Truncate body to 3,000 chars; skip if body < 150 chars.
- **Extract `published_at`** via three strategies: meta tags → JSON-LD → `<time>` element.

**Deliverable:** `ai_core/pipeline/fetcher.py`.

**Definition of Done:** Fetches content from ESPN, Wikipedia, Yahoo Sports successfully. A blocked URL is skipped without crashing. Dates extracted correctly from sites using JSON-LD (e.g. ESPN).

---

### Task 6 — LLM Analysis and Verdict Synthesis

**Exact tasks:**
- Write `synthesize(english_claim, articles) -> AnalysisResult` in `synthesizer.py`.
- Single LLM call (OpenRouter, `openrouter/auto`). Use `response_format={"type": "json_object"}`.
- Apply the **anti-hallucination pattern**: LLM returns indices + stance + verdict; synthesizer fills in URLs/titles/domains/credibility/dates from the input `FetchedArticle` list.
- Apply the **structured chain-of-thought pattern**: prompt forces `claim_in_article` and `user_claim` as required JSON fields before stance.
- Apply the **temporal rule**: more recent dated source wins on direct contradiction.
- Strip `<think>...</think>` blocks (some reasoning models include them) before JSON parsing.
- Return `NOT_SURE` if articles list is empty or LLM fails.

**Deliverable:** `ai_core/pipeline/synthesizer.py`.

**Definition of Done:** Given articles supporting / contradicting a claim, the synthesizer returns the correct verdict with the correct sources. Empty articles list returns `NOT_SURE` with confidence `LOW`. Verified live with English, Vietnamese, true, false, and opinion claims.

---

### Task 7 — Public `analyze()` entry point

**Exact tasks:**
- Implement `ai_core.analyze(text: str) -> AnalysisResult` in `ai_core/__init__.py`.
- Wire all sub-stages: preprocessor → cache → query_builder → searcher → credibility_filter → fetcher → synthesizer → cache store.
- Never raise — empty input or any internal failure returns a `NOT_SURE` `AnalysisResult`.
- Single integration point with Backend.

**Deliverable:** `ai_core/__init__.py`.

**Definition of Done:** Backend can `from ai_core import analyze` and call with a string, receiving a valid `AnalysisResult`. End-to-end smoke test (`scripts/test_pipeline.py`) passes all four cases.

---

### Task 8 — Interim disk cache (to be replaced by Qdrant)

**Exact tasks:**
- Implement `ai_core/cache.py` with `get(english_claim)` and `set(english_claim, result)`.
- SHA-256 key on lowercased English claim. JSON file at `data/cache.json`. 24h TTL. Prune-on-write.
- This is a **temporary measure** until DE delivers the Qdrant vector cache (Stage 1).

**Deliverable:** `ai_core/cache.py`.

**Definition of Done:** Repeat English claims hit the cache. Vietnamese inputs that happen to translate to the same English string also hit. Known limitation documented: LLM translation jitter means same Vietnamese input may produce different cache keys across runs — to be solved by Qdrant vector cache (similarity-based, not hash-based).

---

### Future work (open items)

- **Migrate cache to Qdrant** (Stage 1) when DE delivers. Caching moves from `ai_core.analyze()` to the Backend layer; the in-process disk cache is then deleted.
- **Parallel fetching** in `fetcher.py` (currently sequential; async would cut fetch latency significantly).
- **Atomic claim decomposition** — multi-claim posts are currently collapsed into a single search query. A v2 atomic-claim splitter would individually verify each sub-claim.
- **Single-source confidence inflation** — when only 1 article survives fetching, the LLM still confidently returns `HIGH`. Open question: hard rule in prompt vs. trust LLM judgment.
- **Pinned model vs `openrouter/auto`** — per-source stance labels are noisier under the auto-router. Worth revisiting if user-facing problems emerge.

---

# 3. Cross-Role Dependencies

This section explicitly maps where roles must coordinate. Uncoordinated work at these points will cause integration failures.

| # | Dependency                       | Roles Involved      | What Must Be Agreed                                                            | When                                  |
| - | -------------------------------- | ------------------- | ------------------------------------------------------------------------------ | ------------------------------------- |
| 1 | Embedding model selection        | Backend + DE        | Model name (e.g. multilingual MiniLM), output dimension, library               | Before Qdrant cache integration       |
| 2 | Cache similarity threshold       | Backend + DE        | Numeric value (proposed: 0.92); stored in DE config, read by Backend           | Before cache integration              |
| 3 | Credibility score threshold      | AI Pipeline + DE    | Currently 0.50 (AI Pipeline default). DE's seeded data must align.             | Before DE endpoint goes live          |
| 4 | `/credibility` endpoint schema   | AI Pipeline + DE    | Exact URL, request format, response format, "not found" behavior               | Before AI Pipeline cuts over from JSON to live endpoint |
| 5 | Final response JSON schema       | Backend + Frontend  | Exact field names, verdict enum values, sources array structure (now including `published_at`) | Before any UI code is written |
| 6 | Backend URL configuration        | Frontend + Backend  | Local dev URL (`http://localhost:8000`); how it is configured in the extension | Before Frontend Task 3                |
| 7 | API keys in Docker               | Backend + DE        | Variable names in `.env`; which service owns key injection (AI Pipeline loads its own) | Before Docker Compose is finalized    |
| 8 | Log schema                       | All roles           | JSON structure for log entries; which fields are mandatory                     | Before any service is built           |

> **Highest-risk dependency: #1 (Embedding model selection).** If Backend and DE implement independently with different models, the cache will never produce a valid hit. This is the one agreement that must happen first when Qdrant work begins.

---

# 4. Execution Order & Timeline

## Phase 0 — Agreements (Before Any Code)

All four roles must agree on the following before implementation begins. This phase should take no more than one working session.

1. **Embedding model** — chosen and documented.
2. **Final response JSON schema** — signed off by Backend and Frontend.
3. **Credibility endpoint schema** — signed off by AI Pipeline and DE.
4. **`.env` variable names** — listed and shared.
5. **Log schema** — defined by DE, shared with all.

**Phase 0 exit condition:** A single shared document exists containing all five agreements. Every team member has read and acknowledged it.

---

## Phase 1 — Infrastructure First

These tasks must be completed before the integration phase. Parallel work is possible within Phase 1.

| Task                                | Role     | Depends On         | Can Run In Parallel With  |
| ----------------------------------- | -------- | ------------------ | ------------------------- |
| Docker Compose skeleton             | DE       | Phase 0            | —                         |
| Qdrant setup + endpoints            | DE       | Docker skeleton    | PostgreSQL setup          |
| PostgreSQL + credibility DB seed    | DE       | Docker skeleton    | Qdrant setup              |
| Behavior logging table              | DE       | PostgreSQL         | Qdrant                    |
| FastAPI app scaffold + stub         | Backend  | Phase 0            | All DE tasks              |
| Chrome extension scaffold           | Frontend | Phase 0            | All DE tasks              |

**Phase 1 exit condition:** `docker compose up` brings Qdrant and PostgreSQL to healthy state. Backend stub returns a hardcoded response. Extension scaffold loads in Chrome without errors.

---

## Phase 2 — Core Logic

Most work in Phase 2 can proceed in parallel. Cross-role dependencies are highlighted.

| Task                                  | Role         | Depends On                       | Status      |
| ------------------------------------- | ------------ | -------------------------------- | ----------- |
| Preprocessing (language normalization)| AI Pipeline  | Phase 0                          | ✅ Done (Step 8) |
| Query generation function             | AI Pipeline  | Preprocessing                    | ✅ Done     |
| Serper search integration             | AI Pipeline  | Phase 0 (API key)                | ✅ Done     |
| Credibility filtering                 | AI Pipeline  | DE credibility endpoint (Phase 1) | ✅ Done (interim JSON; will cut over to DE endpoint) |
| Content fetching                      | AI Pipeline  | Phase 0                          | ✅ Done     |
| LLM analysis + verdict synthesis      | AI Pipeline  | Content fetching                 | ✅ Done     |
| Public `analyze()` entry point        | AI Pipeline  | All sub-stages                   | ✅ Done (Step 8) |
| Interim disk cache                    | AI Pipeline  | Synthesizer                      | ✅ Done (to be replaced) |
| Cache check logic                     | Backend      | Qdrant ready (Phase 1)           | Pending     |
| AI Pipeline orchestration in Backend  | Backend      | AI Pipeline complete             | Pending — *unblocked* |
| Text highlight detection              | Frontend     | Extension scaffold               | Pending     |
| Icon display                          | Frontend     | Highlight detection              | Pending     |
| Loading state panel                   | Frontend     | Extension scaffold               | Pending     |
| Result display panel                  | Frontend     | Final JSON schema agreed         | Pending     |

**Phase 2 exit condition:** Each role has a working, tested unit in isolation. ✅ AI Pipeline complete and tested end-to-end. Backend `/analyze` calls the pipeline and returns a response (pending). Extension sends a request and renders a response (pending).

---

## Phase 3 — Integration

All roles integrate in this strict order:

1. **DE ↔ AI Pipeline:** AI Pipeline cuts over from the bundled MBFC JSON to the live `/credibility` endpoint. Single change in `credibility_filter._load_db()`.
2. **AI Pipeline ↔ Backend:** Backend imports `ai_core.analyze`. Verify verdict flows through.
3. **Backend ↔ DE Cache:** Backend stores and retrieves results via Qdrant. At this point, the in-process disk cache in `ai_core` is removed (or kept disabled).
4. **Backend ↔ Frontend:** Extension sends a real request to the running Backend. Verify full flow from highlight to rendered panel.

**Phase 3 exit condition:** A complete end-to-end test — highlight text on VnExpress, click icon, receive verdict in panel — works on at least one real article. Cache hit path verified (second request for same text returns in < 1 second).

---

## Phase 4 — Hardening

- Error scenario testing for all failure cases listed in this spec.
- Latency measurement against the targets defined per stage.
- Vietnamese domain credibility DB expanded to at least 100 entries.
- Documentation updated.

---

# 5. Appendix — Data Models

> **Implementation note:** The AI Pipeline uses **Pydantic** models (not dataclasses). Field shapes match this table; access is via attribute (`result.verdict`) or `.model_dump()` for JSON serialization.

## `AnalysisResult` (AI Pipeline output → Backend response)

| Field         | Type            | Notes                                  |
| ------------- | --------------- | -------------------------------------- |
| `verdict`     | `Verdict` enum  | `TRUE` / `FALSE` / `UNVERIFIED` / `NOT_SURE` |
| `explanation` | string          | Free text, max 500 chars               |
| `sources`     | `List[Source]`  | See Source model below                 |
| `confidence`  | `ConfidenceLevel` enum | `HIGH` / `MEDIUM` / `LOW`        |
| `cached`      | boolean         | `true` if served from cache            |

## `Source`

| Field               | Type             | Notes                                      |
| ------------------- | ---------------- | ------------------------------------------ |
| `url`               | string           | Full URL                                   |
| `domain`            | string           | e.g. `vnexpress.net`                       |
| `title`             | string           | Article headline                           |
| `credibility_score` | float            | 0.0 – 1.0                                  |
| `stance`            | `Stance` enum    | `SUPPORTS` / `CONTRADICTS` / `NEUTRAL`     |
| `published_at`      | `datetime` \| `None` | UTC; null if not extractable           |

## Intermediate pipeline types (internal to AI Pipeline)

These are not exposed to Backend, but documented for traceability:

- `SearchResult` — raw search result (url, title, snippet, domain)
- `ScoredResult` — SearchResult + credibility_score (after filtering)
- `FetchedArticle` — ScoredResult + body + published_at (after fetching)

## `CacheRecord` (Qdrant — when delivered)

| Field         | Type        | Notes                                    |
| ------------- | ----------- | ---------------------------------------- |
| `id`          | UUID        | Unique record identifier                 |
| `embedding`   | float[]     | Dimension per agreed model               |
| `verdict`     | string      | Stored verdict                           |
| `explanation` | string      | Stored explanation                       |
| `sources`     | JSON string | Serialized sources array                 |
| `created_at`  | ISO 8601    | Timestamp                                |

## `SourceRecord` (PostgreSQL)

| Field               | Type           | Notes                          |
| ------------------- | -------------- | ------------------------------ |
| `domain`            | string (PK)    | Primary key                    |
| `credibility_score` | float          | 0.0 – 1.0                      |
| `category`          | string         | e.g. National News, Tabloid    |
| `last_updated`      | date           | Last manual review date        |

## `PipelineLog` (PostgreSQL)

| Field              | Type            | Notes                                       |
| ------------------ | --------------- | ------------------------------------------- |
| `id`               | UUID            | Unique log entry                            |
| `input_hash`       | string          | SHA-256 of input text                       |
| `timestamp`        | ISO 8601        | Request time                                |
| `steps_completed`  | string[]        | e.g. `[preprocess, search, filter, fetch, llm]` |
| `verdict`          | string          | Final verdict                               |
| `error_stage`      | string \| null  | Stage where failure occurred                |
| `error_message`    | string \| null  | Error detail                                |
| `response_time_ms` | integer         | Total processing time                       |

---

*Version 1.1 — Updated 2026-05-21 to reflect AI Pipeline implementation through Step 8.*
*All numeric thresholds (similarity, credibility score, latency targets) remain initial proposals — to be confirmed by the team in Phase 0 for the remaining stages.*
