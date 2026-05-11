import { useState, useEffect, useCallback } from 'react'
import { ShieldCheck, Moon, Sun, PenLine, Search, CircleX, CircleCheck } from 'lucide-react'
import './App.css'

const API_BASE = 'http://localhost:8000'

function App() {
  const [selectedText, setSelectedText] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('fn-theme') || 'light'
  })

  // Apply theme to document
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('fn-theme', theme)
  }, [theme])

  // Listen for selected text from Chrome extension content script
  useEffect(() => {
    const handleMessage = (message) => {
      if (message.type === 'TEXT_SELECTED' && message.text) {
        setSelectedText(message.text)
        setResult(null)
        setError(null)
      }
    }

    // Chrome extension environment
    if (typeof chrome !== 'undefined' && chrome.runtime?.onMessage) {
      chrome.runtime.onMessage.addListener(handleMessage)
      return () => chrome.runtime.onMessage.removeListener(handleMessage)
    }
  }, [])

  const toggleTheme = () => {
    setTheme(prev => prev === 'light' ? 'dark' : 'light')
  }

  const handleAnalyze = useCallback(async () => {
    if (!selectedText.trim()) return

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const response = await fetch(`${API_BASE}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: selectedText }),
      })

      if (!response.ok) {
        throw new Error(`Server error: ${response.status}`)
      }

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
  }

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
          {theme === 'light' ? (
            <Moon size={18} />
          ) : (
            <Sun size={18} />
          )}
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
            className="text-area"
            value={selectedText}
            onChange={(e) => setSelectedText(e.target.value)}
            placeholder="Highlight text on any webpage to capture it here, or paste text manually..."
            rows={6}
          />
          <div className="char-count">
            {selectedText.length} characters
          </div>
        </section>

        {/* Analyze Button */}
        <button
          className={`analyze-btn ${loading ? 'loading' : ''}`}
          onClick={handleAnalyze}
          disabled={!selectedText.trim() || loading}
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
            <div className="result-card">
              <pre className="result-json">{JSON.stringify(result, null, 2)}</pre>
            </div>
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
