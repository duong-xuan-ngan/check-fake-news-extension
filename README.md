# Fake News Detector — System Specification & Team Execution Plan

> **Document type:** Pre-implementation specification
> **Status:** Draft — pending Phase 0 agreements
> **Note:** Numeric thresholds (similarity, credibility, latency) are initial proposals and must be confirmed by the team in Phase 0.

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
| `sources`     | array   | Each: `{ url, domain, credibility_score, title }`              |
| `cached`      | boolean | Always `true` on cache hit                                     |

**On cache miss:** `null` — Backend proceeds to AI Pipeline.

### 3. Internal State

- Similarity threshold for cache hit: agreed constant (proposed: **0.92 cosine similarity**).
- Threshold must be stored in DE config, not hardcoded in Backend.

### 4. Dependencies on Other Stages

- DE must have Qdrant running and the lookup API exposed **before** Backend can implement cache check.
- Embedding model selection must be agreed between Backend and DE (same model used for both storing and querying).

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

---

### Sub-step 2.1 — Query Generation

**1. Input Data:** Raw `text` string (the highlighted claim).

**2. Output Data:** A search query string, max 10 words, preserving names, numbers, and dates.

**3. Internal State:** None persisted.

**4. Dependencies:** None.

**5. Failure Cases:** If text contains no extractable keywords (e.g., pure punctuation), return `NOT_SURE` immediately without proceeding.

**6. Latency:** < 100 ms (in-process function).

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

**4. Dependencies:** Backend must provide `SERPER_API_KEY` as environment variable.

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

**2. Output Data:** Filtered list — only results where `credibility_score >= 0.60` are retained.

**3. Internal State:** None persisted. Credibility data lives in DE's PostgreSQL.

**4. Dependencies:** DE must expose `GET /credibility?domain=<domain>` returning `{ credibility_score, category }`.

**5. Failure Cases:**

| Failure                          | Expected Behavior                                                   |
| -------------------------------- | ------------------------------------------------------------------- |
| DE credibility API unreachable   | Fall back to a hardcoded allowlist of credible Vietnamese domains   |
| Domain not found in DB           | Assign neutral score of 0.5; include in fetch candidates            |
| All results filtered out         | Return `NOT_SURE`; log with reason `"no_credible_sources"`          |

**6. Latency:** < 500 ms total for batch domain lookups.

---

### Sub-step 2.4 — Content Fetching (Newspaper3k)

**1. Input Data:** Filtered list of URLs from 2.3 — max 5 URLs to limit latency.

**2. Output Data:** List of fetched article objects:

| Field               | Type                          |
| ------------------- | ----------------------------- |
| `url`               | string                        |
| `domain`            | string                        |
| `title`             | string                        |
| `body`              | string (max 3,000 chars)      |
| `credibility_score` | float (passed through from 2.3) |

**3. Internal State:** None persisted.

**4. Dependencies:** Filtered URL list from 2.3.

**5. Failure Cases:**

| Failure                     | Expected Behavior                                              |
| --------------------------- | -------------------------------------------------------------- |
| Fetch blocked (403/429)     | Skip URL; continue with remaining                              |
| JavaScript-rendered page    | Log as `"js_render_required"`; skip for v1; use Playwright in v2 |
| Fetch timeout (> 5s/URL)    | Skip URL                                                       |
| All fetches fail            | Return `NOT_SURE`; log with reason `"all_fetches_failed"`      |

**6. Latency:** Fetch up to 5 URLs in parallel; total fetch budget **< 6 seconds**.

---

### Sub-step 2.5 — LLM Analysis (Gemini API)

**1. Input Data:**

| Field              | Type                      |
| ------------------ | ------------------------- |
| `original_text`    | string (the user's claim) |
| `fetched_articles` | array of articles from 2.4 |

**2. Output Data (structured JSON from LLM):**

```json
{
  "verdict": "TRUE | FALSE | UNVERIFIED | NOT_SURE",
  "explanation": "string, max 500 chars",
  "supporting_sources": [
    {
      "url": "string",
      "domain": "string",
      "credibility_score": 0.0,
      "title": "string",
      "stance": "SUPPORTS | CONTRADICTS | NEUTRAL"
    }
  ],
  "confidence": "HIGH | MEDIUM | LOW"
}
```

**Prompt contract (to be finalized by AI Pipeline role):** Prompt must instruct Gemini to (a) determine whether the claim is supported, contradicted, or unverifiable based on provided articles; (b) output a structured JSON object — no free prose; (c) return `"NOT_SURE"` if evidence is ambiguous or insufficient.

**3. Internal State:** None persisted.

**4. Dependencies:** Backend must provide `GEMINI_API_KEY` as environment variable. Articles from 2.4.

**5. Failure Cases:**

| Failure                         | Expected Behavior                                                |
| ------------------------------- | ---------------------------------------------------------------- |
| Gemini rate limit               | Retry once after 2s; if fails again, return `NOT_SURE`           |
| LLM returns malformed JSON      | Retry once with stricter JSON instruction; if fails, `NOT_SURE`  |
| LLM timeout (> 10s)             | Abort; return `NOT_SURE`; log reason                             |
| LLM outputs forbidden verdict   | Validate enum on receipt; default to `NOT_SURE`                  |

**6. Latency:** < 8 seconds.

---

## Stage 3 — Result Return (Backend → Frontend)

### 1. Input Data

The full structured JSON from Sub-step 2.5.

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
      "credibility_score": 0.0,
      "title": "string",
      "stance": "SUPPORTS | CONTRADICTS | NEUTRAL"
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
  "failed_at_stage": "search | filter | fetch | llm | cache",
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
| Pipeline returns malformed verdict   | Return error response with `failed_at_stage = "llm"`           |
| Cache store fails                    | Log error; do not affect Frontend response (fire-and-forget)   |

### 6. Performance / Latency Expectations

| Path                            | Target                |
| ------------------------------- | --------------------- |
| Cache miss — full pipeline      | **< 15 seconds** end-to-end |
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
- Supplement with MBFC data where available for international domains.
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

**Definition of Done:** Sending `POST /analyze` with a test text returns a valid JSON response matching the spec schema in < 15 seconds. Invalid inputs return 400 with a descriptive error.

---

### Task 2 — Cache Check Integration

**Exact tasks:**
- Generate an embedding for the input text using the agreed embedding model.
- Call DE's Qdrant lookup endpoint.
- If cache hit: return result immediately to Frontend, skip AI pipeline.
- If cache miss: proceed to AI Pipeline.

**Deliverable:** Cache check logic implemented and tested with a pre-seeded Qdrant record.

**Definition of Done:** A request for a previously cached claim returns in < 1 second with `"cached": true` in the response.

---

### Task 3 — AI Pipeline Orchestration

**Exact tasks:**
- Call the AI Pipeline module with `{ text, serper_api_key, gemini_api_key }`.
- Receive structured result.
- Fire-and-forget: call DE's cache store endpoint asynchronously (do not await before responding to Frontend).
- Log the request via DE's logging endpoint.

**Deliverable:** Orchestration logic that ties cache miss → pipeline → store → respond in the correct order.

**Definition of Done:** Full end-to-end request (cache miss) completes and produces a correct response with `"cached": false`. Qdrant contains the new cached record after the request.

---

### Task 4 — API Key Management

**Exact tasks:**
- Load `SERPER_API_KEY`, `GEMINI_API_KEY` from environment variables only.
- Pass keys to AI Pipeline via function arguments, not global state.
- Verify at startup that required keys are present; crash with a clear error if missing.
- Add keys to `.env.example` (with placeholder values) for documentation.

**Deliverable:** Keys never appear in source code or logs. `.env.example` documents all required variables.

**Definition of Done:** Running the Backend with a missing key produces a startup error naming the missing variable, not a silent crash during a request.

---

### Task 5 — Error Handling & Response Normalization

**Exact tasks:**
- Catch all exceptions from the AI Pipeline and DE integrations.
- Return the standardized error response JSON (see Stage 3 spec) with `failed_at_stage` populated.
- Log all errors to DE's logging endpoint.
- Never expose raw stack traces to Frontend.

**Deliverable:** Error handling middleware in FastAPI.

**Definition of Done:** Simulating a Serper API failure returns `{ "error": "...", "failed_at_stage": "search", "verdict": "NOT_SURE" }` to the caller, not a 500 with a Python traceback.

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
- Panel must remain visible while the Backend processes (up to 15 seconds).
- Show a spinner or animated placeholder — not a blank panel.

**Deliverable:** Panel component with loading state distinct from result state.

**Definition of Done:** Clicking the icon always produces an immediate panel (< 200 ms). The panel remains visible for the full Backend response time.

---

### Task 5 — Result Display Panel

**Exact tasks:**
- Parse the Backend response JSON.
- Render Section 1: verdict label (color-coded: green/red/grey), confidence badge, explanation text.
- Render Section 2: sources list — each source shows domain, credibility score (as a bar or percentage), and stance label.
- Render the `NOT_SURE` state with neutral styling and text: "Insufficient evidence to determine credibility."
- Render the error state with a friendly message (no raw JSON shown to user).
- Panel must be dismissible (close button or click-outside).

**Deliverable:** Fully styled panel component covering success, not-sure, and error states.

**Definition of Done:** Given mock JSON for each of the four verdicts, the panel renders correctly. Panel is dismissible. No raw JSON or error codes visible to the user.

---

## 2.4 AI Pipeline

### Task 1 — Search Query Generation

**Exact tasks:**
- Write a function `generate_query(text: str) -> str` that extracts the most specific keywords from the input.
- Preserve named entities (people, organizations, locations), numbers, and dates.
- Strip filler phrases ("it is said that", "reportedly", etc.).
- Cap output at 10 words.

**Deliverable:** Tested Python function with at least 5 unit test cases covering different input types.

**Definition of Done:** Given "Chính phủ Việt Nam công bố GDP tăng 7.2% trong quý 3 năm 2024", the function returns a query containing "GDP 7.2% quý 3 2024".

---

### Task 2 — Web Search Integration

**Exact tasks:**
- Write a function `search(query: str, api_key: str) -> List[SearchResult]` that calls Serper API.
- Parse the response into a list of `SearchResult` objects with fields: `url`, `domain`, `title`, `snippet`.
- Extract domain from URL using Python's `urllib.parse`.
- Implement timeout (5s) and handle rate limit / empty results per the spec.

**Deliverable:** Function with integration test (using a real Serper key in a local `.env`).

**Definition of Done:** Function returns a non-empty list of results for a test query. Rate limit and timeout scenarios return an empty list with a logged reason, not an exception.

---

### Task 3 — Source Credibility Filtering

**Exact tasks:**
- Write a function `filter_by_credibility(results, de_api_url) -> List[SearchResult]` that calls DE's credibility endpoint for each domain.
- Retain only results with `credibility_score >= 0.60`.
- Implement fallback to hardcoded allowlist if DE API is unreachable.
- Hardcoded allowlist must be stored in a config file, not inline.

**Deliverable:** Function + hardcoded fallback allowlist file (`pipeline/config/credible_domains.json`).

**Definition of Done:** Function filters a test list correctly. With DE API mocked as unreachable, function falls back to allowlist without raising an exception.

---

### Task 4 — Content Fetching

**Exact tasks:**
- Write an async function `fetch_articles(urls: List[str]) -> List[Article]` that fetches up to 5 URLs in parallel using `asyncio`.
- Use `newspaper3k` as primary parser; fall back to `BeautifulSoup` if `newspaper3k` fails.
- Truncate body to 3,000 characters.
- Skip and log any URL that times out (5s), returns 4xx/5xx, or raises an exception.

**Deliverable:** Async fetch function with at least 3 test URLs covering success, failure, and timeout scenarios.

**Definition of Done:** Function fetches content from VnExpress and Tuổi Trẻ successfully. A 404 URL is skipped without crashing. Total fetch time for 5 URLs does not exceed 6 seconds.

---

### Task 5 — LLM Analysis and Verdict Synthesis

**Exact tasks:**
- Write a function `analyze(original_text, articles, api_key) -> Verdict` that calls Gemini API.
- Construct the prompt per the prompt contract defined in Stage 2.5 of this spec.
- Parse and validate the JSON response — enforce the enum values for `verdict` and `confidence`.
- Implement one retry on malformed JSON.
- Return a `Verdict` dataclass (not a raw dict) so Backend and tests have type safety.

**Deliverable:** Function + `Verdict` dataclass definition in `pipeline/models.py`. Prompt template stored in `pipeline/prompts/analyze.txt`.

**Definition of Done:** Function returns a valid `Verdict` for a test set of 3 articles (one supporting, one contradicting, one neutral). Malformed JSON from a mocked Gemini triggers one retry. `NOT_SURE` is returned when Gemini is mocked as timing out.

---

# 3. Cross-Role Dependencies

This section explicitly maps where roles must coordinate. Uncoordinated work at these points will cause integration failures.

| # | Dependency                       | Roles Involved      | What Must Be Agreed                                                            | When                                  |
| - | -------------------------------- | ------------------- | ------------------------------------------------------------------------------ | ------------------------------------- |
| 1 | Embedding model selection        | Backend + DE        | Model name (e.g. multilingual MiniLM), output dimension, library               | Before any code is written            |
| 2 | Cache similarity threshold       | Backend + DE        | Numeric value (proposed: 0.92); stored in DE config, read by Backend           | Before cache integration              |
| 3 | Credibility score threshold      | AI Pipeline + DE    | Minimum score to pass filter (proposed: 0.60); must match DE's seeded data     | Before filtering logic                |
| 4 | `/credibility` endpoint schema   | AI Pipeline + DE    | Exact URL, request format, response format, "not found" behavior               | Before AI Pipeline Task 3             |
| 5 | Final response JSON schema       | Backend + Frontend  | Exact field names, verdict enum values, sources array structure                | Before any UI code is written         |
| 6 | Backend URL configuration        | Frontend + Backend  | Local dev URL (`http://localhost:8000`); how it is configured in the extension | Before Frontend Task 3                |
| 7 | API keys in Docker               | Backend + DE        | Variable names in `.env`; which service owns key injection                     | Before Docker Compose is finalized    |
| 8 | Log schema                       | All roles           | JSON structure for log entries; which fields are mandatory                     | Before any service is built           |

> **Highest-risk dependency: #1 (Embedding model selection).** If Backend and DE implement independently with different models, the cache will never produce a valid hit. This is the one agreement that must happen first, before any code.

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

| Task                                  | Role         | Depends On                       | Can Run In Parallel With   |
| ------------------------------------- | ------------ | -------------------------------- | -------------------------- |
| Query generation function             | AI Pipeline  | Phase 0                          | All Phase 2 tasks          |
| Serper search integration             | AI Pipeline  | Phase 0 (API key)                | Query generation           |
| Credibility filtering                 | AI Pipeline  | DE credibility endpoint (Phase 1)| Fetch logic                |
| Content fetching                      | AI Pipeline  | Phase 0                          | Filtering logic            |
| LLM analysis + verdict synthesis      | AI Pipeline  | Content fetching                 | —                          |
| Cache check logic                     | Backend      | Qdrant ready (Phase 1)           | AI Pipeline logic          |
| AI Pipeline orchestration in Backend  | Backend      | AI Pipeline complete             | —                          |
| Text highlight detection              | Frontend     | Extension scaffold               | All other Frontend tasks   |
| Icon display                          | Frontend     | Highlight detection              | Backend request logic      |
| Loading state panel                   | Frontend     | Extension scaffold               | Icon display               |
| Result display panel                  | Frontend     | Final JSON schema agreed         | Loading state              |

**Phase 2 exit condition:** Each role has a working, tested unit in isolation. AI Pipeline returns a valid `Verdict` from a test input. Backend `/analyze` calls the pipeline and returns a response. Extension sends a request and renders a response.

---

## Phase 3 — Integration

All roles integrate in this strict order:

1. **DE ↔ AI Pipeline:** AI Pipeline queries the live credibility endpoint. Verify filtering works end-to-end.
2. **AI Pipeline ↔ Backend:** Backend calls the full pipeline module. Verify verdict flows through.
3. **Backend ↔ DE Cache:** Backend stores and retrieves results via Qdrant. Verify cache hit path.
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

## `Verdict` (AI Pipeline output / Backend response)

| Field         | Type          | Notes                                  |
| ------------- | ------------- | -------------------------------------- |
| `verdict`     | string        | `TRUE` / `FALSE` / `UNVERIFIED` / `NOT_SURE` |
| `explanation` | string        | Free text, max 500 chars               |
| `sources`     | list[Source]  | See Source model below                 |
| `confidence`  | string        | `HIGH` / `MEDIUM` / `LOW`              |
| `cached`      | boolean       | `true` if served from Qdrant cache     |

## `Source`

| Field               | Type   | Notes                                      |
| ------------------- | ------ | ------------------------------------------ |
| `url`               | string | Full URL                                   |
| `domain`            | string | e.g. `vnexpress.net`                       |
| `credibility_score` | float  | 0.0 – 1.0                                  |
| `title`             | string | Article headline                           |
| `stance`            | string | `SUPPORTS` / `CONTRADICTS` / `NEUTRAL`     |

## `CacheRecord` (Qdrant)

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
| `steps_completed`  | string[]        | e.g. `[search, filter, fetch, llm]`         |
| `verdict`          | string          | Final verdict                               |
| `error_stage`      | string \| null  | Stage where failure occurred                |
| `error_message`    | string \| null  | Error detail                                |
| `response_time_ms` | integer         | Total processing time                       |

---

*Version 1.0 — Specification phase. No code written yet.*
*All numeric thresholds (similarity, credibility score, latency targets) are initial proposals — to be confirmed by the team in Phase 0.*
