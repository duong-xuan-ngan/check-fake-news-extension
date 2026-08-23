import {
  Check,
  ChevronRight,
  Circle,
  ExternalLink,
  Gauge,
  GripVertical,
  LogIn,
  MessageCircle,
  Settings,
  Shield,
  Sparkles,
  X,
} from 'lucide-react'

const BRAND_LOGO_URL = chrome.runtime.getURL('icons/SnapCheck_MainMenu.png')

const VERDICT_UI = {
  TRUE: {
    label: 'Likely True',
    tone: 'High credibility',
    color: '#15803d',
    soft: '#effaf2',
    border: '#bbf7d0',
    gradient: 'linear-gradient(135deg, #86efac, #22c55e)',
    icon: Check,
  },
  FALSE: {
    label: 'Likely False',
    tone: 'Low credibility',
    color: '#b91c1c',
    soft: '#fff1f2',
    border: '#fecdd3',
    gradient: 'linear-gradient(135deg, #fca5a5, #ef4444)',
    icon: X,
  },
  UNVERIFIED: {
    label: 'Not Sure',
    tone: 'Unverified',
    color: '#b45309',
    soft: '#fffbeb',
    border: '#fde68a',
    gradient: 'linear-gradient(135deg, #fde68a, #f59e0b)',
    icon: null,
  },
  NOT_SURE: {
    label: 'Not Sure',
    tone: 'Unverified',
    color: '#b45309',
    soft: '#fffbeb',
    border: '#fde68a',
    gradient: 'linear-gradient(135deg, #fde68a, #f59e0b)',
    icon: null,
  },
}

const confidenceToPercent = (confidence) => {
  if (typeof confidence === 'number') return Math.max(0, Math.min(100, Math.round(confidence)))
  if (confidence === 'HIGH') return 86
  if (confidence === 'MEDIUM') return 62
  if (confidence === 'LOW') return 34
  return 50
}

function VerdictIcon({ ui }) {
  const Icon = ui.icon

  return (
    <div className="vf-verdict-icon" style={{ background: ui.gradient }}>
      {Icon ? <Icon size={27} strokeWidth={3.2} /> : <span>?</span>}
    </div>
  )
}

function SourceLogo({ domain }) {
  const initials = (domain || 'SRC')
    .replace(/^www\./, '')
    .split('.')
    .filter(Boolean)[0]
    ?.slice(0, 3)
    .toUpperCase() || 'SRC'

  return <div className="vf-source-logo">{initials}</div>
}

function SourceRow({ source }) {
  const isUnrated = source.rating_status === 'UNRATED' || source.credibility_score == null
  const score = source.credibility_score
  const label = isUnrated ? 'Unrated' : score >= 0.7 ? 'High' : score >= 0.45 ? 'Medium' : 'Low'
  const color = isUnrated ? '#64748b' : score >= 0.7 ? '#16a34a' : score >= 0.45 ? '#d97706' : '#dc2626'

  return (
    <a href={source.url} target="_blank" rel="noopener noreferrer" className="vf-source-row" title={source.title}>
      <SourceLogo domain={source.domain} />
      <div className="vf-source-copy">
        <span className="vf-source-title">{source.title || source.domain || 'Source'}</span>
        <span className="vf-source-domain">{source.domain || source.url}</span>
      </div>
      <span className="vf-source-score" style={{ color }}>
        <Circle size={8} fill="currentColor" strokeWidth={0} />
        {label}
      </span>
      <ExternalLink className="vf-source-link" size={15} />
    </a>
  )
}

/**
 * Presentational only. Fetch/loading/cancel/positioning/drag orchestration all
 * live in content.jsx — this component renders the given state and forwards
 * the drag handle's pointerdown to whatever handler content.jsx supplies.
 */
export default function PopupApp({ result, error, signInRequired, quotaExceeded, onSignIn, onClose, onDragHandlePointerDown, onViewFullReport }) {
  const ui = VERDICT_UI[result?.verdict] || VERDICT_UI.NOT_SURE
  const confidence = result ? confidenceToPercent(result.confidence) : 0
  const sources = result?.sources || []
  const summary = result?.explanation || 'There is not enough reliable evidence to verify this claim yet.'

  return (
    <section className="verifact-popup">
      <header className="vf-header">
        <div className="vf-header-left">
          <button
            type="button"
            className="vf-drag-handle"
            onPointerDown={onDragHandlePointerDown}
            title="Drag to move"
            aria-label="Drag to move"
          >
            <GripVertical size={16} />
          </button>
          <div className="vf-brand">
            <span className="vf-brand-logo-frame">
              <img className="vf-brand-logo" src={BRAND_LOGO_URL} alt="SnapCheck — Check before you trust." />
            </span>
          </div>
        </div>
        <button className="vf-icon-button" onClick={onClose} title="Close">
          <X size={18} />
        </button>
      </header>

      <div className="vf-body">
        {signInRequired && (
          <div className="vf-error">
            <div className="vf-error-mark vf-error-mark--accent">
              <LogIn size={28} />
            </div>
            <h2>Sign in required</h2>
            <p>Sign in with Google to check claims.</p>
            <button className="vf-signin-button" type="button" onClick={onSignIn}>
              Sign in with Google
            </button>
          </div>
        )}

        {quotaExceeded && (
          <div className="vf-error">
            <div className="vf-error-mark vf-error-mark--accent">
              <Gauge size={28} />
            </div>
            <h2>Daily limit reached</h2>
            <p>You've used all 5 checks for today. Your limit resets at midnight UTC.</p>
            <button className="vf-signin-button" type="button" onClick={onSignIn}>
              View usage
            </button>
          </div>
        )}

        {error && (
          <div className="vf-error">
            <div className="vf-error-mark">
              <Shield size={28} />
            </div>
            <h2>Analysis failed</h2>
            <p>{error}</p>
          </div>
        )}

        {result && !error && (
          <div className="vf-result-grid">
            <aside className="vf-verdict-card" style={{ background: ui.soft, borderColor: ui.border }}>
              <div className="vf-verdict-top">
                <VerdictIcon ui={ui} />
                <div>
                  <h2 style={{ color: ui.color }}>{ui.label}</h2>
                  <span style={{ color: ui.color }}>{ui.tone}</span>
                </div>
              </div>

              <div className="vf-meter" aria-label={`Confidence ${confidence}%`}>
                <div style={{ width: `${confidence}%`, background: ui.gradient }} />
              </div>

              <strong className="vf-confidence">Confidence {confidence}%</strong>
              <p>{summary}</p>
            </aside>

            <main className="vf-details">
              <section>
                <div className="vf-section-title">
                  <Sparkles size={19} fill="#22c55e" strokeWidth={0} />
                  <h2>AI Summary</h2>
                </div>
                <p className="vf-summary">{summary}</p>
                <button className="vf-full-report-button" type="button" onClick={() => onViewFullReport(result)}>
                  View full report <ChevronRight size={15} />
                </button>
              </section>

              <section>
                <div className="vf-section-title vf-section-title-row">
                  <h2>Sources</h2>
                  <span>
                    {sources.length} found <ChevronRight size={15} />
                  </span>
                </div>
                <div className="vf-source-list">
                  {sources.length > 0 ? (
                    sources.map((source, index) => <SourceRow key={`${source.url || source.title}-${index}`} source={source} />)
                  ) : (
                    <div className="vf-empty-source">No sources found for this claim.</div>
                  )}
                </div>
              </section>
            </main>
          </div>
        )}
      </div>

      <footer className="vf-footer">
        <button className="vf-icon-button" title="Feedback" aria-label="Feedback">
          <MessageCircle size={17} />
        </button>
        <button className="vf-icon-button" title="Settings" aria-label="Settings">
          <Settings size={17} />
        </button>
      </footer>
    </section>
  )
}
