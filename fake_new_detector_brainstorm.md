# Fake News Detector — Browser Extension
## Project Brainstorm & Design Document

---

## 1. The Real Problem

People encounter unverified news daily on social media (Facebook, Threads) but don't bother checking because **the process is too inconvenient** — copy, open new tab, paste, write a prompt. The barrier isn't awareness; it's **friction**.

> Key insight: If checking took just 1 click without leaving the page, users would do it.

---

## 2. Core User Flow

1. User highlights suspicious text on a webpage
2. A small extension icon appears near the cursor
3. User clicks the icon
4. A panel appears **above the highlighted text** showing the analysis result

**Output displayed to user:**
- Credibility level (High / Medium / Low — or %)
- Explanation of why (e.g., "sensationalist headline, no specific sources found")
- Referenced sources used for the analysis
- **"Not sure" state** when evidence is insufficient — never force a verdict

> Key insight: Users won't trust the tool immediately. They calibrate trust by checking if the explanation matches their own reading. Clear reasoning = higher trust over time.

---

## 3. Why "Not Sure" Is a Feature, Not a Bug

A tool that always gives a confident verdict is **more dangerous** than one that admits uncertainty. The worst failure mode is: tool says "High credibility" → user shares it → turns out to be fake. That user never comes back.

Explicit uncertainty is a sign of engineering maturity for a trust-critical system.

---

## 4. AI Pipeline (Core Responsibility)

### Step-by-step logic:

```
[1] Receive highlighted text
        ↓
[2] Generate search query
    (keep specific details: numbers, names, dates)
        ↓
[3] Search the web → Serper API
    (returns list of URLs)
        ↓
[4] Extract domain from each URL
    (e.g., vnexpress.net)
        ↓
[5] Check source credibility → MBFC Database
    (Media Bias / Fact Check)
        ↓
[6] Fetch content from credible sources only
    → Newspaper3k (BeautifulSoup as fallback)
        ↓
[7] Send to LLM for analysis
    Input: original highlighted text + fetched content
    → Gemini API (free tier)
        ↓
[8] Output: credibility verdict + explanation + sources
    (or "not sure" if evidence is weak)
```

### Key design decisions:

| Decision | Reasoning |
|----------|-----------|
| Filter by credibility **before** fetching content | Don't waste resources fetching unreliable sources |
| Keep specific details in search query | Vague queries return irrelevant results |
| "Not sure" as a first-class output | Prevents dangerous false confidence |
| Sequential pipeline for v1 | Easier to debug; know exactly which step fails |
| Streaming + early stopping | For v2, after v1 is working |

---

## 5. Source Credibility — How It Works

**Viral ≠ Credible.** A piece of news can spread widely and still be false.

Credibility is determined by:
- History of accurate reporting
- Being a recognized, established outlet
- Clear, logical argumentation

**Implementation approach (prioritized):**

| Priority | Approach | Why |
|----------|----------|-----|
| First | MBFC database lookup | Pre-built, reliable, low effort |
| First | Restrict search to known credible domains | Simple, effective, immediate |
| Later | Analyze source's historical accuracy | High effort, save for v2 |
| Later | Topic-specific credibility scoring | Complex, save for v2 |

---

## 6. Tech Stack

| Component | Tool | Reason |
|-----------|------|--------|
| Search | Serper API | Free tier (2,500 queries), simple API |
| Source credibility | MBFC Database | Pre-built credibility ratings |
| Web scraping | Newspaper3k | Built for news articles, handles most cases |
| LLM analysis | Gemini API | Free tier on Google AI Studio |
| Backend | FastAPI (Python) | Async-native, lightweight |
| Frontend | Chrome Extension (JS) | Direct browser integration |

---

## 7. System Architecture

```
[Browser Extension]
  - Detects text highlight
  - Shows trigger icon
  - Displays result panel
        ↓ HTTPS
[Backend API]
  - Receives text
  - Runs AI pipeline
  - Returns structured result
        ↓
[AI Pipeline]
  Serper → MBFC filter → Newspaper3k → Gemini
```

**Why separate Frontend and Backend?**
Each handles a distinct responsibility and can be developed, tested, and scaled independently. Tightly coupled systems are expensive to change and hard to debug.

---

## 8. Team Structure

| Role | Responsibility |
|------|---------------|
| AI (you) | RAG pipeline, source evaluation, LLM integration, verdict synthesis |
| Backend | API server, routing, infrastructure |
| Frontend | Chrome extension UI, user interaction |
| Data Engineering | Data pipeline, storage, infrastructure support |

**Key interfaces to align on:**
- **AI ↔ Frontend:** What format does the extension send text? What format does the verdict come back in?
- **AI ↔ Backend/DE:** What environment does the AI pipeline need? Which API keys, which dependencies?

---

## 9. Build Order (v1 First)

> Don't build the perfect system. Build the smallest thing that works.

**v1 goal:** Input one sentence → find sources → return a verdict. Ugly is fine. Slow is fine. It just needs to run.

**v2 and beyond:**
- Streaming pipeline (process sources as they arrive)
- Early stopping (stop searching when evidence is strong enough)
- Playwright/Selenium for JavaScript-heavy sites
- Topic-specific credibility scoring

---

## 10. Failure Modes to Design Against

| Failure | Impact | Mitigation |
|---------|--------|------------|
| Slow response (>3s) | User abandons tool | Optimize pipeline, show loading state |
| Irrelevant explanation | User loses trust | Keep query specific, validate LLM output |
| False confident verdict | User shares fake news, blames tool | "Not sure" state, never force verdict |
| Scraping blocked | No content fetched | Fallback sources, handle gracefully |

---

*Built from scratch through first-principles thinking — not generated from a template.*
*Version 1.0 — brainstorm phase complete.*
