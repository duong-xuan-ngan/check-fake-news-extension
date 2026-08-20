// Create context menu item
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: 'analyze-selection',
    title: 'Analyze with Fake News Checker',
    contexts: ['selection'],
  })
})

// Handle context menu click — send message to content script
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId === 'analyze-selection' && info.selectionText) {
    chrome.tabs.sendMessage(tab.id, {
      type: 'TEXT_SELECTED',
      text: info.selectionText,
    })
  }
})

// Google token for the current session — kept in memory so sign-out can revoke it.
let cachedGoogleToken = null

function base64UrlEncode(bytes) {
  let binary = ''
  bytes.forEach((b) => {
    binary += String.fromCharCode(b)
  })
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

async function buildAuthUrl(clientId) {
  const verifier = base64UrlEncode(crypto.getRandomValues(new Uint8Array(32)))
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier))
  const challenge = base64UrlEncode(new Uint8Array(digest))
  const redirectUri = `https://${chrome.runtime.id}.chromiumapp.org/`
  const params = new URLSearchParams({
    response_type: 'code',
    client_id: clientId,
    redirect_uri: redirectUri,
    scope: 'openid email profile',
    code_challenge: challenge,
    code_challenge_method: 'S256',
  })
  return { url: `https://accounts.google.com/o/oauth2/v2/auth?${params}`, verifier, redirectUri }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'OPEN_OPTIONS') {
    chrome.runtime.openOptionsPage()
    return false
  }

  if (message.type === 'AUTH_GET_GOOGLE_TOKEN') {
    if (!message.clientId) {
      sendResponse({ error: 'VITE_GOOGLE_CLIENT_ID is not configured' })
      return false
    }

    buildAuthUrl(message.clientId).then(({ url, verifier, redirectUri }) => {
      chrome.identity.launchWebAuthFlow({ url, interactive: true }, (redirectUrl) => {
        if (chrome.runtime.lastError || !redirectUrl) {
          sendResponse({ error: chrome.runtime.lastError?.message || 'Sign-in cancelled' })
          return
        }
        const code = new URLSearchParams(new URL(redirectUrl).search).get('code')
        if (!code) {
          sendResponse({ error: 'No authorization code returned' })
          return
        }
        sendResponse({ code, codeVerifier: verifier, redirectUri })
      })
    })
    return true
  }

  if (message.type === 'AUTH_SIGN_OUT') {
    const finish = () => {
      cachedGoogleToken = null
      sendResponse({ ok: true })
    }
    if (cachedGoogleToken) {
      chrome.identity.removeCachedAuthToken({ token: cachedGoogleToken }, finish)
    } else {
      finish()
    }
    return true
  }

  return false
})
