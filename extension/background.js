// Create context menu item
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: 'analyze-selection',
    title: 'Check with SnapCheck',
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

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type !== 'OPEN_FULL_REPORT' || !message.result) return

  chrome.storage.session
    .set({ snapcheckFullReport: message.result })
    .then(() => chrome.tabs.create({ url: chrome.runtime.getURL('report.html') }))
    .then(() => sendResponse({ ok: true }))
    .catch((error) => sendResponse({ ok: false, error: error.message }))

  return true
})
