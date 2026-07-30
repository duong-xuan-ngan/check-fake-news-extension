import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import PopupApp from './components/PopupApp.jsx'
import './index.css'

const mountReactApp = (selectedText, rect) => {
  let container = document.getElementById('fake-news-checker-container')
  if (!container) {
    container = document.createElement('div')
    container.id = 'fake-news-checker-container'
    container.style.position = 'absolute'
    container.style.zIndex = '999999'
    document.body.appendChild(container)
    
    const shadowRoot = container.attachShadow({ mode: 'open' })
    
    // Inject the CSS
    const styleLink = document.createElement('link')
    styleLink.rel = 'stylesheet'
    styleLink.href = chrome.runtime.getURL('content.css')
    shadowRoot.appendChild(styleLink)
    
    const rootEl = document.createElement('div')
    rootEl.id = 'root'
    shadowRoot.appendChild(rootEl)
    
    const root = createRoot(rootEl)
    
    container._reactRoot = root
  }
  
  // Position it to the right of the selection
  // Add fallback logic to keep it within screen bounds
  const popupWidth = 400; // Expected width from PopupApp
  const spaceOnRight = window.innerWidth - rect.right;
  
  if (spaceOnRight > popupWidth + 20) {
    // Plenty of space on the right
    container.style.top = `${rect.top + window.scrollY}px`;
    container.style.left = `${rect.right + window.scrollX + 15}px`;
  } else {
    // Not enough space, fallback to bottom right alignment
    container.style.top = `${rect.bottom + window.scrollY + 15}px`;
    container.style.left = `${Math.max(10, rect.right + window.scrollX - popupWidth)}px`;
  }
  
  // Render
  container._reactRoot.render(
    <StrictMode>
      <PopupApp selectedText={selectedText} onClose={() => {
        container.style.display = 'none'
      }} />
    </StrictMode>
  )
  container.style.display = 'block'
}

let currentIcon = null
let currentSelection = ''

document.addEventListener('mouseup', (e) => {
  // If clicked inside our container, ignore
  const container = document.getElementById('fake-news-checker-container')
  if (container && e.composedPath().includes(container)) {
    return
  }
  // Ignore clicks on the icon itself
  if (currentIcon && e.composedPath().includes(currentIcon)) {
    return
  }

  // Remove existing icon
  if (currentIcon) {
    currentIcon.remove()
    currentIcon = null
  }
  
  // Hide popup if clicking outside
  if (container) {
    container.style.display = 'none'
  }

  const selection = window.getSelection()
  const selectedText = selection.toString().trim()

  if (selectedText && selectedText.length > 0 && selectedText.length <= 2000) {
    currentSelection = selectedText
    const range = selection.getRangeAt(0)
    const rect = range.getBoundingClientRect()

    // Create Icon
    const icon = document.createElement('img')
    icon.src = chrome.runtime.getURL('icons/icon128.png')
    icon.style.position = 'absolute'
    icon.style.width = '24px'
    icon.style.height = '24px'
    icon.style.cursor = 'pointer'
    icon.style.zIndex = '999998'
    icon.style.background = 'white'
    icon.style.borderRadius = '50%'
    icon.style.boxShadow = '0 2px 5px rgba(0,0,0,0.2)'
    
    // Position icon near the end of selection
    icon.style.top = `${rect.bottom + window.scrollY}px`
    icon.style.left = `${rect.right + window.scrollX + 5}px`

    icon.addEventListener('click', () => {
      mountReactApp(currentSelection, rect)
      icon.remove()
      currentIcon = null
    })

    document.body.appendChild(icon)
    currentIcon = icon
  }
})

// Listen to context menu message from background
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'TEXT_SELECTED' && message.text) {
    let rect = {
      bottom: window.scrollY + 100,
      left: window.scrollX + window.innerWidth / 2 - 200,
    }
    
    // Try to get real selection coordinates if still selected
    const selection = window.getSelection()
    if (selection && selection.rangeCount > 0) {
      const selectedText = selection.toString().trim()
      if (selectedText === message.text.trim()) {
        const range = selection.getRangeAt(0)
        rect = range.getBoundingClientRect()
      }
    }
    
    mountReactApp(message.text, rect)
  }
})
