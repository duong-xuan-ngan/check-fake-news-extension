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
