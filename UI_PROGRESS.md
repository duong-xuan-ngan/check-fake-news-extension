# SnapCheck (VeriFact) — Content-Script UI Progress & Session Log

> **Owner:** Ngan
> **Project:** Fake News Detector Browser Extension — content-script UI only (highlight bubble, processing pill, result card). Backend/AI-pipeline progress lives separately in `PROGRESS.md`; deployment progress in `DEPLOYMENT_PROGRESS.md`. This file doesn't touch either.
> **Last updated:** 2026-08-14
> **Status:** All three UI pieces built. The custom bubble is back to its intended design (face/eyes/tail) with the position + contrast + label changes applied. Not yet rebuilt/browser-tested since this round.

---

## ⚠️ Read this before touching the bubble

The bubble is a **custom, face-like design** and must stay that way. It is **not** a generic rounded capsule. It has, and must keep:

- Asymmetric corner radii (`16px 12px 14px 13px`) — the "face" silhouette
- Two border-only "eye" arcs on the top edge (`.vf-bubble-eyes` / `.vf-bubble-eye`)
- A small speech-bubble tail (`.vf-bubble-tail`)
- The blur, border, shadow, and premium styling
- Its size/proportions (150×30)

During this session the bubble was **twice** accidentally flattened into a plain capsule (eyes + tail stripped) while trying to apply small position/label/contrast tweaks — both times that was **wrong** and had to be reverted. If a request says "adjust the bubble," assume it means *keep this exact design* and change only the specific thing named. Do not simplify the geometry as a side effect. The face/eyes/tail are the whole point of the piece.

---

## How to continue in a new chat

**Say this to Claude:**

> Read `/Users/duongxuanngan/Documents/fake-new-detector/check-fake-news-extension/UI_PROGRESS.md` and continue from where we left off. You have filesystem MCP access at that project root.

---

## Rename note

The bubble's small visible **"SnapCheck" secondary label was removed** (per request) — the bubble now shows only "Want to know?". The `aria-label` still reads "Want to know? Check this with SnapCheck" (screen-reader only, left as original — the request was about the *visible* label). `PopupApp.jsx`'s header still reads "VeriFact" / "AI credibility check" — untouched. A full rebrand either direction is a separate, explicit task.

---

## Architecture overview

Three independent floating UI pieces, each its own Shadow DOM container appended directly to `document.body` by `content.jsx`, each linking `chrome.runtime.getURL('content.css')` into its own shadow root:

| Piece | Container id | Component | Position type |
|---|---|---|---|
| Highlight bubble | `#fake-news-checker-bubble` | `HighlightBubble.jsx` | `absolute`, document-anchored near selection |
| Processing pill | `#fake-news-checker-pill` | `ProcessingPill.jsx` | `fixed`, bottom-center of viewport |
| Result / error card | `#fake-news-checker-container` | `PopupApp.jsx` | `absolute`, document-anchored near selection |

Each has its **own, separate** positioning function in `content.jsx` — they don't share positioning code. This was intentional across several rounds: every redesign request was explicitly scoped to touch only one piece, so the three stayed decoupled by design rather than by accident.

Flow: `mouseup` on a text selection → `showBubble()`. Click the bubble → `runAnalysis()`, which hides the bubble, shows the pill, fetches, then swaps to the result card (or error). Right-click → "check with SnapCheck" context menu item skips the bubble entirely and calls `runAnalysis()` directly.

---

## Completed

### Result card — `PopupApp.jsx` + result-related parts of `content.jsx` + `index.css`

- Compact 420px, 2-column layout (verdict card | AI summary + sources)
- Dynamic max-height via CSS var `--vf-max-height`, computed fresh per placement — flex column + `min-height:0` on `.vf-body` means the body scrolls internally while header/footer stay put
- 4-direction smart positioning (`computeCandidate` / `pickBestCandidate`): scores right/below/above/left by available space, preferring whichever fits **and** avoids the bottom-right "widget zone" (`WIDGET_ZONE_WIDTH`/`HEIGHT` — a geometry-only heuristic for where chat/help widgets like Messenger conventionally sit, not real DOM collision detection)
- Draggable via pointer-capture on a `GripVertical` handle in the header (`startResultDrag`) — clamped so the header stays reachable even dragged to an edge; doesn't touch `--vf-max-height` mid-drag
- `resultDragged` flag skips auto-repositioning once the user has manually moved it; reset at the top of every new `runAnalysis()` call so a fresh analysis gets smart-positioned again
- Footer is icon-only (Feedback, Settings) — no text labels

### Processing pill — `ProcessingPill.jsx` + pill-related parts of `content.jsx` + `index.css`

- Small (56px) translucent dark pill, fixed bottom-center, independent of both the bubble and the result card
- Ring + pulse animation is pure CSS (`vf-spin`/`vf-pulse` keyframes) — no JS timers
- Hover swaps the spinner for a small ×; clicking anywhere on the pill cancels immediately: hides synchronously, aborts the fetch via `AbortController`, and — critically — **no result card appears afterward** (the abort is checked before `showResult` is ever called)
- Traveling-dot animation connects the click origin to the pill (`playConnectAnimation`)

### Highlight bubble — `HighlightBubble.jsx` + bubble-related parts of `content.jsx` + `index.css`

The SnapCheck-branded custom piece (see the ⚠️ note above — keep the face design). Current state:

- **Custom face-like geometry, intact:** asymmetric corner radii (`16px 12px 14px 13px`), two border-only "eye" arcs on the top edge (`.vf-bubble-eyes` / `.vf-bubble-eye`), a rotated-square speech-bubble tail (`.vf-bubble-tail`), blur + border + shadow, 150×30.
- **4-stage hover choreography** — appear → hover (~200ms) → hold (~500ms, blue glow, text fully opaque) → press (scale 0.98) — via staggered `transition-delay` on a single `:hover` rule. No JS state machine.
- **Text: "Want to know?" only**, centered (`justify-content: center` on `.vf-bubble`). The "SnapCheck" secondary label (`.vf-bubble-brand`) was removed.
- **Positioning (`positionBubble` in `content.jsx`) — vertical only:** above the selection by default (gap `BUBBLE_GUTTER` = 8px), flips below if there isn't enough room above. No left/right placement. Horizontally centered over the selection's midpoint, clamped to viewport edges.
- **Contrast (resting state, before hover):** opacity `0.92`, background `rgba(255,255,255,0.97)`, border `rgba(15,23,42,0.14)`, text `rgba(15,23,42,0.8)`. Bumped up from the original `0.62 / 0.92 / 0.08 / 0.55` so the text is readable immediately, still subtle/premium. The `@keyframes vf-bubble-in` `to`-state and the `prefers-reduced-motion` fallback were both updated to the same `0.92` resting opacity so the animation's final frame doesn't silently override the base value.

**Not built or browser-tested since this round.** Next step: `cd sidepanel-src && npm run build`, reload the unpacked extension in `chrome://extensions`, and refresh any already-open test tab. **If it still appears to the right / still shows the old design after rebuild, that's a stale build or an un-refreshed tab, not the source** — verify the build actually ran and reload both the extension and the tab.

---

## Open design note (not a bug — your call)

The `.vf-bubble-tail` sits on the **left edge** of the bubble. That was designed for when the bubble sat *beside* the selection. Now that the bubble sits **above/below**, the tail points sideways into empty space rather than at the selected text. It's been left exactly as the original design per the "keep everything, only change these things — not a redesign" instruction. If you want the tail to actually point at the text (down when the bubble is above, up when below), that's a small, deliberate follow-up change to `.vf-bubble-tail`'s edge + rotation — flag it explicitly if you want it, since moving it counts as touching the bubble geometry.

---

## Known gotchas for whoever picks this up

- **`str_replace`/`edit_file` intermittently fail on this iCloud-synced path**, even immediately after a successful read. `filesystem:write_file` (full overwrite) has been reliable every time this session — use that for edits here, not surgical patches.
- **`filesystem:write_file` takes `{ path, content }`** — not `{ path, file_text, description }` (that's the container `create_file` tool's schema; mixing them up throws a validation error).
- **Do not use the generic `create_file`/`bash_tool`/`view` container tools for this project.** They operate on a sandboxed container filesystem, not the actual Mac path. Only `filesystem:*` MCP tools reach the real project.
- **Vite only builds `content.jsx`.** See `sidepanel-src/vite.config.js` — `rollupOptions.input` is hardcoded to `src/content.jsx`, output is `extension/content.js` + `extension/content.css`. Build with `cd sidepanel-src && npm run build`. `extension/assets/*` and `extension/index.html` are stale, unreferenced by `manifest.json`.
- **After rebuilding:** reload the extension in `chrome://extensions` *and* refresh the test tab — an already-open tab keeps running the previously-injected content script even after the extension itself reloads.
- Custom CSS properties (like `--vf-max-height`) set on a Shadow DOM host element correctly inherit into that shadow root's content — confirmed working, used for the result card's dynamic height.

---

## Files touched this session

- `sidepanel-src/src/content.jsx`
- `sidepanel-src/src/components/PopupApp.jsx`
- `sidepanel-src/src/components/ProcessingPill.jsx`
- `sidepanel-src/src/components/HighlightBubble.jsx`
- `sidepanel-src/src/index.css`
