# Frontend Implementation Plan

Implement FE-1 (validation), FE-4 (rotating loading messages), FE-5 (result display UI), and a backend mock response for `/analyze`.

---

## 1. Backend — Mock response for `/analyze`

File: `fn-extension-backend/main.py`

Replace the current stub with a spec-compliant mock response. Add `time.sleep(7)` to simulate pipeline latency and trigger rotating messages in the UI:

```python
@app.post("/analyze")
def analyze_endpoint(data: AnalyzeRequest):
    import time
    time.sleep(7)  # Simulate full pipeline latency
    return {
        "verdict": "FALSE",
        "explanation": "According to credible sources, this claim is inaccurate. Multiple reputable outlets have refuted it based on verified data.",
        "sources": [
            { "url": "https://vnexpress.net/sample", "domain": "vnexpress.net",
              "credibility_score": 0.92, "title": "Fact check: The truth behind this claim", "stance": "CONTRADICTS" },
            { "url": "https://tuoitre.vn/sample", "domain": "tuoitre.vn",
              "credibility_score": 0.88, "title": "Experts weigh in on the controversy", "stance": "CONTRADICTS" },
            { "url": "https://thanhnien.vn/sample", "domain": "thanhnien.vn",
              "credibility_score": 0.71, "title": "Analysis: What the data actually shows", "stance": "NEUTRAL" }
        ],
        "confidence": "HIGH",
        "cached": False,
        "response_time_ms": 7150
    }
```

---

## 2. FE-1 — Validation > 2000 chars

File: `extension/content.js` + `sidepanel-src/src/App.jsx`

- `content.js`: if `selectedText.length > 2000`, send `{ type: 'SELECTION_TOO_LONG', text }` instead of `TEXT_SELECTED`
- `App.jsx`: listen for `SELECTION_TOO_LONG` → show red warning banner + disable Analyze button

---

## 3. FE-4 — Rotating loading messages (after 5s)

File: `sidepanel-src/src/App.jsx`

- **0–5s**: standard spinner + "Analyzing..." (current behavior)
- **After 5s**: start rotating every 3s through:
  1. "Analyzing text..."
  2. "Searching for related sources..."
  3. "Cross-referencing data..."
  4. "Verifying source credibility..."
  5. "Almost there..."

Implementation: `useEffect` + `setInterval` when `loading === true`, cleared on completion.

---

## 4. FE-5 — Result Display Panel

Files: `sidepanel-src/src/App.jsx` + `sidepanel-src/src/App.css`

Replace `<pre>{JSON.stringify(result)}</pre>` with proper UI sections:

### VerdictBanner
| Verdict | Color | Icon |
|---|---|---|
| TRUE | `--success` (green) | CheckCircle |
| FALSE | `--danger` (red) | XCircle |
| UNVERIFIED | `--warning` (amber) | AlertCircle |
| NOT_SURE | `--text-muted` (grey) | MinusCircle |

- Confidence badge: `HIGH` / `MEDIUM` / `LOW` chip alongside verdict label
- `cached: true` → small "⚡ Cached" badge
- Explanation text below verdict

### SourcesList
- Per source: domain (bold) + title (smaller) + external link icon
- Credibility bar: progress bar 0–100%, colored by score (`--success` ≥0.7, `--warning` ≥0.5, `--danger` <0.5)
- Stance chip: `SUPPORTS` (green), `CONTRADICTS` (red), `NEUTRAL` (grey)

### NOT_SURE state
- Neutral `--bg-tertiary` box with text: *"Insufficient evidence to determine credibility."*

### Error state
- Existing red box — keep as-is

---

## Execution Order

1. Backend mock (`main.py`) — unblocks UI testing immediately
2. FE-1 validation (`content.js` + `App.jsx`)
3. FE-4 rotating messages (`App.jsx`)
4. FE-5 result UI (`App.jsx` + `App.css`)
