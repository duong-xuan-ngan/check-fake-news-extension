# Solution Architecture — Fake News Detection Browser Extension

**Project:** Check Fake News Extension
**Author:** Ngan — AI Pipeline Engineer
**Last updated:** 2026-05-18

---

## 1. Overview

A Chrome browser extension that lets users highlight suspicious text on social media (Facebook, Threads) and receive a structured fact-check verdict in a sidepanel. The system is composed of four logical layers:

1. **Chrome Extension** — sidepanel UI, captures highlighted text.
2. **Backend (FastAPI)** — receives requests, manages cache, orchestrates the AI pipeline.
3. **AI Pipeline** — five-stage fact-checking engine.
4. **External services** — Serper (web search), MBFC (credibility database), Gemini (LLM analysis).

The system is optimized for two goals:

- **Low latency on repeat queries** via a Redis cache keyed on the highlighted text.
- **Graceful degradation** — failures at any pipeline stage produce a meaningful verdict (`UNVERIFIED` / `NOT_SURE`) rather than crashing the request.

---

## 2. Architecture diagram

```
                          ┌───────────────────────────────┐
                          │       Chrome extension        │
                          │     (sidepanel UI · React)    │
                          └──────────────┬────────────────┘
                                         │
                                         │  POST /analyze
                                         │  { "text": "<highlighted>" }
                                         ▼
                          ┌───────────────────────────────┐
                          │       Backend · FastAPI       │     check       ┌─────────────┐
                          │   Receives · Orchestrates     │ ───────────────▶│    Redis    │
                          │       Returns verdict         │ ◀───────────────│  Cache (TTL)│
                          └──────────────┬────────────────┘    hit / miss   └──────┬──────┘
                                         │                                          │
                                         │ cache miss                               │ store result
                                         ▼                                          │
        ┌─────────────────────────────────────────────────────────┐                 │
        │                       AI PIPELINE                        │                 │
        │                                                          │                 │
        │   ┌──────────────────────────────┐                       │                 │
        │   │       query_builder          │                       │                 │
        │   │  str → search query (≤90c)   │                       │                 │
        │   └──────────────┬───────────────┘                       │                 │
        │                  ▼                                       │                 │
        │   ┌──────────────────────────────┐    ┌──────────────┐   │                 │
        │   │          searcher            │ ◀─▶│  Serper API  │   │                 │
        │   │  query → SearchResult ×10    │    │  Web search  │   │                 │
        │   └──────────────┬───────────────┘    └──────────────┘   │                 │
        │                  ▼                                       │                 │
        │   ┌──────────────────────────────┐    ┌──────────────┐   │                 │
        │   │     credibility_filter       │ ◀─▶│ MBFC dataset │   │                 │
        │   │  drops score < 0.5           │    │ (local JSON) │   │                 │
        │   │  → ScoredResult              │    └──────────────┘   │                 │
        │   └──────────────┬───────────────┘                       │                 │
        │                  ▼                                       │                 │
        │   ┌──────────────────────────────┐                       │                 │
        │   │          fetcher             │                       │                 │
        │   │  downloads body via          │                       │                 │
        │   │  newspaper3k (≤3000 chars)   │                       │                 │
        │   │  → FetchedArticle            │                       │                 │
        │   └──────────────┬───────────────┘                       │                 │
        │                  ▼                                       │                 │
        │   ┌──────────────────────────────┐    ┌──────────────┐   │                 │
        │   │        synthesizer           │ ◀─▶│  Gemini API  │   │                 │
        │   │  evidence → AnalysisResult   │    │  Structured  │   │                 │
        │   │  (verdict, explanation,      │    │  output JSON │   │                 │
        │   │   sources, confidence)       │    └──────────────┘   │                 │
        │   └──────────────┬───────────────┘                       │                 │
        │                  │                                       │                 │
        └──────────────────┼───────────────────────────────────────┘                 │
                           │                                                          │
                           └─────── AnalysisResult ──────────────────────────────────┘
                                         │
                                         ▼
                          (returned to Backend → Chrome extension)
```

---

## 3. Components

### 3.1 Chrome extension

| Property | Value |
|---|---|
| **Tech** | Vanilla JS / React, Chrome Extension Manifest V3 |
| **UI surface** | Sidepanel |
| **Triggers** | User selects text on any page → clicks extension icon |
| **Sends** | `POST /analyze` with `{ "text": "<highlighted>" }` |
| **Receives** | `AnalysisResult` object |
| **Displays** | Verdict badge, explanation, source list with credibility bars, confidence level |

**Why it exists:** Native browser integration is the only way to capture *selected* text on third-party sites without users copy-pasting. The sidepanel keeps the verdict visible while the user continues reading.

---

### 3.2 Backend (FastAPI)

| Property | Value |
|---|---|
| **Tech** | Python 3.11, FastAPI, Uvicorn |
| **Endpoint** | `POST /analyze` |
| **Responsibilities** | Validate input · check cache · invoke pipeline · cache result · return verdict |
| **Cache key** | `sha256(highlighted_text)` |
| **Cache TTL** | 24 hours (configurable) |

**Why it exists:** Thin orchestration layer. Keeps API keys (Serper, Gemini) off the client, gives a single place to enforce rate limits and observability, and decouples the extension from pipeline implementation.

---

### 3.3 Redis cache

| Property | Value |
|---|---|
| **Tech** | Redis 7 (single-node for dev, managed for prod) |
| **Schema** | `key = sha256(text)`, `value = AnalysisResult JSON` |
| **TTL** | 24 hours |

**Why it exists:** The same misleading headline is often shared by many users in a short window. Caching by hashed text means the second user gets an instant answer and the system avoids paying Serper + Gemini twice for identical content. Cached results carry `cached: true` in the response so the UI can label them.

---

### 3.4 AI pipeline

Five sequential stages. Each stage has a strict input/output contract from `ai_core/schema.py`.

| # | Stage | Input | Output | External dep | Status |
|---|---|---|---|---|---|
| 1 | `query_builder` | `str` (highlighted text) | `str` (search query) | — | ✅ Done |
| 2 | `searcher` | `str` (query) | `List[SearchResult]` (10) | Serper API | ✅ Done |
| 3 | `credibility_filter` | `List[SearchResult]` | `List[ScoredResult]` (filtered) | MBFC dataset | ✅ Done |
| 4 | `fetcher` | `List[ScoredResult]` | `List[FetchedArticle]` | newspaper3k | ⬅️ In progress |
| 5 | `synthesizer` | `List[FetchedArticle]` + original text | `AnalysisResult` | Gemini API | ⬜ Todo |

**Data shape evolution:**

```
str
  → SearchResult     (url, title, snippet, domain)
  → ScoredResult     (+ credibility_score)
  → FetchedArticle   (+ body ≤ 3000 chars, – snippet)
  → Source           (+ stance, – body)
  → AnalysisResult   (verdict, explanation, sources, confidence, cached)
```

---

#### 3.4.1 `query_builder`

Turns conversational or context-laden highlighted text into a clean search query suitable for Serper.

**Why it exists:** Highlighted text often contains pronouns, emojis, or quoted speech that hurt search recall. A focused query yields more relevant evidence.

---

#### 3.4.2 `searcher`

Calls Serper API, returns top 10 results as `SearchResult(url, title, snippet, domain)`.

**Why it exists:** A claim is only fact-checkable against external evidence. Serper provides a fast, structured Google search proxy with predictable rate limits.

**Failure mode:** Serper returns 0 results → pipeline short-circuits and Backend returns `verdict=UNVERIFIED, confidence=LOW`.

---

#### 3.4.3 `credibility_filter`

For each `SearchResult`, looks up the `domain` in the MBFC credibility dataset, attaches a `credibility_score` in `[0, 1]`, then drops any result with score `< 0.5`.

**Why it exists:** Not all sources are equally trustworthy. Filtering by credibility before fetching avoids wasting bandwidth on low-quality articles and prevents the LLM from being influenced by unreliable evidence.

**Failure mode:** All results filtered out → pipeline short-circuits and Backend returns `verdict=UNVERIFIED`.

---

#### 3.4.4 `fetcher`

For each surviving `ScoredResult`, downloads the article body using `newspaper3k`, capped at 3000 characters. Snippet is replaced by the full body.

**Why it exists:** Snippets are 1–2 sentences — too thin to support a real verdict. Full article text lets the synthesizer reason over actual claims, not search-engine teasers.

**Failure mode:** Per-article failure (timeout, paywall, JS-rendered page) → fall back to the existing `snippet` for that result. Continue with remaining articles. Only fail the whole pipeline if *every* article fails.

---

#### 3.4.5 `synthesizer`

Sends the highlighted text + all `FetchedArticle` evidence to Gemini with a structured-output schema. Gemini returns:

- A `verdict` ∈ {TRUE, FALSE, UNVERIFIED, NOT_SURE}
- An `explanation` (≤ 500 chars)
- For each source, a `stance` ∈ {SUPPORTS, REFUTES, NEUTRAL}
- A `confidence` ∈ {HIGH, MEDIUM, LOW}

**Why it exists:** This is the actual reasoning step. Everything before it is *evidence collection*; this is the *judgement*. Using Gemini with structured output guarantees a parseable response shape and removes the need for brittle text post-processing.

**Failure mode:** Gemini call fails → return `verdict=NOT_SURE, confidence=LOW` with the partial source list.

---

### 3.5 External services

| Service | Purpose | Failure handling |
|---|---|---|
| **Serper API** | Google search results, JSON | `UNVERIFIED` on 0 results / 5xx |
| **MBFC dataset** | Per-domain credibility scores (local JSON, refreshable) | `score = 0.5` (neutral) for unknown domains |
| **Gemini API** | LLM reasoning + structured output | `NOT_SURE` on 5xx or schema-mismatch |

---

## 4. Data contracts

```python
# ai_core/schema.py

class SearchResult:
    url: str
    title: str
    snippet: str
    domain: str

class ScoredResult(SearchResult):
    credibility_score: float          # [0, 1]

class FetchedArticle:
    url: str
    title: str
    domain: str
    credibility_score: float
    body: str                         # ≤ 3000 chars

class Source:
    url: str
    domain: str
    credibility_score: float
    stance: Literal["SUPPORTS", "REFUTES", "NEUTRAL"]

class AnalysisResult:
    verdict: Literal["TRUE", "FALSE", "UNVERIFIED", "NOT_SURE"]
    explanation: str                  # ≤ 500 chars
    sources: list[Source]
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    cached: bool
```

---

## 5. End-to-end request lifecycle

**Scenario:** User on Facebook highlights the headline *"Scientists confirm 5G causes COVID-19"* and clicks the extension icon.

1. **Extension** captures the selection via `window.getSelection()`, sends `POST /analyze` to the backend with the text in the body.
2. **Backend** hashes the text (`sha256`) and queries Redis.
3. **Cache miss** → backend invokes the AI pipeline.
4. **`query_builder`** rewrites the text into a clean query, e.g. `"5G cause COVID-19 scientific evidence"`.
5. **`searcher`** calls Serper → returns 10 results including BBC, Reuters, two health-misinformation blogs, etc.
6. **`credibility_filter`** scores each via MBFC: BBC (0.95), Reuters (0.95), misinformation blogs (0.2) → blogs dropped.
7. **`fetcher`** downloads the body of each surviving article via newspaper3k.
8. **`synthesizer`** sends the original claim + evidence to Gemini, which returns `verdict=FALSE`, `confidence=HIGH`, with each source's stance labeled.
9. **Backend** stores the `AnalysisResult` in Redis with a 24h TTL, then returns it to the extension.
10. **Extension** renders the verdict in the sidepanel: red "FALSE" badge, explanation, list of refuting sources.

A second user highlighting the same headline within 24h hits step 3 with a cache hit and gets the verdict in <100ms.

---

## 6. Failure-handling matrix

| Failure point | Behaviour | User-visible verdict |
|---|---|---|
| Empty / very short highlighted text | Reject at backend with 400 | — |
| Serper returns 0 results | Skip remaining pipeline | `UNVERIFIED · LOW` |
| All sources filtered out by credibility | Skip remaining pipeline | `UNVERIFIED · LOW` |
| Per-article fetch failure | Fall back to snippet | (pipeline continues) |
| All article fetches fail | Skip synthesis | `UNVERIFIED · LOW` |
| Gemini API failure | Return early | `NOT_SURE · LOW` |
| Gemini returns schema-invalid JSON | Return early | `NOT_SURE · LOW` |

**Design principle:** the pipeline never crashes the request. Every failure path produces a valid `AnalysisResult` that the UI can render.

---

## 7. Open questions / future work

- **Async pipeline** — should pipeline stages run in parallel where independent (e.g. fetching multiple articles concurrently)? Likely yes for `fetcher`.
- **Vector cache** — the current cache requires exact text match. A semantic cache (embed text, ANN lookup) would hit on rephrasings.
- **Stance disagreement** — when sources disagree, the synthesizer currently picks a verdict but doesn't surface the disagreement to the UI. A future version could show "sources are split."
- **Multilingual** — current pipeline assumes English. Vietnamese support would require a Vietnamese-language MBFC equivalent or alternative credibility signal.

---

## 8. File layout

```
ai_core/
├── schema.py                        ✅
└── pipeline/
    ├── query_builder.py             ✅
    ├── searcher.py                  ✅
    ├── credibility_filter.py        ✅
    ├── fetcher.py                   ⬅️ in progress
    └── synthesizer.py               ⬜ todo
backend/
├── main.py                          (FastAPI app)
├── routes/analyze.py                (POST /analyze)
└── cache.py                         (Redis wrapper)
extension/
├── manifest.json
├── sidepanel.html / .js
└── content_script.js                (capture selection)
```
