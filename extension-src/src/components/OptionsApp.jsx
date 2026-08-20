import { useEffect, useState } from 'react'
import { LogOut } from 'lucide-react'
import { apiFetch, getSession, saveSession } from '../lib/api.js'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'
const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || ''
const APP_VERSION = chrome.runtime.getManifest().version

function getResetCountdown(timestamp) {
  const d = new Date(timestamp)
  const next = Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate() + 1)
  const diffMs = Math.max(0, next - timestamp)
  const hours = Math.floor(diffMs / 3600000)
  const mins = Math.floor((diffMs % 3600000) / 60000)
  return `${hours}h ${mins}m`
}

export default function OptionsApp() {
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [usage, setUsage] = useState(null)
  const [confirmSignOut, setConfirmSignOut] = useState(false)
  const [now, setNow] = useState(Date.now())

  useEffect(() => {
    getSession().then((data) => {
      setSession(data)
      setLoading(false)
    })
  }, [])

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 60000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    if (!session?.accessToken) {
      setUsage(null)
      return
    }
    apiFetch('/usage')
      .then((response) => {
        if (response.status === 401) {
          setSession(null)
          return null
        }
        return response.ok ? response.json() : null
      })
      .then((data) => setUsage(data))
      .catch(() => setUsage(null))
  }, [session])

  const signIn = async () => {
    setBusy(true)
    setError(null)
    try {
      const tokenResp = await chrome.runtime.sendMessage({
        type: 'AUTH_GET_GOOGLE_TOKEN',
        clientId: GOOGLE_CLIENT_ID,
      })
      if (!tokenResp || !tokenResp.code) throw new Error(tokenResp?.error || 'Google sign-in was cancelled')

      const response = await fetch(`${API_BASE}/auth/google`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code: tokenResp.code,
          code_verifier: tokenResp.codeVerifier,
          redirect_uri: tokenResp.redirectUri,
        }),
      })
      if (!response.ok) throw new Error(`Server error: ${response.status}`)

      const data = await response.json()
      const next = {
        accessToken: data.access_token,
        refreshToken: data.refresh_token,
        user: data.user,
      }
      await saveSession(next)
      setSession(next)
    } catch (err) {
      setError(err.message || 'Sign-in failed')
    } finally {
      setBusy(false)
    }
  }

  const signOut = async () => {
    setBusy(true)
    setError(null)
    setConfirmSignOut(false)
    const session = await getSession()
    if (session?.refreshToken) {
      try {
        await fetch(`${API_BASE}/auth/logout`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: session.refreshToken }),
        })
      } catch {
        // Best-effort server-side revocation.
      }
    }
    try {
      await chrome.runtime.sendMessage({ type: 'AUTH_SIGN_OUT' })
    } catch {
      // Sign-out revoke is best-effort; still clear the local session below.
    }
    await saveSession(null)
    setSession(null)
    setBusy(false)
  }

  if (loading) {
    return <div className="vf-options-loading">Loading…</div>
  }

  const remainingPct = usage ? Math.max(0, Math.round((usage.remaining / usage.limit) * 100)) : 0

  return (
    <main className="vf-options-page">
      <div className="vf-options-card">
        <h1>SnapCheck Account</h1>

        {session ? (
          <>
            <div className="vf-account">
              {session.user?.picture ? (
                <img className="vf-account-avatar" src={session.user.picture} alt="" referrerPolicy="no-referrer" />
              ) : (
                <div className="vf-account-avatar">{(session.user?.name || session.user?.email || '?').charAt(0).toUpperCase()}</div>
              )}
              <div className="vf-account-copy">
                <strong>{session.user?.name || 'Signed in'}</strong>
                <span>{session.user?.email}</span>
              </div>
            </div>

            {usage && (
              <div className="vf-usage-block">
                <div className="vf-usage-head">
                  <span>Daily checks</span>
                  <strong>
                    {usage.remaining} / {usage.limit} left
                  </strong>
                </div>
                <div className="vf-usage-bar" aria-label={`${usage.remaining} of ${usage.limit} checks remaining`}>
                  <div style={{ width: `${remainingPct}%` }} />
                </div>
                <span className="vf-usage-reset">Resets in {getResetCountdown(now)}</span>
              </div>
            )}

            <div className="vf-account-actions">
              {confirmSignOut ? (
                <>
                  <button type="button" className="vf-options-button" onClick={signOut} disabled={busy}>
                    Confirm sign out
                  </button>
                  <button type="button" className="vf-options-button vf-options-button--ghost" onClick={() => setConfirmSignOut(false)} disabled={busy}>
                    Cancel
                  </button>
                </>
              ) : (
                <button type="button" className="vf-options-button vf-options-button--danger" onClick={() => setConfirmSignOut(true)}>
                  <LogOut size={15} />
                  Sign out
                </button>
              )}
            </div>
          </>
        ) : (
          <div className="vf-signin">
            <p>Sign in with Google to fact-check claims.</p>
            <button type="button" className="vf-options-button" onClick={signIn} disabled={busy}>
              {busy ? 'Signing in…' : 'Sign in with Google'}
            </button>
          </div>
        )}

        {error && <p className="vf-options-error">{error}</p>}

        <footer className="vf-options-footer">
          <a href="#" onClick={(e) => e.preventDefault()}>Privacy</a>
          <a href="#" onClick={(e) => e.preventDefault()}>Terms</a>
          <a href="#" onClick={(e) => e.preventDefault()}>Feedback</a>
          <span className="vf-options-version">v{APP_VERSION}</span>
        </footer>
      </div>
    </main>
  )
}
