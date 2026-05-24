# Solution Architecture — Fake News Detection Browser Extension

**Project:** Check Fake News Extension
**Author:** Ngan — AI Pipeline Engineer
**Last updated:** 2026-05-21

---

## 1. Overview

A Chrome browser extension that lets users highlight suspicious text on social media (Facebook, Threads) and receive a structured fact-check verdict in a sidepanel. The system is composed of four logical layers:

1. **Chrome Extension** — sidepanel UI, captures highlighted text.
2. **Backend (FastAPI)** — receives requests, manages cache, orchestrates the AI pipeline.
3. **AI Pipeline** — six-stage fact-checking engine.
4. **External services** — Serper (web search), MBFC dataset (credibility data), OpenRouter (LLM reasoning).

The system is optimized for two goals:

- **Low latency on repeat queries** via a cache keyed on the normalized English claim.
- **Graceful degradation** — failures at any pipeline stage produce a meaningful verdict (`UNVERIFIED` / `NOT_SURE`) rather than crashing the request. The pipeline **never raises** to the Backend; every failure mode returns a valid `AnalysisResult`.

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
                          │       Backend · FastAPI       │
                          │  Receives · Validates · Logs  │
                          │     (Qdrant cache: v2)        │
                          └──────────────┬────────────────┘
                                         │
                                         │ ai_core.analyze(text)
                                         ▼
        ┌──────────────────────────────────────────────────────────┐
        │                       AI PIPELINE                        │
        │                                                          │
        │   ┌──────────────────────────────┐                       │
        │   │       preprocessor           │                       │
        │   │  raw text (any lang)         │                       │
        │   │   → english_claim            │     LLM call only     │
        │   │   (LLM call if non-English)  │     for non-English   │
        │   └──────────────┬───────────────┘                       │
        │                  ▼                                       │
        │   ┌──────────────────────────────┐                       │
        │   │       cache (interim)        │ ──── hit ────┐        │
        │   │  hash(english_claim)         │              │        │
        │   │  data/cache.json · 24h TTL   │ ──── miss ───┤        │
        │   └──────────────────────────────┘              │        │
        │                  │ miss                         │        │
        │                  ▼                              │        │
        │   ┌──────────────────────────────┐              │        │
        │   │       query_builder          │              │        │
        │   │  english_claim → search query│              │        │
        │   │  (3-layer fallback)          │              │        │
        │   └──────────────┬───────────────┘              │        │
        │                  ▼                              │        │
        │   ┌──────────────────────────────┐ ┌──────────┐ │        │
        │   │          searcher            │◀│  Serper  │ │        │
        │   │  query → SearchResult ×10    │ │ Web API  │ │        │
        │   └──────────────┬───────────────┘ └──────────┘ │        │
        │                  ▼                              │        │
        │   ┌──────────────────────────────┐ ┌──────────┐ │        │
        │   │     credibility_filter       │◀│   MBFC   │ │        │
        │   │  threshold 0.5 · dedup by    │ │  JSON    │ │        │
        │   │  domain → ScoredResult       │ │ (local)  │ │        │
        │   └──────────────┬───────────────┘ └──────────┘ │        │
        │                  ▼                              │        │
        │   ┌──────────────────────────────┐              │        │
        │   │          fetcher             │              │        │
        │   │  newspaper3k (+ bs4 fallback)│              │        │
        │   │  body ≤3000c · published_at  │              │        │
        │   │  → FetchedArticle            │              │        │
        │   └──────────────┬───────────────┘              │        │
        │                  ▼                              │        │
        │   ┌──────────────────────────────┐ ┌──────────┐ │        │
        │   │        synthesizer           │◀│OpenRouter│ │        │
        │   │  single LLM call · JSON mode │ │ (openrouter│        │
        │   │  → AnalysisResult            │ │ /auto)   │ │        │
        │   └──────────────┬───────────────┘ └──────────┘ │        │
        │                  ▼                              │        │
        │   ┌──────────────────────────────┐              │        │
        │   │      cache.set(...)          │              │        │
        │   └──────────────┬───────────────┘              │        │
        │                  │                              │        │
        └──────────────────┼──────────────────────────────┼────────┘
                           │                              │
                           └─── AnalysisResult ───────────┘
                                         │
                                         ▼
                          (returned to Backend → Chrome extension)
```

> The cache currently lives inside the AI Pipeline as an interim hash-based disk store. In v2 it will move to the Backend layer as a **Qdrant vector cache** owned by Data Engineering — see §3.3 and §7.

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
| **Displays** | Verdict badge, explanation, source list with credibility bars, confidence level, **publication date per source** |

**Why it exists:** Native browser integration is the only way to capture *selected* text on third-party sites without users copy-pasting. The sidepanel keeps the verdict visible while the user continues reading.

---

### 3.2 Backend (FastAPI)

| Property | Value |
|---|---|
| **Tech** | Python 3.11+, FastAPI, Uvicorn |
| **Endpoint** | `POST /analyze` |
| **Responsibilities** | Validate input · invoke pipeline · return verdict |
| **AI Pipeline call** | `from ai_core import analyze; result = analyze(text)` — single function call |
| **v2 cache** | Qdrant vector cache (vector similarity threshold ≥ 0.92) owned by DE |

**Why it exists:** Thin orchestration layer. Keeps API keys off the client, gives a single place to enforce rate limits and observability, and decouples the extension from pipeline implementation.

**Note on API keys:** AI Pipeline loads `SERPER_API_KEY` and `OPENROUTER_API_KEY` from its own `.env`. Backend does not pass keys.

---

### 3.3 Cache

The cache has two phases.

**Phase 1 (current, interim):** Hash-based disk cache inside the AI Pipeline.

| Property | Value |
|---|---|
| **Tech** | Plain JSON file at `data/cache.json` |
| **Owner** | AI Pipeline (`ai_core/cache.py`) |
| **Key** | `sha256(english_claim.lower().strip())` |
| **Value** | Serialized `AnalysisResult` |
| **TTL** | 24 hours · pruned on every write |

**Phase 2 (v2, planned):** Qdrant vector cache, owned by DE.

| Property | Value |
|---|---|
| **Tech** | Qdrant (Docker) |
| **Owner** | Data Engineering — accessed by Backend, not AI Pipeline |
| **Key** | Embedding of `english_claim` (model TBD in Phase 0 of integration) |
| **Match** | Cosine similarity ≥ 0.92 |
| **Value** | `AnalysisResult` JSON + metadata |

**Why two phases:** the interim hash cache is a single-file workable solution to ship the pipeline without blocking on DE infrastructure. The Qdrant migration solves two problems the hash cache cannot:
- **LLM translation non-determinism** — two runs of the same Vietnamese input can produce slightly different English translations, breaking hash equality. Embeddings are robust to such jitter (near-identical vectors).
- **Semantic deduplication** — paraphrased claims ("Messi joined Inter Miami" vs "Messi is at Inter Miami") land near each other in vector space and share a cache hit.

When Qdrant lands, the cache check moves from inside `ai_core.analyze()` to Backend orchestration, and `ai_core/cache.py` is removed.

---

### 3.4 AI pipeline

Six sequential stages. Each stage has a strict input/output contract from `ai_core/schema.py`.

| # | Stage | Input | Output | External dep | Status |
|---|---|---|---|---|---|
| 0 | `preprocessor` | `str` (raw text, any language) | `str` (`english_claim`) | OpenRouter (LLM, only when non-English) | ✅ Done |
| 1 | `query_builder` | `str` (`english_claim`) | `str` (search query) | OpenRouter (LLM, only for medium-long claims) | ✅ Done |
| 2 | `searcher` | `str` (query) | `List[SearchResult]` (≤10) | Serper API | ✅ Done |
| 3 | `credibility_filter` | `List[SearchResult]` | `List[ScoredResult]` (filtered + deduped) | MBFC JSON | ✅ Done |
| 4 | `fetcher` | `List[ScoredResult]` | `List[FetchedArticle]` | newspaper3k + BeautifulSoup | ✅ Done |
| 5 | `synthesizer` | `english_claim` + `List[FetchedArticle]` | `AnalysisResult` | OpenRouter (LLM, JSON mode) | ✅ Done |

**Data shape evolution:**

```
str (raw, any language)
  → str (english_claim — translated if needed)
  → SearchResult       (url, title, snippet, domain)
  → ScoredResult       (url, title, snippet, domain, credibility_score)
  → FetchedArticle     (url, title, domain, credibility_score, body ≤3000c, published_at)
  → Source             (url, title, domain, credibility_score, stance, published_at)
  → AnalysisResult     (verdict, explanation, sources, confidence, cached)
```

Note that intermediate types (`SearchResult`, `ScoredResult`, `FetchedArticle`) are independent Pydantic models — not subclasses. Each models exactly what is known at that stage, with no placeholder fields.

---

#### 3.4.0 `preprocessor` (added in Step 8)

Normalizes raw input to a clean English claim before any other pipeline stage runs.

**Why it exists:** Vietnamese and other non-English inputs are common, but downstream stages (search, credibility, synthesis) are most reliable on English. Pulling translation out into its own stage means every downstream stage has one stable input language, and the cache key (and future embedding) is computed on a normalized representation.

**Logic:**
- A regex heuristic (`is_english`) detects whether the input is already English (ASCII letters + common punctuation). If yes, skip the LLM.
- If not English, one OpenRouter call translates with a narrow prompt: preserve entities, numbers, and dates verbatim; return text only.
- On any LLM failure, fall back to the cleaned original — pipeline continues; downstream stages will likely produce `NOT_SURE` if the input was unsearchable, which is the correct degradation.

**Cost:** zero LLM calls for English input, one for non-English.

---

#### 3.4.1 `query_builder`

Turns the English claim into a clean Serper search query.

**Why it exists:** Long or conversational claims hurt search recall. A focused keyword query yields more relevant evidence.

**Three-layer fallback:**
1. **Pass-through** — if the claim is already ≤10 words, return it as-is (no LLM call).
2. **LLM rewrite** — OpenRouter call with a constrained prompt: keyword-focused, ≤15 words, preserve entities.
3. **Regex entity extraction** — capitalized tokens + numbers, used only if the LLM fails.

---

#### 3.4.2 `searcher`

Calls Serper API, returns top 10 results as `SearchResult(url, title, snippet, domain)`.

**Why it exists:** A claim is only fact-checkable against external evidence. Serper is a fast, structured Google-search proxy with predictable rate limits.

**Failure mode:** Serper returns 0 results or times out → empty list propagates; pipeline ultimately returns `NOT_SURE · LOW`.

---

#### 3.4.3 `credibility_filter`

Looks up each result's domain in the MBFC credibility dataset, attaches a `credibility_score` in `[0, 1]`, drops any result with score `< 0.5`, and **deduplicates by domain** (first occurrence wins).

**Why it exists:** Not all sources are equally trustworthy. Filtering by credibility before fetching avoids wasting bandwidth on low-quality articles and prevents the LLM from being influenced by unreliable evidence. Deduplication avoids over-weighting a single outlet that happens to rank multiple times for the same query.

**Subdomain fallback:** if `en.wikipedia.org` is not in the DB, the filter retries with `wikipedia.org`.

**Known MBFC quirk:** platforms like `facebook.com` and `youtube.com` score 0.9 (rated as publishers in MBFC). The fetcher typically can't extract usable bodies from these anyway, so they self-exclude downstream.

**Failure mode:** All results filtered out → empty list propagates; pipeline returns `NOT_SURE · LOW`.

**Future:** when DE delivers `GET /credibility?domain=`, only `_load_db()` changes — JSON file removed.

---

#### 3.4.4 `fetcher`

For each surviving `ScoredResult`, downloads the article body using `newspaper3k`, with a `requests` + BeautifulSoup fallback. Body is truncated at 3000 characters. Also extracts `published_at: Optional[datetime]` via three strategies (meta tags → JSON-LD → `<time>` element).

**Why it exists:** Snippets are 1–2 sentences — too thin to support a real verdict. Full article text lets the synthesizer reason over actual claims, not search-engine teasers. Publication dates let the synthesizer apply a temporal rule when sources contradict each other.

**Failure mode:** Per-article failure (timeout, paywall, JS-rendered page, body < 150 chars) → skip that article and continue with the rest. **No fallback to snippet** — short or missing bodies are skipped entirely. If *every* article fails, the synthesizer receives an empty list and returns `NOT_SURE · LOW`.

---

#### 3.4.5 `synthesizer`

Sends the English claim + all `FetchedArticle` evidence to OpenRouter in a single LLM call with `response_format={"type": "json_object"}`. Returns a complete `AnalysisResult`.

**Why it exists:** This is the actual reasoning step. Everything before it is *evidence collection*; this is the *judgment*. A single call (rather than per-article calls) lets the LLM compare sources holistically and costs one API call instead of N.

**Anti-hallucination pattern (critical):** The LLM is asked to return only `article_index` (into the list we passed), stance, verdict, explanation, and confidence. URLs, titles, domains, credibility scores, and `published_at` are filled in from our own `FetchedArticle` data — never echoed by the LLM. This eliminates a major hallucination surface with zero benefit.

**Structured chain-of-thought:** The prompt forces the LLM to write `claim_in_article` and `user_claim` as required JSON fields *before* picking a stance. The comparison is explicit and label confusion drops.

**Temporal rule:** When two sources directly contradict, the more recent `published_at` wins. Sources without dates cannot override sources with dates. The rule is narrow and mechanical — not a general "is this claim time-sensitive?" judgment, which would itself be a hallucination surface.

**Failure mode:** Empty articles list, LLM timeout, malformed JSON, or schema-invalid enum → return `NOT_SURE · LOW · sources=[]`.

---

### 3.5 External services

| Service | Purpose | Failure handling |
|---|---|---|
| **Serper API** | Google search results, JSON | Empty list propagates → `NOT_SURE · LOW` |
| **MBFC dataset** | Per-domain credibility scores (local JSON, refreshable via `scripts/build_mbfc.py`) | Domain not found → result dropped (does not pass threshold) |
| **OpenRouter** (preprocessor) | Vietnamese → English translation | Fall back to cleaned original |
| **OpenRouter** (query_builder) | Claim → keyword query | Fall back to regex entity extraction |
| **OpenRouter** (synthesizer) | Evidence → verdict + reasoning | `NOT_SURE · LOW` on any failure |

All OpenRouter calls go through the same OpenAI-compatible client targeting `https://openrouter.ai/api/v1` with model `openrouter/auto`. Temperature 0.1 across all three call sites.

---

## 4. Data contracts

```python
# ai_core/schema.py  (Pydantic models)

class SearchResult(BaseModel):
    url: str
    title: str
    snippet: str
    domain: str

class ScoredResult(BaseModel):
    url: str
    title: str
    snippet: str
    domain: str
    credibility_score: float          # [0, 1]

class FetchedArticle(BaseModel):
    url: str
    domain: str
    title: str
    body: str                         # ≤ 3000 chars
    credibility_score: float
    published_at: Optional[datetime]  # UTC; None if unextractable

class Source(BaseModel):
    url: str
    domain: str
    title: str
    credibility_score: float
    stance: Stance                    # SUPPORTS | CONTRADICTS | NEUTRAL
    published_at: Optional[datetime]

class AnalysisResult(BaseModel):
    verdict: Verdict                  # TRUE | FALSE | UNVERIFIED | NOT_SURE
    explanation: str                  # ≤ 500 chars
    sources: List[Source]
    confidence: ConfidenceLevel       # HIGH | MEDIUM | LOW
    cached: bool
```

> Note: each intermediate type holds exactly the fields known at that stage, with no placeholders. Design principle: **no lying types.**

---

## 5. End-to-end request lifecycle

**Scenario:** User on Facebook highlights the Vietnamese headline *"Florentino Perez là chủ tịch của FC Barcelona"* and clicks the extension icon.

1. **Extension** captures the selection via `window.getSelection()`, sends `POST /analyze` to the backend with the text in the body.
2. **Backend** validates length and calls `ai_core.analyze(text)`.
3. **`preprocessor`** — `is_english()` returns False (Vietnamese diacritics detected); one LLM call translates → `"Florentino Perez is the president of FC Barcelona"`.
4. **Cache lookup** — `sha256` of the English claim → checks `data/cache.json` → miss.
5. **`query_builder`** — claim is 8 words (≤10), so Layer 1 passes it through unchanged. No LLM call.
6. **`searcher`** calls Serper → returns 10 results including ESPN, Wikipedia, Yahoo Sports, Facebook, and a few others.
7. **`credibility_filter`** scores each domain via MBFC; drops domains below 0.5 and deduplicates → ESPN (0.9), Wikipedia (0.5), Yahoo Sports (0.9) survive.
8. **`fetcher`** downloads bodies via newspaper3k. ESPN exposes `datePublished` in JSON-LD → date extracted (`2026-05-13`). Wikipedia and Yahoo Sports also yield dates.
9. **`synthesizer`** sends the English claim + 3 articles to OpenRouter in one call with JSON mode. LLM returns: `verdict=FALSE`, `confidence=HIGH`, each source labeled `CONTRADICTS`, explanation citing that all sources name Perez as president of *Real Madrid*, not Barcelona.
10. **Cache store** — `AnalysisResult` is written to `data/cache.json` with current timestamp; expired entries are pruned.
11. **Backend** returns the `AnalysisResult` to the extension.
12. **Extension** renders the verdict in the sidepanel: red "FALSE" badge, explanation, three contradicting sources with credibility bars and publication dates.

A second user highlighting the same English headline within 24h will hit the cache at step 4 and get the verdict in <100ms. A second user highlighting the same Vietnamese headline may or may not hit cache, depending on whether the LLM's translation happens to be byte-identical — Qdrant fixes this in v2.

---

## 6. Failure-handling matrix

| Failure point | Behaviour | User-visible verdict |
|---|---|---|
| Empty / very short highlighted text | `analyze()` returns early with sentinel | `NOT_SURE · LOW` |
| Preprocessor LLM (translation) fails | Fall back to cleaned original text | (pipeline continues; downstream may degrade) |
| Query builder LLM fails | Fall back to regex entity extraction | (pipeline continues) |
| Serper returns 0 results | Empty list propagates | `NOT_SURE · LOW` |
| All sources filtered out by credibility | Empty list propagates | `NOT_SURE · LOW` |
| Per-article fetch failure | Skip that article and continue | (pipeline continues) |
| All article fetches fail | Synthesizer receives empty list | `NOT_SURE · LOW` |
| Synthesizer LLM call fails | Return early | `NOT_SURE · LOW` |
| Synthesizer returns malformed JSON | Pydantic validation fails → return early | `NOT_SURE · LOW` |
| Cache read/write fails | Logged; treated as miss; pipeline continues | (transparent to user) |

**Design principle:** the pipeline never crashes the request. Every failure path produces a valid `AnalysisResult` that the UI can render. `ai_core.analyze()` is guaranteed never to raise.

---

## 7. Open questions / future work

- **Qdrant vector cache migration.** Move caching from `ai_core/cache.py` to a Backend-owned Qdrant store. Solves LLM translation non-determinism and enables semantic deduplication across paraphrases and languages. Blocked on DE infrastructure.
- **Parallel fetching.** `fetcher` is currently sequential. Async + `asyncio.gather` would cut latency significantly when 3+ articles are fetched.
- **Atomic claim decomposition.** Multi-claim posts are currently collapsed into a single search query. A v2 splitter would individually verify each sub-claim.
- **Single-source confidence inflation.** When only one article survives fetching, the synthesizer often still returns `HIGH` confidence. Open question whether to enforce a hard rule in the prompt or accept LLM judgment.
- **Model selection.** `openrouter/auto` routes across providers, which produces variable stance-label noise. Worth comparing against a pinned model if user-facing problems emerge.
- **Stance disagreement surfacing.** When sources are genuinely split, the UI currently flattens this to a single verdict. A future version could expose "sources are split" with the stance breakdown.

---

## 8. File layout

```
ai_core/
├── __init__.py                      ✅ (public analyze() entry point)
├── schema.py                        ✅
├── cache.py                         ✅ (interim — moves to Backend in v2)
└── pipeline/
    ├── preprocessor.py              ✅ (new in Step 8)
    ├── query_builder.py             ✅
    ├── searcher.py                  ✅
    ├── credibility_filter.py        ✅
    ├── fetcher.py                   ✅
    └── synthesizer.py               ✅
data/
├── mbfc_credibility.json            (built by scripts/build_mbfc.py)
└── cache.json                       (created on first cache write)
scripts/
├── build_mbfc.py                    (one-time MBFC CSV → JSON)
└── test_pipeline.py                 (end-to-end smoke test)
backend/                             (pending)
├── main.py
└── routes/analyze.py
extension/                           (pending)
├── manifest.json
├── sidepanel.html / .js
└── content_script.js
```
