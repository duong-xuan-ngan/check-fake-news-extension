import React, { useState, useEffect, useCallback, useRef } from 'react'
import { ShieldCheck, X, Loader2, CircleCheck, CircleX, CircleMinus, CircleAlert, ExternalLink, ShieldAlert } from 'lucide-react'

const API_BASE = 'http://localhost:8000'

const VERDICT_CONFIG = {
  TRUE: {
    color: 'text-green-600',
    bg: 'bg-green-100',
    border: 'border-green-300',
    icon: CircleCheck,
    label: 'True',
  },
  FALSE: {
    color: 'text-red-600',
    bg: 'bg-red-100',
    border: 'border-red-300',
    icon: CircleX,
    label: 'False',
  },
  UNVERIFIED: {
    color: 'text-amber-600',
    bg: 'bg-amber-100',
    border: 'border-amber-300',
    icon: CircleAlert,
    label: 'Unverified',
  },
  NOT_SURE: {
    color: 'text-slate-500',
    bg: 'bg-slate-100',
    border: 'border-slate-300',
    icon: CircleMinus,
    label: 'Not Sure',
  },
}

const STANCE_CONFIG = {
  SUPPORTS: { color: 'text-green-700', bg: 'bg-green-100' },
  CONTRADICTS: { color: 'text-red-700', bg: 'bg-red-100' },
  NEUTRAL: { color: 'text-slate-700', bg: 'bg-slate-100' },
}

function credBarColor(score) {
  if (score >= 0.7) return 'bg-green-500'
  if (score >= 0.5) return 'bg-amber-500'
  return 'bg-red-500'
}

export default function PopupApp({ selectedText, onClose }) {
  const [activeTab, setActiveTab] = useState('analysis')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const hasFetched = useRef(false)

  const handleAnalyze = useCallback(async () => {
    if (!selectedText.trim() || hasFetched.current) return
    hasFetched.current = true
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

  useEffect(() => {
    handleAnalyze()
  }, [handleAnalyze])

  return (
    <div className="w-[400px] h-[500px] bg-white rounded-xl shadow-[0_10px_40px_-10px_rgba(0,0,0,0.3)] border border-slate-200 flex flex-col font-sans overflow-hidden">
      {/* Header */}
      <header className="flex items-center justify-between px-4 py-3 bg-white border-b border-slate-100 shadow-sm z-10">
        <div className="flex items-center gap-2">
          <div className="text-blue-500 flex items-center justify-center bg-blue-50 p-1.5 rounded-lg">
            <ShieldCheck size={20} strokeWidth={2.5} />
          </div>
          <h1 className="font-semibold text-slate-800 text-sm tracking-tight m-0 p-0">Fake News Checker</h1>
        </div>
        <button onClick={onClose} className="text-slate-400 hover:text-slate-600 transition-colors p-1 rounded-md hover:bg-slate-50 cursor-pointer border-none bg-transparent">
          <X size={18} />
        </button>
      </header>

      {/* Tabs */}
      <div className="flex border-b border-slate-200 bg-slate-50/50">
        <button
          onClick={() => setActiveTab('analysis')}
          className={`flex-1 py-3 text-sm font-medium transition-colors border-b-2 cursor-pointer bg-transparent m-0 ${activeTab === 'analysis' ? 'border-blue-500 text-blue-600 bg-white' : 'border-transparent text-slate-500 hover:text-slate-700 hover:bg-slate-50'}`}
        >
          Analysis
        </button>
        <button
          onClick={() => setActiveTab('sources')}
          className={`flex-1 py-3 text-sm font-medium transition-colors border-b-2 cursor-pointer bg-transparent m-0 ${activeTab === 'sources' ? 'border-blue-500 text-blue-600 bg-white' : 'border-transparent text-slate-500 hover:text-slate-700 hover:bg-slate-50'}`}
        >
          Sources {result?.sources && <span className="ml-1.5 bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded-full text-xs">{result.sources.length}</span>}
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto bg-slate-50/30">
        {loading && (
          <div className="flex flex-col items-center justify-center h-full p-8 text-center space-y-4">
            <Loader2 className="w-8 h-8 text-blue-500 animate-spin mx-auto" />
            <p className="text-sm text-slate-500 font-medium animate-pulse m-0">Analyzing claim credibility...</p>
          </div>
        )}

        {error && !loading && (
          <div className="flex flex-col items-center justify-center h-full p-8 text-center space-y-3">
            <div className="w-12 h-12 bg-red-50 text-red-500 rounded-full flex items-center justify-center mb-2 mx-auto">
              <ShieldAlert size={24} />
            </div>
            <h3 className="font-semibold text-slate-800 m-0">Analysis Failed</h3>
            <p className="text-sm text-slate-500 m-0">{error}</p>
          </div>
        )}

        {!loading && !error && result && (
          <div className="p-5 h-full box-border">
            {activeTab === 'analysis' && (
              <div className="space-y-5 animate-in fade-in duration-300">
                {/* Verdict Badge */}
                <div className={`p-4 rounded-xl border ${VERDICT_CONFIG[result.verdict]?.bg || VERDICT_CONFIG.NOT_SURE.bg} ${VERDICT_CONFIG[result.verdict]?.border || VERDICT_CONFIG.NOT_SURE.border}`}>
                  <div className="flex items-start justify-between mb-3">
                    <div className={`flex items-center gap-2 font-bold text-lg ${VERDICT_CONFIG[result.verdict]?.color || VERDICT_CONFIG.NOT_SURE.color}`}>
                      {React.createElement(VERDICT_CONFIG[result.verdict]?.icon || VERDICT_CONFIG.NOT_SURE.icon, { size: 22, strokeWidth: 2.5 })}
                      {VERDICT_CONFIG[result.verdict]?.label || VERDICT_CONFIG.NOT_SURE.label}
                    </div>
                    {result.confidence && (
                      <span className={`px-2.5 py-1 text-xs font-bold uppercase tracking-wider rounded-md bg-white shadow-sm border border-slate-200 ${result.confidence === 'HIGH' ? 'text-green-700' : result.confidence === 'MEDIUM' ? 'text-amber-700' : 'text-slate-500'}`}>
                        {result.confidence} CONFIDENCE
                      </span>
                    )}
                  </div>
                  
                  {result.explanation ? (
                    <p className="text-sm text-slate-700 leading-relaxed font-medium m-0">
                      {result.explanation}
                    </p>
                  ) : (
                    <p className="text-sm text-slate-500 italic m-0">No detailed explanation provided.</p>
                  )}
                </div>

                {/* Selected Text context */}
                <div className="space-y-2 mt-5">
                  <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider m-0">Analyzed Claim</h3>
                  <div className="bg-white p-3.5 rounded-lg border border-slate-200 shadow-sm">
                    <p className="text-sm text-slate-600 italic line-clamp-4 leading-relaxed border-l-2 border-blue-400 pl-3 m-0">
                      "{selectedText}"
                    </p>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'sources' && (
              <div className="space-y-3 animate-in fade-in duration-300 pb-4">
                {result.sources && result.sources.length > 0 ? (
                  result.sources.map((source, i) => {
                    const stance = STANCE_CONFIG[source.stance] || STANCE_CONFIG.NEUTRAL
                    const score = source.credibility_score ?? 0
                    
                    return (
                      <div key={i} className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow group mb-3">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider bg-slate-100 px-2 py-0.5 rounded-md">
                            {source.domain}
                          </span>
                          <span className={`text-xs font-bold px-2 py-0.5 rounded-md ${stance.color} ${stance.bg}`}>
                            {source.stance}
                          </span>
                        </div>
                        
                        <a href={source.url} target="_blank" rel="noopener noreferrer" className="block text-sm font-medium text-slate-800 mb-3 hover:text-blue-600 transition-colors group-hover:underline decoration-blue-300 underline-offset-2 no-underline">
                          {source.title}
                          <ExternalLink size={12} className="inline ml-1 mb-0.5 text-slate-400" />
                        </a>
                        
                        <div className="flex items-center gap-3 mt-3">
                          <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                            <div 
                              className={`h-full rounded-full ${credBarColor(score)}`}
                              style={{ width: `${Math.round(score * 100)}%` }}
                            />
                          </div>
                          <span className="text-xs font-semibold text-slate-500 w-10 text-right">
                            {Math.round(score * 100)}%
                          </span>
                        </div>
                      </div>
                    )
                  })
                ) : (
                  <div className="text-center py-10">
                    <p className="text-sm text-slate-500 m-0">No sources found for this claim.</p>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
