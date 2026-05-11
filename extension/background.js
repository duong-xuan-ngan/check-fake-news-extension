// Open side panel when extension icon is clicked
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true })

// Create context menu item
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: 'analyze-selection',
    title: 'Analyze with Fake News Checker',
    contexts: ['selection'],
  })
})

// Handle context menu click — open side panel and send selected text
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId === 'analyze-selection' && info.selectionText) {
    // Open the side panel first
    await chrome.sidePanel.open({ tabId: tab.id })

    // Small delay to let the panel load, then send the text
    setTimeout(() => {
      chrome.runtime.sendMessage({
        type: 'TEXT_SELECTED',
        text: info.selectionText,
      })
    }, 500)
  }
})

// Relay messages from content script to side panel
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'TEXT_SELECTED') {
    // Forward to all extension pages (side panel will pick it up)
    chrome.runtime.sendMessage(message)
  }
})
