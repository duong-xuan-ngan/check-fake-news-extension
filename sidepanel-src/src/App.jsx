import { useState, useEffect, useCallback, useRef } from 'react'
import { ShieldCheck, Moon, Sun, PenLine, Search, CircleX, CircleCheck, CircleAlert, CircleMinus, ExternalLink, Zap } from 'lucide-react'
import './App.css'

const API_BASE = 'http://localhost:8000'

const LOADING_MESSAGES = [
  'Analyzing text...',
  'Searching for related sources...',
  'Cross-referencing data...',
  'Verifying source credibility...',
  'Almost there...',
]

const VERDICT_CONFIG = {
  TRUE: {
    color: 'var(--success)',
    bg: 'rgba(34, 197, 94, 0.1)',
    border: 'rgba(34, 197, 94, 0.3)',
    icon: CircleCheck,
    label: 'True',
  },
  FALSE: {
    color: 'var(--danger)',
    bg: 'rgba(239, 68, 68, 0.1)',
    border: 'rgba(239, 68, 68, 0.3)',
    icon: CircleX,
    label: 'False',
  },
  UNVERIFIED: {
    color: 'var(--warning)',
    bg: 'rgba(245, 158, 11, 0.1)',
    border: 'rgba(245, 158, 11, 0.3)',
    icon: CircleAlert,
    label: 'Unverified',
  },
  NOT_SURE: {
    color: 'var(--text-muted)',
    bg: 'var(--bg-tertiary)',
    border: 'var(--border-color)',
    icon: CircleMinus,
    label: 'Not Sure',
  },
}

const STANCE_CONFIG = {
  SUPPORTS: { color: 'var(--success)', bg: 'rgba(34, 197, 94, 0.1)' },
  CONTRADICTS: { color: 'var(--danger)', bg: 'rgba(239, 68, 68, 0.1)' },
  NEUTRAL: { color: 'var(--text-muted)', bg: 'var(--bg-tertiary)' },
}

function credBarColor(score) {
  if (score >= 0.7) return 'var(--success)'
  if (score >= 0.5) return 'var(--warning)'
  return 'var(--danger)'
}

function VerdictBanner({ result }) {
  const config = VERDICT_CONFIG[result.verdict] || VERDICT_CONFIG.NOT_SURE
  const Icon = config.icon
  return (
    <div className="verdict-banner" style={{ background: config.bg, borderColor: config.border }}>
      <div className="verdict-header">
        <div className="verdict-label" style={{ color: config.color }}>
          <Icon size={20} />
          <span>{config.label}</span>
        </div>
        <div className="verdict-badges">
          {result.confidence && (
            <span className={`confidence-badge confidence-${result.confidence.toLowerCase()}`}>
              {result.confidence}
            </span>
          )}
          {result.cached && (
            <span className="cached-badge">
              <Zap size={11} />
              Cached
            </span>
          )}
        </div>
      </div>
      {result.verdict === 'NOT_SURE' ? (
        <p className="not-sure-text">Insufficient evidence to determine credibility.</p>
      ) : (
        result.explanation && (
          <p className="verdict-explanation">{result.explanation}</p>
        )
      )}
    </div>
  )
}

function SourceItem({ source }) {
  const stance = STANCE_CONFIG[source.stance] || STANCE_CONFIG.NEUTRAL
  const score = source.credibility_score ?? 0
  return (
    <div className="source-item">
      <div className="source-header">
        <span className="source-domain">{source.domain}</span>
        <span className="stance-chip" style={{ color: stance.color, background: stance.bg }}>
          {source.stance}
        </span>
      </div>
      <a href={source.url} target="_blank" rel="noopener noreferrer" className="source-title">
        {source.title}
        <ExternalLink size={11} />
      </a>
      <div className="credibility-bar-wrap">
        <div className="credibility-bar-bg">
          <div
            className="credibility-bar-fill"
            style={{ width: `${Math.round(score * 100)}%`, background: credBarColor(score) }}
          />
        </div>
        <span className="credibility-score">{Math.round(score * 100)}%</span>
      </div>
    </div>
  )
}

function App() {
  const [selectedText, setSelectedText] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [tooLong, setTooLong] = useState(false)
  const [loadingMessage, setLoadingMessage] = useState('')
  const [theme, setTheme] = useState(() => localStorage.getItem('fn-theme') || 'light')
  const loadingTimeoutRef = useRef(null)
  const loadingIntervalRef = useRef(null)
  const messageIdxRef = useRef(0)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('fn-theme', theme)
  }, [theme])

  useEffect(() => {
    const handleMessage = (message) => {
      if (message.type === 'TEXT_SELECTED' && message.text) {
        setSelectedText(message.text)
        setTooLong(false)
        setResult(null)
        setError(null)
      } else if (message.type === 'SELECTION_TOO_LONG' && message.text) {
        setSelectedText(message.text)
        setTooLong(true)
        setResult(null)
        setError(null)
      }
    }
    if (typeof chrome !== 'undefined' && chrome.runtime?.onMessage) {
      chrome.runtime.onMessage.addListener(handleMessage)
      return () => chrome.runtime.onMessage.removeListener(handleMessage)
    }
  }, [])

  useEffect(() => {
    if (!loading) {
      clearTimeout(loadingTimeoutRef.current)
      clearInterval(loadingIntervalRef.current)
      setLoadingMessage('')
      return
    }
    messageIdxRef.current = 0
    loadingTimeoutRef.current = setTimeout(() => {
      setLoadingMessage(LOADING_MESSAGES[0])
      messageIdxRef.current = 1
      loadingIntervalRef.current = setInterval(() => {
        setLoadingMessage(LOADING_MESSAGES[messageIdxRef.current % LOADING_MESSAGES.length])
        messageIdxRef.current += 1
      }, 3000)
    }, 5000)
    return () => {
      clearTimeout(loadingTimeoutRef.current)
      clearInterval(loadingIntervalRef.current)
    }
  }, [loading])

  const toggleTheme = () => setTheme(prev => prev === 'light' ? 'dark' : 'light')

  const handleAnalyze = useCallback(async () => {
    if (!selectedText.trim() || selectedText.length > 2000) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const response = await fetch(`${API_BASE}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: selectedText }),
      })
      if (!response.ok) throw new Error(`Server error: ${response.status}`)
      const data = await response.json()
      setResult(data)
    } catch (err) {
      setError(err.message || 'Failed to connect to server')
    } finally {
      setLoading(false)
    }
  }, [selectedText])

  const handleClear = () => {
    setSelectedText('')
    setResult(null)
    setError(null)
    setTooLong(false)
  }

  const isOverLimit = selectedText.length > 2000

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="header-left">
          <div className="logo-icon">
            <ShieldCheck size={20} />
          </div>
          <h1 className="header-title">Fake News Checker</h1>
        </div>
        <button
          className="theme-toggle"
          onClick={toggleTheme}
          title={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
          id="theme-toggle-btn"
        >
          {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
        </button>
      </header>

      {/* Main content */}
      <main className="app-main">
        {/* Selected Text Section */}
        <section className="section">
          <div className="section-header">
            <label htmlFor="selected-text" className="section-label">
              <PenLine size={14} />
              Selected Text
            </label>
            {selectedText && (
              <button className="clear-btn" onClick={handleClear} id="clear-btn">
                Clear
              </button>
            )}
          </div>
          <textarea
            id="selected-text"
            className={`text-area${isOverLimit ? ' text-area--error' : ''}`}
            value={selectedText}
            onChange={(e) => {
              setSelectedText(e.target.value)
              setTooLong(e.target.value.length > 2000)
            }}
            placeholder="Highlight text on any webpage to capture it here, or paste text manually..."
            rows={6}
          />
          <div className={`char-count${isOverLimit ? ' char-count--error' : ''}`}>
            {selectedText.length} / 2,000 characters
          </div>
        </section>

        {/* Over-limit warning */}
        {isOverLimit && (
          <div className="warning-box" id="warning-too-long">
            <CircleAlert size={15} />
            <span>Please select a shorter passage (max 2,000 characters)</span>
          </div>
        )}

        {/* Analyze Button */}
        <button
          className={`analyze-btn ${loading ? 'loading' : ''}`}
          onClick={handleAnalyze}
          disabled={!selectedText.trim() || loading || isOverLimit}
          id="analyze-btn"
        >
          {loading ? (
            <>
              <span className="spinner" />
              Analyzing...
            </>
          ) : (
            <>
              <Search size={16} />
              Analyze Text
            </>
          )}
        </button>

        {/* Rotating loading message (shown after 5s) */}
        {loading && loadingMessage && (
          <p className="loading-message" key={loadingMessage}>{loadingMessage}</p>
        )}

        {/* Error */}
        {error && (
          <div className="error-box" id="error-box">
            <CircleX size={16} />
            <span>{error}</span>
          </div>
        )}

        {/* Result */}
        {result && (
          <section className="result-section" id="result-section">
            <div className="section-header">
              <span className="section-label">
                <CircleCheck size={14} />
                Analysis Result
              </span>
            </div>

            <VerdictBanner result={result} />

            {result.sources && result.sources.length > 0 && (
              <div className="sources-section">
                <p className="sources-title">Sources</p>
                {result.sources.map((source, i) => (
                  <SourceItem key={i} source={source} />
                ))}
              </div>
            )}
          </section>
        )}
      </main>

      {/* Footer */}
      <footer className="app-footer">
        <span>Fake News Checker Extension</span>
      </footer>
    </div>
  )
}

export default App
