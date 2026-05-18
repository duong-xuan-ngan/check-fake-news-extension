# Solution Architecture Design — New Chat Brief

> **Read this file first before responding to anything.**

---

## Who I am

I am Ngan, a third-year Computer Science/Software Engineering student at Vietnamese-German University (VGU). I am the **AI Pipeline Engineer** on a team project building a fake news detection browser extension.

---

## What this chat is for

I want to design and draw the **full solution architecture** of my project — covering the entire system from the Chrome extension through to external APIs. The diagram should be good enough for both my own understanding and for team documentation/presentation.

---

## What my project is about

A Chrome browser extension that lets users highlight suspicious text on social media (Facebook, Threads) and get an instant fact-check verdict.

**The system has four layers:**

1. **Chrome Extension** (sidepanel UI) — user highlights text, clicks icon, sees verdict
2. **Backend** (FastAPI) — receives the highlighted text, orchestrates the pipeline, returns verdict
3. **AI Pipeline** (my responsibility) — the fact-checking engine:
   - `query_builder` → turns highlighted text into a search query
   - `searcher` → calls Serper API, gets 10 web results
   - `credibility_filter` → filters sources using MBFC credibility database (threshold: 0.5)
   - `fetcher` → downloads full article content using newspaper3k
   - `synthesizer` → sends evidence to Gemini, gets structured verdict
4. **External APIs** — Serper (web search), Gemini (LLM analysis), MBFC (credibility data)

**Final output contract:**
```
AnalysisResult:
  verdict: TRUE | FALSE | UNVERIFIED | NOT_SURE
  explanation: str (max 500 chars)
  sources: List[Source]  # each has url, domain, credibility_score, stance
  confidence: HIGH | MEDIUM | LOW
  cached: bool
```

**Pipeline data flow:**
```
str (highlighted text)
  → SearchResult      (url, title, snippet, domain)
  → ScoredResult      (+ credibility_score)
  → FetchedArticle    (+ body ≤3000 chars, no snippet)
  → Source            (+ stance, no body)
  → AnalysisResult    (final verdict)
```

---

## How we should collaborate

- **Ngan thinks first** — Claude asks questions, Ngan answers from understanding, Claude corrects or builds on top
- **Claude does not explain everything at once** — one concept at a time
- **Claude does not draw the diagram immediately** — guide Ngan to identify each component first, then render
- **Claude asks 1 short check question** before moving to each new component
- **After each component is identified:** ask Ngan to explain the connection to adjacent components in own words

---

## Expected responsibilities of the assistant

1. Ask Ngan to identify each system component from memory before placing it in the diagram
2. Correct misunderstandings before they get drawn into the architecture
3. Explain *why* each component exists — not just what it does
4. Once all components are identified and understood, render a clean architecture diagram
5. After rendering, ask Ngan to walk through a user scenario end-to-end using the diagram

---

## Main focus of the discussion

- Full system scope: Extension → Backend → AI Pipeline → External APIs
- Data flow between components (what type goes in, what type comes out)
- Where caching sits (Redis)
- Where failures are handled (graceful degradation points)
- How the Chrome extension communicates with Backend (REST API, what payload)
- How Backend communicates with the AI Pipeline (direct call or message queue)

---

## What we have already built (AI Pipeline)

| File | Status |
|---|---|
| `ai_core/schema.py` | ✅ Done |
| `ai_core/pipeline/query_builder.py` | ✅ Done |
| `ai_core/pipeline/searcher.py` | ✅ Done |
| `ai_core/pipeline/credibility_filter.py` | ✅ Done |
| `ai_core/pipeline/fetcher.py` | ⬅️ In progress |
| `ai_core/pipeline/synthesizer.py` | ⬜ Todo |

---

## How to start

Ask me this first:

> "When a user highlights text on Facebook and clicks your extension icon — what is the very first thing that happens technically? Who sends what to whom?"

Wait for my answer before drawing anything.
