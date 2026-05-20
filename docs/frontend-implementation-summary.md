# Frontend Implementation Summary

## Overview

This document describes the changes made to the frontend (Chrome Extension + Side Panel) and backend mock as part of the frontend development phase.

---

## 1. Backend — Mock Response for `/analyze`

**File:** `fn-extension-backend/main.py`

The stub endpoint was replaced with a spec-compliant mock response that matches the exact JSON schema defined in Stage 3 of the system spec. An artificial delay (`time.sleep`) simulates the real AI pipeline latency.

**Mock response shape:**
```json
{
  "verdict": "FALSE",
  "explanation": "...",
  "sources": [
    {
      "url": "...",
      "domain": "vnexpress.net",
      "credibility_score": 0.92,
      "title": "...",
      "stance": "CONTRADICTS"
    }
  ],
  "confidence": "HIGH",
  "cached": false,
  "response_time_ms": 7150
}
```

---

## 2. FE-1 — Text Selection Validation (> 2,000 characters)

**File:** `extension/content.js`

Added a length check on `mouseup`. If the highlighted text exceeds 2,000 characters, the content script sends a different message type so the side panel can display a warning instead of silently allowing an invalid request.

**Before:**
```js
chrome.runtime.sendMessage({ type: 'TEXT_SELECTED', text: selectedText })
```

**After:**
```js
chrome.runtime.sendMessage({
  type: selectedText.length > 2000 ? 'SELECTION_TOO_LONG' : 'TEXT_SELECTED',
  text: selectedText,
})
```

**In the side panel (`App.jsx`):**
- Listens for `SELECTION_TOO_LONG` message → sets `tooLong` state
- Textarea border turns amber when over the limit
- Character counter turns amber and shows `x / 2,000 characters`
- Warning banner appears: *"Please select a shorter passage (max 2,000 characters)"*
- Analyze button is disabled while over the limit

---

## 3. FE-4 — Rotating Loading Messages

**File:** `sidepanel-src/src/App.jsx`

For requests that take longer than 5 seconds, the side panel shows contextual status messages that rotate every 3 seconds. This gives the user feedback that the analysis is progressing rather than stalled.

**Behavior:**
- **0 – 5s:** Standard spinner with "Analyzing..." button text
- **After 5s:** A message appears below the button and rotates every 3s:
  1. *Analyzing text...*
  2. *Searching for related sources...*
  3. *Cross-referencing data...*
  4. *Verifying source credibility...*
  5. *Almost there...*

**Implementation:** Uses `setTimeout` (5s delay) + `setInterval` (3s rotation) stored in `useRef` to avoid stale closures. Both timers are cleared when loading ends or the component unmounts.

---

## 4. FE-5 — Result Display Panel

**Files:** `sidepanel-src/src/App.jsx`, `sidepanel-src/src/App.css`

The raw JSON dump (`<pre>{JSON.stringify(result)}</pre>`) was replaced with two purpose-built components.

### VerdictBanner

Displays the top-level analysis result with color coding:

| Verdict | Color | Icon |
|---|---|---|
| `TRUE` | Green | CircleCheck |
| `FALSE` | Red | CircleX |
| `UNVERIFIED` | Amber | CircleAlert |
| `NOT_SURE` | Grey | CircleMinus |

Additional elements:
- **Confidence badge** — `HIGH` (green), `MEDIUM` (amber), `LOW` (red) pill badge
- **Cached badge** — ⚡ Cached shown in accent color when `cached: true`
- **Explanation text** — shown below the verdict for TRUE/FALSE/UNVERIFIED
- **Not Sure copy** — shows *"Insufficient evidence to determine credibility."* when verdict is `NOT_SURE`

### SourceItem

Each source in the `sources` array is rendered as a card containing:
- **Domain** (bold) + **Stance chip** — `SUPPORTS` (green), `CONTRADICTS` (red), `NEUTRAL` (grey)
- **Article title** — clickable link that opens in a new tab
- **Credibility bar** — progress bar from 0–100%, color-coded by score:
  - ≥ 70% → green
  - 50–69% → amber
  - < 50% → red

---

## Files Changed

| File | Change |
|---|---|
| `fn-extension-backend/main.py` | Mock `/analyze` response with artificial delay |
| `extension/content.js` | `SELECTION_TOO_LONG` message type for > 2,000 char selections |
| `sidepanel-src/src/App.jsx` | Full update: validation, rotating messages, VerdictBanner, SourceItem |
| `sidepanel-src/src/App.css` | New styles for all new UI components |
