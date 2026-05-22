# AI Pipeline — Learning Progress & Session Log

> **Owner:** Ngan (AI Pipeline role)
> **Project:** Fake News Detector Browser Extension
> **Last updated:** 2026-05-21
> **Status:** Step 8 complete (`analyze()` integration, preprocessor lift-out, disk cache). Hash-based cache works but does not survive LLM-translation non-determinism — to be replaced by a Qdrant vector cache later. Pipeline functionally correct end-to-end.

---

## How to continue in a new chat

**Say this to Claude:**

> Read `D:\ThirdYear\second_semester\check-fake-news-extension\check-fake-new-extension\PROGRESS.md` and continue from where we left off.
>
> You have filesystem MCP access at `D:/ThirdYear/second_semester/check-fake-news-extension/`.

---

## Working style (current)

- Claude writes not too important boilerplate and structural code directly to the filesystem, left only core code and logic for Ngan (with the supporting from Claude).
- Ngan focuses on understanding the system — pipeline design, data flow, tradeoffs, prompting principles.
- Claude explains the system before writing code; asks short check questions on the core ideas, not on syntax.
- Ngan runs tests in the terminal and pastes output back. Claude diagnoses, then fixes.

---

## Pipeline overview

```
analyze(text: str) -> AnalysisResult

    ├── preprocessor.py         ✅ DONE  (new in Step 8)
    ├── cache.py                ✅ DONE  (new in Step 8 — to be replaced by Qdrant later)
    ├── query_builder.py        ✅ DONE
    ├── searcher.py             ✅ DONE
    ├── credibility_filter.py   ✅ DONE
    ├── fetcher.py              ✅ DONE
    └── synthesizer.py          ✅ DONE
```

**End-to-end verified live** with the Vietnamese claim *"Florentino Perez là chủ tịch của FC Barcelona"* via `analyze()` — returned verdict `FALSE`, confidence `HIGH`, three credible contradicting sources (ESPN, Wikipedia, Yahoo Sports) with publication dates extracted.

---

## Schema — pipeline stages

```
                  SearchResult   →   ScoredResult   →   FetchedArticle   →   Source
                  (after search)     (after filter)     (after fetch)         (after LLM)

                  url                url                url                   url
                  title              title              title                 title
                  snippet            snippet            body (≤3000 chars)    domain
                  domain             domain             domain                credibility_score
                                     credibility_score  credibility_score     stance
                                                        published_at          published_at
```

`AnalysisResult` is the final contract with Backend: verdict + explanation + sources + confidence + cached.

**Schema note (Step 8):** `QueryResult` was removed. With translation lifted out to `preprocessor.normalize()`, `query_builder.build_search_query()` now has a single responsibility and returns a plain `str`.

---

## Completed steps

### Step 1 — Understand the contract (conceptual)
- Pipeline contract: `analyze(text: str) -> AnalysisResult`
- `NOT_SURE` is a first-class verdict, not an error
- When any stage fails → return `NOT_SURE`, never raise to caller

### Step 2 — Fix the schema (`ai_core/schema.py`)
- Removed `PARTIALLY_TRUE`, added `UNVERIFIED`
- Removed `credibility_score` from verdict (forces hallucination)
- Added `Stance` enum, `FetchedArticle`, `ScoredResult`
- Principle: **narrower LLM output space = more reliable output**
- Principle: **each type represents exactly what's known at that pipeline stage** (no placeholder fields, no lying types)
- **Step 8 cleanup:** removed `QueryResult` — became redundant after translation was lifted out of `query_builder`.

### Step 3 — `query_builder.py`
- 3-layer fallback: clean input → LLM → regex entity extraction
- Raw Vietnamese text is a bad Serper query: MBFC is English-only, search engines need keywords
- Principle: **graceful degradation** — best → good enough → never crash
- **Step 7.5 upgrade:** migrated from Gemini Flash to OpenRouter; previously did translation + query construction in one call, returned `QueryResult`.
- **Step 8 simplification:** translation responsibility moved to `preprocessor.py`. `query_builder` now takes an English claim and returns a plain `str`. Function renamed `build_query` → `build_search_query`. Layer 1 short-circuits when the claim is already ≤10 words (no LLM call needed for short, already-keyword-ish claims).

### Step 4 — `searcher.py`
- Serper endpoint: `POST https://google.serper.dev/search`
- Domain extraction: `urlparse(url).netloc.removeprefix("www.")`
- API keys in `.env`, never hardcoded — three consequences of hardcoding: cost abuse, sensitive data exposure, attacker manipulation

### Step 5 — `credibility_filter.py`
- Loads `data/mbfc_credibility.json` at import (built one-time via `scripts/build_mbfc.py` from MBFC raw CSV)
- `CREDIBILITY_THRESHOLD = 0.5` — domains below this are dropped
- Subdomain fallback: `en.wikipedia.org` → looks up `wikipedia.org`
- **Deduplicates by domain** — same domain only kept once (first result wins)
- Returns `List[ScoredResult]` — not `Source` because stance isn't known yet
- Known MBFC quirk: `facebook.com`, `youtube.com` score 0.9 (rated as platforms, not publishers)
- When DE delivers `/credibility` API: replace `_load_db()` with HTTP call, delete the JSON

### Step 6 — `fetcher.py`
- Primary: `newspaper3k`. Fallback: `requests` + `BeautifulSoup` `<p>` extraction
- `MIN_BODY_LENGTH = 150` chars (~3-4 sentences) — shorter bodies skipped
- `MAX_BODY_LENGTH = 3000` chars — truncation cap before LLM
- Single-responsibility: fetcher only fetches. Empty/short body → skip, don't return verdict
- `NOT_SURE` is the synthesizer's decision when there's no evidence — not the fetcher's
- Sites that block scrapers (e.g. facebook.com) consistently fail — expected, dropped gracefully
- **Step 7.5 upgrade:** also extracts `published_at` (Optional[datetime]). Three-strategy date scrape: (1) standard meta tags like `article:published_time`, (2) JSON-LD `datePublished` inside `<script type="application/ld+json">` (used by ESPN, NYT, etc.), (3) `<time datetime="...">` element.

### Step 7 — `synthesizer.py`
- **Single LLM call** for all reasoning. Per-article calls = more API cost + LLM can't compare sources holistically.
- **API:** OpenRouter (`https://openrouter.ai/api/v1`), OpenAI-compatible SDK. Model: `openrouter/auto`
- **Anti-hallucination pattern (critical):** The LLM only returns `article_index` + stance + verdict + explanation + confidence. URLs, titles, domains, and credibility scores are filled in from our own `FetchedArticle` data. **Never ask the LLM to echo back data you already have** — pure hallucination risk with zero benefit.
- **Structured chain-of-thought pattern:** prompt forces the LLM to write `claim_in_article` and `user_claim` BEFORE picking a stance label.
- Stripping logic for reasoning models: `re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)` before JSON parsing.

### Step 7.5 — Cross-language input + temporal awareness + JSON-mode reliability

- **Cross-language pipeline.** Vietnamese (or any non-English) input translated to English; the English claim, not raw text, is passed to the synthesizer.
- **Temporal awareness.** `FetchedArticle` and `Source` carry `published_at: Optional[datetime]`. Synthesizer prompt has a narrow temporal rule: when sources directly contradict, prefer the more recent.
- **`response_format={"type": "json_object"}`** added to LLM calls — fixes failure mode where unescaped quotes broke JSON parsing.

### Step 8 — `analyze()` integration + preprocessor + cache

**What we built:**

- **`ai_core/pipeline/preprocessor.py` (new).** Lifts translation out of `query_builder` into its own stage. Two-step contract:
  - `is_english(text)` — pure heuristic, no LLM call. Returns True if every char is in basic Latin + common punctuation.
  - `translate_to_english(text)` — LLM call via OpenRouter. Narrow prompt: pure translator, preserves named entities and numbers verbatim.
  - `normalize(text)` — public entry. Cleans whitespace, truncates to 1500 chars, skips LLM for English input, calls translator otherwise. Falls back to cleaned original on translation failure.
- **`ai_core/cache.py` (new).** Disk-backed JSON cache at `data/cache.json`. SHA-256 key on the lowercased English claim. 24h TTL. Prune-on-write. `get()` returns `AnalysisResult` with `cached=True`; `set()` refuses to re-store results that themselves came from cache. Uses `model_dump_json()` for safe serialization of `datetime` and enums.
- **`ai_core/__init__.py`.** Replaced `NotImplementedError` with the real `analyze()` wiring all stages: `preprocessor → cache.get → query_builder → searcher → credibility_filter → fetcher → synthesizer → cache.set`. Never raises — empty input returns a `NOT_SURE` sentinel.
- **`ai_core/pipeline/analyzer.py` (deleted).** Dead code from before Step 6 — Gemini-based, referenced deleted `CredibilityAnalysis` type, duplicated synthesizer's job. Removed.

**What we haven't achieved (open challenges):**

- **Hash-based cache key is non-deterministic across runs.** Because the LLM translator can produce slightly different English for the same Vietnamese input on different runs (even at `temperature=0.1`), the SHA-256 hash of `english_claim` differs across calls — so cache reads never hit. Confirmed live: two consecutive `analyze()` calls with the same Vietnamese input stored under two different cache keys.
- **Decision:** *not* patching this. The proper fix is to replace hash-based caching with **vector embedding + Qdrant**: embed the English claim, do nearest-neighbor lookup with a similarity threshold, hit/miss based on semantic distance. Embedding is robust to LLM translation jitter (small wording differences → near-identical vectors) and also enables semantic dedup across paraphrases and languages — which hash-based caching could never do regardless of how we tweak the key.
- **Until Qdrant lands:** the disk cache is functionally inert. Every `analyze()` call writes one new entry, none ever get hit. Cost is negligible (one extra disk write per call, entries auto-prune after 24h). No urgency.
- **Integration point is clean.** Swapping cache backends only touches the two cache lines in `analyze()` — everything else is unaffected. This is the payoff of having `analyze()` as the single integration spot.

---

## Known limitations

- **Multi-claim posts** — pipeline collapses long multi-claim text into a single search query and verifies the main thrust. Sub-claims not individually checked. v2 scope: atomic-claim decomposition.
- **Hash cache doesn't survive LLM non-determinism.** Deferred to Qdrant vector cache.
- **Single-source confidence inflation** (Step 7.5). Defer.
- **Stance labels noisy under `openrouter/auto`** (Step 7.5). Defer.
- **Vietnamese without diacritics** would bypass the `is_english` check incorrectly. Rare; gracefully degrades to `NOT_SURE` via downstream retrieval failure.

---

## Next step: Step 9 — Backend integration OR Qdrant vector cache

Two viable next directions. Pick based on what's blocking other team members:

### Option A — Backend integration

Connect `analyze()` to the FastAPI endpoint in `fn-extension-backend/`. Verify the full extension → backend → ai_core → response loop works. This is what unblocks the rest of the team end-to-end.

### Option B — Qdrant vector cache

Replace the hash cache with embedding-based caching. Sketch:

```
embed(english_claim) → 768-dim vector (e.g. sentence-transformers all-mpnet-base-v2)
qdrant.search(vector, threshold=0.92) → nearest neighbor
  hit (similarity ≥ threshold AND not expired) → return cached AnalysisResult
  miss → run pipeline → qdrant.upsert(vector, AnalysisResult JSON)
```

Things to think about:
- Embedding model: local (sentence-transformers) vs API (OpenAI/Cohere)? Local = free + offline + slower. API = consistent + faster + ongoing cost.
- Threshold tuning: too high → too few hits; too low → wrong results returned. Needs eval.
- Qdrant deployment: local Docker for dev, hosted for prod.
- TTL still applies — semantic match doesn't help if the underlying fact has changed.

---

## Environment

- Python venv: `ngan/` inside project root (Python 3.14.4)
- `.env` location: `D:/ThirdYear/second_semester/check-fake-news-extension/.env`
- Required env vars: `SERPER_API_KEY`, `OPENROUTER_API_KEY` (Gemini no longer used after Step 7.5)
- `dotenv` loaded at module level in each pipeline file
- Required packages: `requests`, `python-dotenv`, `pydantic`, `newspaper3k`, `beautifulsoup4`, `lxml`, `lxml_html_clean`, `openai`

---

## Manual test pattern

End-to-end test via the public `analyze()` entry point:

```python
from ai_core import analyze

# First call — full pipeline runs
result = analyze("Florentino Perez là chủ tịch của FC Barcelona")
print(result.model_dump_json(indent=2))
print(f"cached: {result.cached}")  # → False

# Second call — currently misses cache due to LLM translation non-determinism.
# When Qdrant vector cache lands, this will return cached=True.
result2 = analyze("Florentino Perez là chủ tịch của FC Barcelona")
print(f"cached: {result2.cached}")
```

Per-stage REPL test (useful for diagnosing which stage is misbehaving):

```python
from ai_core.pipeline.preprocessor import normalize
from ai_core.pipeline.query_builder import build_search_query
from ai_core.pipeline.searcher import search
from ai_core.pipeline.credibility_filter import filter_credible
from ai_core.pipeline.fetcher import fetch_all
from ai_core.pipeline.synthesizer import synthesize

raw_text = 'Florentino Perez là chủ tịch của FC Barcelona'

english_claim = normalize(raw_text)
print(f"english_claim : {english_claim}")

search_query = build_search_query(english_claim)
print(f"search_query  : {search_query}")

results  = search(search_query)
scored   = filter_credible(results)
articles = fetch_all(scored)

result_final = synthesize(english_claim, articles)
print(result_final.model_dump_json(indent=2))
```

---

## Design principles established

1. **Contract first** — define input/output before implementation
2. **Narrow LLM output space** — enums > floats, constrained prompts > open-ended, JSON mode > prose
3. **Isolate failures** — test one file at a time
4. **Graceful degradation** — try best → fall back → never crash
5. **Fail loud in dev** — always print/log errors
6. **No lying types** — each schema type holds only what's known at that stage
7. **Decouple from third-party shapes** — map external API responses to your schema immediately
8. **Never ask the LLM to echo back data you already have** — pure hallucination risk, zero benefit
9. **Structured chain-of-thought** — force reasoning into required JSON fields instead of prose
10. **Single-responsibility per pipeline stage** — fetcher fetches, synthesizer decides verdicts; stages don't bleed into each other
11. **Every LLM judgment is a hallucination surface** — the narrower and more mechanical the rule, the more reliable.
12. **Defense in depth for structured output** — schema enums + prompt format instructions + API `response_format` mode. Each layer independent.
13. **Lift transformations out of judgment stages.** Translation lives in `preprocessor`, not `query_builder`. Each stage does one transformation cleanly. (Step 8.)
14. **Don't hash through non-deterministic stages.** If an LLM call sits between the raw input and the cache key, repeat-cache-hits are unreliable. Hash either the deterministic input (raw text) or use a similarity-tolerant store (vector DB). (Step 8 — open lesson, to be applied in Step 9.)
