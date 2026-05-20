# AI Pipeline — Learning Progress & Session Log

> **Owner:** Ngan (AI Pipeline role)
> **Project:** Fake News Detector Browser Extension
> **Last updated:** 2026-05-18
> **Status:** Step 5 complete, Step 6 next

---

## How to continue in a new chat

**Say this to Claude:**

> Read `D:\ThirdYear\second_semester\check-fake-news-extension\check-fake-new-extension\PROGRESS.md` and continue from where we left off.

---

## Working style (updated)

- Claude writes all boilerplate and structural code directly to the filesystem
- Ngan focuses on understanding the system — pipeline design, data flow, tradeoffs
- Core knowledge questions asked before key design decisions; Ngan answers before Claude proceeds
- No coding from scratch unless Ngan wants to

---

## Pipeline overview

```
analyze(text: str) -> AnalysisResult

    ├── query_builder.py        ✅ DONE
    ├── searcher.py             ✅ DONE
    ├── credibility_filter.py   ✅ DONE
    ├── fetcher.py              ⬅️ NEXT (Step 6)
    └── synthesizer.py          ⬜ TODO
```

---

## Schema — four pipeline stages

```
SearchResult   →   ScoredResult   →   FetchedArticle   →   Source
(after search)     (after filter)     (after fetch)         (after LLM)

url                url                url                   url
title              title              title                 title
snippet            snippet            body (≤3000 chars)    domain
domain             domain             domain                credibility_score
                   credibility_score  credibility_score     stance
```

`AnalysisResult` is the final contract with Backend: verdict + explanation + sources + confidence + cached.

---

## Completed steps

### Step 1 — Understand the contract (conceptual)
- Pipeline contract: `analyze(text: str) -> AnalysisResult`
- `NOT_SURE` is a first-class verdict, not an error
- When Serper is down → return `NOT_SURE`, not an API error

### Step 2 — Fix the schema (`ai_core/schema.py`)
- Removed `PARTIALLY_TRUE`, added `UNVERIFIED`
- Removed `credibility_score` from verdict (forces hallucination)
- Added `Stance` enum, `FetchedArticle`, `ScoredResult`
- Principle: **narrower LLM output space = more reliable output**
- Principle: **each type represents exactly what's known at that pipeline stage**

### Step 3 — `query_builder.py`
- 3-layer fallback: clean input → Gemini Flash → regex entity extraction
- Raw Vietnamese text is a bad Serper query: MBFC is English-only, search engines need keywords
- Principle: **graceful degradation** — best → good enough → never crash

### Step 4 — `searcher.py`
- Serper endpoint: `POST https://google.serper.dev/search`
- Domain extraction: `urlparse(url).netloc.removeprefix("www.")`
- API keys in `.env`, never hardcoded

### Step 5 — `credibility_filter.py`
- Loads `data/mbfc_credibility.json` at import time (one-time build via `scripts/build_mbfc.py`)
- `CREDIBILITY_THRESHOLD = 0.5` — domains below this are dropped
- Subdomain fallback: `en.wikipedia.org` → looks up `wikipedia.org`
- Returns `List[ScoredResult]` — not `List[Source]` because stance isn't known yet
- MBFC platform quirk: `facebook.com`, `youtube.com` score 0.9 (rated as platforms, not publishers)
- When DE delivers `/credibility` API: replace `_load_db()` with HTTP call, delete JSON file

**Key design decision:** Added `ScoredResult` as intermediate type between `SearchResult` and `FetchedArticle`. Rejected merging into one class — would require placeholder fields, violating the "no lying types" principle.

---

## Next step: Step 6 — `fetcher.py`

**What it does:**
- Takes `List[ScoredResult]` from `credibility_filter.py`
- Downloads each article using `newspaper3k`
- Truncates body to 3000 chars
- Returns `List[FetchedArticle]`

**Key things to think about before implementing:**
- What happens when a URL is paywalled or blocks scrapers?
- What's the timeout strategy — fetch all sequentially or in parallel?
- What's the minimum viable body length to be useful to the LLM?

---

## Environment

- Python venv: `ngan/` inside project root
- `.env` location: `D:/ThirdYear/second_semester/check-fake-news-extension/.env`
- `dotenv` loaded at module level in each pipeline file
- Test pattern: `python -c "from ai_core.pipeline.X import Y; ..."`

---

## Design principles

1. **Contract first** — define input/output before implementation
2. **Narrow LLM output space** — enums > floats, constrained prompts > open-ended
3. **Isolate failures** — test one file at a time
4. **Graceful degradation** — try best → fall back → never crash
5. **Fail loud in dev** — always print/log errors
6. **No lying types** — each schema type holds only what's known at that stage
7. **Decouple from third-party shapes** — map external API responses to your schema immediately
