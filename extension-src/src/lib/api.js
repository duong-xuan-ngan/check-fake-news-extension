const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'
const SESSION_KEY = 'vf_session'

export async function getSession() {
  const data = await chrome.storage.local.get(SESSION_KEY)
  return data[SESSION_KEY] || null
}

export async function saveSession(session) {
  if (session) {
    await chrome.storage.local.set({ [SESSION_KEY]: session })
  } else {
    await chrome.storage.local.remove(SESSION_KEY)
  }
}

let refreshInFlight = null

async function refreshSession() {
  if (refreshInFlight) return refreshInFlight

  refreshInFlight = (async () => {
    const session = await getSession()
    if (!session?.refreshToken) return null
    try {
      const response = await fetch(`${API_BASE}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: session.refreshToken }),
      })
      if (!response.ok) return null
      const data = await response.json()
      const next = {
        accessToken: data.access_token,
        refreshToken: data.refresh_token,
        user: session.user,
      }
      await saveSession(next)
      return next
    } catch {
      return null
    }
  })()

  try {
    return await refreshInFlight
  } finally {
    refreshInFlight = null
  }
}

/**
 * Fetch with automatic bearer token + silent refresh-once-retry.
 * Returns the final response; on auth failure the session is cleared.
 */
export async function apiFetch(path, { auth = true, ...options } = {}) {
  let session = await getSession()

  const doFetch = (token) =>
    fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        ...(options.headers || {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    })

  let response = await doFetch(session?.accessToken)

  if (auth && response.status === 401) {
    const refreshed = await refreshSession()
    if (refreshed) {
      response = await doFetch(refreshed.accessToken)
    } else {
      await saveSession(null)
    }
  }

  return response
}
