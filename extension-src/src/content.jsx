import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import PopupApp from './components/PopupApp.jsx'
import ProcessingPill from './components/ProcessingPill.jsx'
import HighlightBubble, {
  BUBBLE_CORE_WIDTH,
  BUBBLE_CORE_HEIGHT,
  BUBBLE_TAIL_HEIGHT,
} from './components/HighlightBubble.jsx'
import { apiFetch, getSession } from './lib/api.js'
import './index.css'

const POPUP_WIDTH = 420
const POPUP_GUTTER = 15
const VIEWPORT_MARGIN = 12
const CARD_MIN_HEIGHT = 240
const CARD_MAX_HEIGHT = 560
const CARD_HEADER_VISIBLE = 56 // px of the card kept on-screen (header/handle) when dragged near an edge

// Bottom-right corner of the viewport is where chat/help/support widgets (Messenger,
// Intercom, Zendesk, etc.) conventionally live. A cheap, DOM-free heuristic: avoid
// landing there if a candidate that doesn't is reasonably available.
const WIDGET_ZONE_WIDTH = 380
const WIDGET_ZONE_HEIGHT = 200

const BUBBLE_GUTTER = 8 // gap between the selection and the bubble's core edge (spec: 6-10px)

const getFallbackRect = () => ({
  top: 100,
  right: Math.max(POPUP_WIDTH + POPUP_GUTTER, window.innerWidth - POPUP_GUTTER),
  bottom: 100,
})

const normalizeRect = (rect) => {
  const fallback = getFallbackRect()
  return {
    top: Number.isFinite(rect?.top) ? rect.top : fallback.top,
    right: Number.isFinite(rect?.right) ? rect.right : fallback.right,
    bottom: Number.isFinite(rect?.bottom) ? rect.bottom : fallback.bottom,
    left: Number.isFinite(rect?.left) ? rect.left : fallback.right - POPUP_WIDTH,
  }
}

// ---------- Result / error card — document-anchored near the selection ----------
// Unchanged.

function getResultContainer() {
  let container = document.getElementById('fake-news-checker-container')
  if (!container) {
    container = document.createElement('div')
    container.id = 'fake-news-checker-container'
    container.style.position = 'absolute'
    container.style.zIndex = '999999'
    container.style.display = 'none'
    document.body.appendChild(container)

    const shadowRoot = container.attachShadow({ mode: 'open' })
    const styleLink = document.createElement('link')
    styleLink.rel = 'stylesheet'
    styleLink.href = chrome.runtime.getURL('content.css')
    shadowRoot.appendChild(styleLink)

    const rootEl = document.createElement('div')
    rootEl.id = 'root'
    shadowRoot.appendChild(rootEl)

    container._reactRoot = createRoot(rootEl)
  }
  return container
}

/** Full viewport-relative position + max-height this direction would produce. */
function computeCandidate(dir, safeRect, viewportWidth, viewportHeight) {
  let top
  let left
  let maxHeight

  if (dir === 'right' || dir === 'left') {
    left = dir === 'right' ? safeRect.right + POPUP_GUTTER : safeRect.left - POPUP_GUTTER - POPUP_WIDTH
    left = Math.min(Math.max(left, VIEWPORT_MARGIN), viewportWidth - POPUP_WIDTH - VIEWPORT_MARGIN)

    const spaceFromTop = viewportHeight - safeRect.top - VIEWPORT_MARGIN
    maxHeight = Math.max(CARD_MIN_HEIGHT, Math.min(CARD_MAX_HEIGHT, spaceFromTop))
    top = Math.min(safeRect.top, viewportHeight - maxHeight - VIEWPORT_MARGIN)
    top = Math.max(VIEWPORT_MARGIN, top)
  } else {
    const space = dir === 'below' ? viewportHeight - safeRect.bottom - VIEWPORT_MARGIN : safeRect.top - VIEWPORT_MARGIN
    maxHeight = Math.max(CARD_MIN_HEIGHT, Math.min(CARD_MAX_HEIGHT, space - POPUP_GUTTER))
    top = dir === 'below' ? safeRect.bottom + POPUP_GUTTER : safeRect.top - POPUP_GUTTER - maxHeight
    top = Math.max(VIEWPORT_MARGIN, top)

    left = safeRect.right - POPUP_WIDTH / 2
    left = Math.min(Math.max(left, VIEWPORT_MARGIN), viewportWidth - POPUP_WIDTH - VIEWPORT_MARGIN)
  }

  const space =
    dir === 'right'
      ? viewportWidth - safeRect.right - VIEWPORT_MARGIN
      : dir === 'left'
        ? safeRect.left - VIEWPORT_MARGIN
        : dir === 'below'
          ? viewportHeight - safeRect.bottom - VIEWPORT_MARGIN
          : safeRect.top - VIEWPORT_MARGIN

  const need = dir === 'right' || dir === 'left' ? POPUP_WIDTH : CARD_MIN_HEIGHT
  const fits = space >= need

  const cardRight = left + POPUP_WIDTH
  const cardBottom = top + maxHeight
  const inWidgetZone = cardRight > viewportWidth - WIDGET_ZONE_WIDTH && cardBottom > viewportHeight - WIDGET_ZONE_HEIGHT

  return { dir, top, left, maxHeight, space, fits, inWidgetZone }
}

/**
 * Priority order: avoid the likely-widget corner first, fit well second, raw
 * space last. "right" stays the preferred default when nothing else matters —
 * it sits beside the text without pushing content up or down — but loses out
 * whenever it would land on top of where a chat/help widget usually sits.
 */
function pickBestCandidate(safeRect, viewportWidth, viewportHeight) {
  const candidates = ['right', 'below', 'above', 'left'].map((dir) =>
    computeCandidate(dir, safeRect, viewportWidth, viewportHeight)
  )

  return (
    candidates.find((c) => c.fits && !c.inWidgetZone) ||
    candidates.find((c) => !c.inWidgetZone) ||
    candidates.find((c) => c.fits) ||
    candidates.reduce((best, c) => (c.space > best.space ? c : best))
  )
}

/**
 * Skipped entirely once the user has manually dragged the card.
 */
function positionResultContainer(container, rect) {
  const safeRect = normalizeRect(rect)
  const viewportWidth = window.innerWidth
  const viewportHeight = window.innerHeight
  const { top, left, maxHeight } = pickBestCandidate(safeRect, viewportWidth, viewportHeight)

  container.style.top = `${top + window.scrollY}px`
  container.style.left = `${left + window.scrollX}px`
  container.style.setProperty('--vf-max-height', `${Math.round(maxHeight)}px`)
}

/**
 * Pointer-capture drag: only the handle initiates it, capture keeps the drag
 * tracking even if the cursor leaves the card, and it's clamped so the header
 * always stays reachable. Doesn't touch --vf-max-height — the card keeps the
 * height it was given at initial placement.
 */
function startResultDrag(e, container) {
  if (e.button !== 0) return
  e.preventDefault()

  const handle = e.currentTarget
  handle.setPointerCapture(e.pointerId)

  const startX = e.clientX
  const startY = e.clientY
  const startTop = parseFloat(container.style.top) || 0
  const startLeft = parseFloat(container.style.left) || 0

  document.body.style.userSelect = 'none'
  document.body.style.cursor = 'grabbing'

  const onMove = (moveEvent) => {
    const dx = moveEvent.clientX - startX
    const dy = moveEvent.clientY - startY

    const minLeft = window.scrollX + VIEWPORT_MARGIN
    const maxLeft = window.scrollX + window.innerWidth - POPUP_WIDTH - VIEWPORT_MARGIN
    const minTop = window.scrollY + VIEWPORT_MARGIN
    const maxTop = window.scrollY + window.innerHeight - CARD_HEADER_VISIBLE - VIEWPORT_MARGIN

    container.style.left = `${Math.min(Math.max(startLeft + dx, minLeft), maxLeft)}px`
    container.style.top = `${Math.min(Math.max(startTop + dy, minTop), maxTop)}px`
  }

  const onUp = () => {
    handle.removeEventListener('pointermove', onMove)
    handle.removeEventListener('pointerup', onUp)
    handle.removeEventListener('pointercancel', onUp)
    document.body.style.userSelect = ''
    document.body.style.cursor = ''
    resultDragged = true
  }

  handle.addEventListener('pointermove', onMove)
  handle.addEventListener('pointerup', onUp)
  handle.addEventListener('pointercancel', onUp)
}

function showResult({ result, error, signInRequired, quotaExceeded }, rect) {
  const container = getResultContainer()
  if (!resultDragged) {
    positionResultContainer(container, rect)
  }
  container._reactRoot.render(
    <StrictMode>
      <PopupApp
        result={result}
        error={error}
        signInRequired={signInRequired}
        quotaExceeded={quotaExceeded}
        onSignIn={() => chrome.runtime.sendMessage({ type: 'OPEN_OPTIONS' })}
        onClose={() => {
          container.style.display = 'none'
        }}
        onDragHandlePointerDown={(e) => startResultDrag(e, container)}
        onViewFullReport={(report) => {
          chrome.runtime.sendMessage({ type: 'OPEN_FULL_REPORT', result: report })
        }}
      />
    </StrictMode>
  )
  container.style.display = 'block'
}

function hideResult() {
  const container = document.getElementById('fake-news-checker-container')
  if (container) container.style.display = 'none'
}

// ---------- Processing pill — independent, viewport-fixed at bottom-center ----------
// Unchanged.

function getPillContainer() {
  let container = document.getElementById('fake-news-checker-pill')
  if (!container) {
    container = document.createElement('div')
    container.id = 'fake-news-checker-pill'
    container.style.position = 'fixed'
    container.style.left = '50%'
    container.style.bottom = '28px'
    container.style.transform = 'translateX(-50%)'
    container.style.zIndex = '1000000'
    container.style.display = 'none'
    document.body.appendChild(container)

    const shadowRoot = container.attachShadow({ mode: 'open' })
    const styleLink = document.createElement('link')
    styleLink.rel = 'stylesheet'
    styleLink.href = chrome.runtime.getURL('content.css')
    shadowRoot.appendChild(styleLink)

    const rootEl = document.createElement('div')
    rootEl.id = 'root'
    shadowRoot.appendChild(rootEl)

    container._reactRoot = createRoot(rootEl)
    container._shadowRoot = shadowRoot
  }
  return container
}

function playConnectAnimation(shadowRoot, originRect) {
  if (!originRect) return
  const startX = originRect.left + originRect.width / 2
  const startY = originRect.top + originRect.height / 2
  const endX = window.innerWidth / 2
  const endY = window.innerHeight - 28

  const dot = document.createElement('div')
  dot.className = 'vf-connect-dot'
  dot.style.left = `${startX}px`
  dot.style.top = `${startY}px`
  dot.style.setProperty('--dx', `${endX - startX}px`)
  dot.style.setProperty('--dy', `${endY - startY}px`)
  dot.addEventListener('animationend', () => dot.remove())
  shadowRoot.appendChild(dot)
}

function showPill(onCancel, originRect) {
  const container = getPillContainer()
  container._reactRoot.render(
    <StrictMode>
      <ProcessingPill onCancel={onCancel} />
    </StrictMode>
  )
  container.style.display = 'block'
  playConnectAnimation(container._shadowRoot, originRect)
}

function hidePill() {
  const container = document.getElementById('fake-news-checker-pill')
  if (container) container.style.display = 'none'
}

// ---------- Highlight-trigger bubble — appears before any check starts ----------
// Its own container, its own placement rule, no relation to the result card's
// positioning logic above.

function getBubbleContainer() {
  let container = document.getElementById('fake-news-checker-bubble')
  if (!container) {
    container = document.createElement('div')
    container.id = 'fake-news-checker-bubble'
    container.style.position = 'absolute'
    container.style.zIndex = '999998'
    container.style.display = 'none'
    document.body.appendChild(container)

    const shadowRoot = container.attachShadow({ mode: 'open' })
    const styleLink = document.createElement('link')
    styleLink.rel = 'stylesheet'
    styleLink.href = chrome.runtime.getURL('content.css')
    shadowRoot.appendChild(styleLink)

    const rootEl = document.createElement('div')
    rootEl.id = 'root'
    shadowRoot.appendChild(rootEl)

    container._reactRoot = createRoot(rootEl)
  }
  return container
}

function computeBubblePlacement(rect) {
  const viewportWidth = window.innerWidth
  const viewportHeight = window.innerHeight

  // Keep the tail over the final visible text fragment; only nudge enough to
  // prevent horizontal viewport overflow.
  const anchorX = rect.right - Math.min(Math.max(rect.width / 2, 12), 30)
  const coreLeft = Math.min(
    Math.max(anchorX - BUBBLE_CORE_WIDTH / 2, VIEWPORT_MARGIN),
    viewportWidth - BUBBLE_CORE_WIDTH - VIEWPORT_MARGIN
  )
  const outerHeight = BUBBLE_CORE_HEIGHT + BUBBLE_TAIL_HEIGHT
  const aboveTop = rect.top - BUBBLE_GUTTER - outerHeight
  const belowTop = rect.bottom + BUBBLE_GUTTER

  if (aboveTop >= VIEWPORT_MARGIN) {
    return { tailSide: 'bottom', coreLeft, outerTop: aboveTop }
  }
  if (belowTop + outerHeight <= viewportHeight - VIEWPORT_MARGIN) {
    return { tailSide: 'top', coreLeft, outerTop: belowTop }
  }

  // On a very short viewport, stay on the side with more room rather than
  // detaching the bubble horizontally from its selection anchor.
  const placeAbove = rect.top >= viewportHeight - rect.bottom
  return {
    tailSide: placeAbove ? 'bottom' : 'top',
    coreLeft,
    outerTop: placeAbove ? VIEWPORT_MARGIN : viewportHeight - outerHeight - VIEWPORT_MARGIN,
  }
}

function positionBubble(container, rect) {
  const { tailSide, coreLeft, outerTop } = computeBubblePlacement(rect)
  container.style.left = `${coreLeft + window.scrollX}px`
  container.style.top = `${outerTop + window.scrollY}px`

  return tailSide
}

function showBubble(rect) {
  const container = getBubbleContainer()
  const tailSide = positionBubble(container, rect)
  container._reactRoot.render(
    <StrictMode>
      <HighlightBubble
        tailSide={tailSide}
        onActivate={() => {
          const originRect = container.getBoundingClientRect()
          hideBubble()
          runAnalysis(currentSelection, originRect)
        }}
      />
    </StrictMode>
  )
  container.style.display = 'block'
}

function hideBubble() {
  const container = document.getElementById('fake-news-checker-bubble')
  if (container) container.style.display = 'none'
}

// ---------- Orchestration: single in-flight analysis, cancellable ----------
// Unchanged.

let activeController = null
let resultDragged = false
let signInPending = false

async function runAnalysis(text, originRect) {
  if (activeController) activeController.abort()
  const controller = new AbortController()
  activeController = controller
  resultDragged = false

  hideResult()

  const session = await getSession()
  if (!session || !session.accessToken) {
    signInPending = true
    showResult({ signInRequired: true }, originRect)
    return
  }
  signInPending = false

  showPill(() => {
    controller.abort()
    hidePill()
  }, originRect)

  try {
    const response = await apiFetch('/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
      signal: controller.signal,
    })
    if (response.status === 401) {
      signInPending = true
      hidePill()
      showResult({ signInRequired: true }, originRect)
      return
    }
    if (response.status === 429) {
      let quotaExceeded = true
      try {
        const body = await response.json()
        if (body?.detail?.error !== 'daily_limit_reached') quotaExceeded = false
      } catch {
        quotaExceeded = false
      }
      hidePill()
      if (quotaExceeded) {
        showResult({ quotaExceeded: true }, originRect)
      } else {
        showResult({ error: 'Too many requests. Please try again later.' }, originRect)
      }
      return
    }
    if (!response.ok) throw new Error(`Server error: ${response.status}`)
    const result = await response.json()
    if (controller.signal.aborted) return
    hidePill()
    showResult({ result }, originRect)
  } catch (err) {
    if (controller.signal.aborted || err.name === 'AbortError') return
    hidePill()
    showResult({ error: err.message || 'Failed to connect to server' }, originRect)
  } finally {
    if (activeController === controller) activeController = null
  }
}

// ---------- Selection handling ----------
// Unchanged.

let currentSelection = ''

document.addEventListener('mouseup', (e) => {
  const resultContainer = document.getElementById('fake-news-checker-container')
  if (resultContainer && e.composedPath().includes(resultContainer)) return

  const pillContainer = document.getElementById('fake-news-checker-pill')
  if (pillContainer && e.composedPath().includes(pillContainer)) return

  const bubbleContainer = document.getElementById('fake-news-checker-bubble')
  if (bubbleContainer && e.composedPath().includes(bubbleContainer)) return

  hideBubble()
  hideResult()

  const selection = window.getSelection()
  const selectedText = selection.toString().trim()

  if (selectedText && selectedText.length > 0 && selectedText.length <= 2000 && selection.rangeCount > 0) {
    currentSelection = selectedText
    const range = selection.getRangeAt(0)
    const rects = Array.from(range.getClientRects()).filter((rect) => rect.width > 0 && rect.height > 0)
    const rect = rects[rects.length - 1] || range.getBoundingClientRect()
    showBubble(rect)
  }
})

chrome.runtime.onMessage.addListener((message) => {
  if (message.type === 'TEXT_SELECTED' && message.text) {
    let rect = getFallbackRect()

    const selection = window.getSelection()
    if (selection && selection.rangeCount > 0) {
      const selectedText = selection.toString().trim()
      if (selectedText === message.text.trim()) {
        const range = selection.getRangeAt(0)
        rect = range.getBoundingClientRect()
      }
    }

    runAnalysis(message.text, rect)
  }
})

chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== 'local' || !changes.vf_session) return
  if (changes.vf_session.newValue && signInPending && currentSelection) {
    signInPending = false
    runAnalysis(currentSelection, getFallbackRect())
  }
})
