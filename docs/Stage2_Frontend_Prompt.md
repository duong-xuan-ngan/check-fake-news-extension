# Prompt — Stage 2 Frontend Implementation
## Credibility Evaluator Browser Extension

---

## Project Context

This is a Chrome browser extension called **Credibility Evaluator**. Users highlight a passage of text on Facebook or Threads, and the extension analyses it and returns a credibility score backed by specific retrieved sources.

Stage 1 is already complete and includes: Chrome Manifest V3, a React sidebar, a background worker that sends selected text to a FastAPI backend and receives a single JSON response containing a score, confidence level, and a plain-English explanation. An exact-match Redis cache is also in place.

Stage 2 upgrades the entire pipeline to integrate RAG — the backend now streams results via SSE instead of returning a single response, and adds the ability to retrieve external sources. Your job is to upgrade the frontend to correctly handle this new data flow end to end.

---

## Technical Constraints

The extension runs on Chrome Manifest V3, meaning the background context is a service worker, not a persistent background page. The sidebar is rendered in React inside a Chrome side panel or an injected iframe. The backend is FastAPI, streaming results via SSE with content-type text/event-stream at the POST /analyze endpoint. No user content may be stored beyond the session without explicit opt-in. All meaningful output must appear within 5 seconds of the user triggering analysis.

---

## Backend Data Flow in Stage 2

The backend sends SSE events in the following sequence. The first event is the score event, which contains the numerical score, confidence level, and explanation — this arrives earliest, around 1 second. Next is the sources event, containing a list of retrieved sources, each with a URL, domain name, excerpt, and a domain authority score from 0 to 1. If there is a cache hit, the backend also sends a cached event indicating whether the cache type is exact or semantic. If retrieval fails, the backend sends an error event with the name of the failed task. The stream always ends with a done event. Events may arrive out of order, and sources and error are mutually exclusive for any given task.

---

## Tasks to Implement

### Task 1 — Streaming UI

Rewrite the fetch logic in the background worker to consume the SSE stream. Important: do not use the EventSource API — it only supports GET requests and is blocked in a Manifest V3 service worker. Instead, use fetch() combined with ReadableStream to read data chunk by chunk. After each chunk, parse the event/data pairs from the buffer and forward them to the sidebar via chrome.runtime.sendMessage. Set a hard timeout of 5 seconds — if the done event has not arrived by then, treat the state as degraded mode. The goal is for the score badge to appear within approximately 1 second, with the remaining sections rendering progressively as events arrive.

### Task 2 — Sources Section

Build a SourcesList component inside the React sidebar. Each source card displays three pieces of information: the domain name in bold (truncated if too long), an excerpt of no more than 2–3 lines with an ellipsis, and a colour-coded badge reflecting domain authority. The badge is green for authority of 0.75 or above, amber for 0.45 to below 0.75, and red for below 0.45. If there are no sources and retrieval did not fail, display "No sources found". Sources should be collapsed by default when confidence is HIGH, and expanded by default when confidence is MEDIUM or LOW.

### Task 3 — Progressive Disclosure

Add intermediate UI states to cover the gap between when the score has arrived but sources have not yet. During this window, display a skeleton placeholder consisting of grey animated pulse bars with a "Checking sources…" label above them. When the sources event arrives, replace the skeleton with the real SourcesList using a smooth CSS fade-in transition — no animation library should be used. The score badge and explanation panel must not re-render during this transition.

### Task 4 — Graceful Error Display

Handle the case where the backend sends an error event with task set to retrieval. In this case, display a non-blocking warning banner with a warning icon and the message "Sources unavailable — score based on AI reasoning only". The banner should use yellow or amber colouring, not red, because this is an intentionally designed degraded state, not a system failure. The score and explanation must still render normally. Under no circumstances should the app crash or display an error boundary for this case.

### Task 5 — Cache Transparency Indicator

When a cached event is received from the backend, display a small pill badge near the score reading "Cached result". If cache_type is semantic, include a subtext or tooltip saying "Similar claim retrieved from cache". If it is exact, the subtext should read "Identical text retrieved from cache". The badge must be visually subtle — muted colour, small font — so it does not distract from the main score. If no cached event is received, render nothing at all; do not display "Not cached".

### Task 6 — End-to-End Smoke Test

Write an integration smoke test using Playwright or the Chrome extension testing API. The test must load the unpacked extension into a browser instance, navigate to a real or mocked Facebook page, simulate a user highlighting text over a specific claim, trigger the extension sidebar, and assert within 5 seconds that the score badge displays a number between 0 and 100, and that either at least one source card is rendered or the "Sources unavailable" warning is shown. The test must also confirm there are no JS errors in the extension console.

---

## Component Structure After Stage 2

The Sidebar is the outermost container. Inside it, ScoreBadge renders when the score event arrives (around 1 second in). CachedIndicator only renders when a cached event is received. ExplanationPanel renders at the same time as the score. RetrievalWarning only appears when retrieval has failed. SourcesSection is the most complex part — internally it shows SourcesSkeleton while waiting, then transitions to SourcesList once sources arrive.

---

## Acceptance Criteria

The score badge must appear within approximately 1 second of the request being sent. Sources must render after the score without a page reload. Each source card must include the domain, excerpt, and authority badge with the correct colour for the given threshold. The "Checking sources…" skeleton must be visible during the window between the score event and the sources event. The transition from skeleton to sources list must be smooth with no flicker. When retrieval fails, the app must still render the score and the warning without crashing. The "Cached result" badge must appear only when there is a cache hit and must be absent when the result is fresh. The smoke test must pass within 5 seconds with a score visible and at least one source or warning present.

---

## What Not To Do

Do not use the EventSource API — it does not support POST in Manifest V3. Do not block the entire sidebar waiting for the full stream before rendering anything. Do not place a spinner over the whole sidebar — only the sources section should have a skeleton. Do not store text or sources in localStorage or any other persistent browser storage. Do not show an error boundary or a "Something went wrong" message for retrieval failure — this is an intentional degraded state.

---

## Implementation Order

Start with Task 1, as SSE streaming is the foundation that unblocks all other tasks. Then work on Task 3 (skeleton) alongside Task 2 (sources), since the two are tightly coupled. Tasks 4 and 5 are independent and can follow. Task 6 should be done last to test the complete flow end to end.
