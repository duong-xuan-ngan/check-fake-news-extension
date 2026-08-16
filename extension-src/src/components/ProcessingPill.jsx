import { X } from 'lucide-react'

/**
 * Small fixed, bottom-center indicator shown while analysis is in flight.
 * Click anywhere on it to cancel — ring/core fade out, an X fades in on hover.
 */
export default function ProcessingPill({ onCancel }) {
  return (
    <button type="button" className="vf-pill" onClick={onCancel} aria-label="Cancel fact-check">
      <span className="vf-pill-ring" aria-hidden="true" />
      <span className="vf-pill-core" aria-hidden="true" />
      <span className="vf-pill-cancel" aria-hidden="true">
        <X size={18} strokeWidth={2.4} />
      </span>
    </button>
  )
}
