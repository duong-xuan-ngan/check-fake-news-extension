// Content script — captures selected text and sends to extension

document.addEventListener('mouseup', () => {
  const selectedText = window.getSelection().toString().trim()

  if (selectedText && selectedText.length > 0) {
    chrome.runtime.sendMessage({
      type: selectedText.length > 2000 ? 'SELECTION_TOO_LONG' : 'TEXT_SELECTED',
      text: selectedText,
    })
  }
})
