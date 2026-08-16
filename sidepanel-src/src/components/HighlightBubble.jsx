export const BUBBLE_CORE_WIDTH = 146
export const BUBBLE_CORE_HEIGHT = 30
export const BUBBLE_TAIL_HEIGHT = 6

/** The compact trigger shown immediately after a text selection. */
export default function HighlightBubble({ onActivate, tailSide = 'bottom' }) {
  const outerHeight = BUBBLE_CORE_HEIGHT + BUBBLE_TAIL_HEIGHT

  return (
    <button
      type="button"
      className={`vf-bubble vf-bubble--${tailSide}`}
      style={{ width: BUBBLE_CORE_WIDTH, height: outerHeight }}
      onClick={onActivate}
      aria-label="Check this selected text with SnapCheck"
    >
      <span className="vf-bubble-core">
        <span className="vf-bubble-face" aria-hidden="true">
          <i />
          <i />
        </span>
        <span className="vf-bubble-text">Want To Know?</span>
      </span>
      <span className="vf-bubble-tail" aria-hidden="true" />
    </button>
  )
}
