const content = document.getElementById('report-content')

const verdictLabels = {
  TRUE: 'Likely True',
  FALSE: 'Likely False',
  UNVERIFIED: 'Not Sure',
  NOT_SURE: 'Not Sure',
}

function addTextElement(tag, className, text) {
  const element = document.createElement(tag)
  element.className = className
  element.textContent = text
  return element
}

function safeExternalUrl(value) {
  if (typeof value !== 'string') return null
  try {
    const url = new URL(value)
    return url.protocol === 'https:' || url.protocol === 'http:' ? url.href : null
  } catch {
    return null
  }
}

function credibilityLabel(score) {
  if (typeof score !== 'number') return null
  if (score >= 0.7) return 'High credibility'
  if (score >= 0.45) return 'Medium credibility'
  return 'Low credibility'
}

function createSource(source) {
  const safeUrl = safeExternalUrl(source?.url)
  const item = document.createElement(safeUrl ? 'a' : 'div')
  item.className = 'report-source'

  if (safeUrl) {
    item.href = safeUrl
    item.target = '_blank'
    item.rel = 'noopener noreferrer'
  }

  const title = source?.title || source?.domain || source?.url || 'Source'
  item.append(addTextElement('strong', 'report-source-title', title))

  const details = [source?.domain, credibilityLabel(source?.credibility_score)].filter(Boolean).join(' · ')
  if (details) item.append(addTextElement('span', 'report-source-details', details))

  return item
}

chrome.storage.session.get('snapcheckFullReport').then(({ snapcheckFullReport: report }) => {
  if (!report || typeof report !== 'object') {
    content.append(addTextElement('p', 'report-empty', 'No report is available yet. Run a SnapCheck analysis, then choose “View full report.”'))
    return
  }

  const verdict = verdictLabels[report.verdict] || 'Not Sure'
  content.append(addTextElement('p', 'report-eyebrow', verdict))
  content.append(addTextElement('h1', 'report-title', 'Full report'))
  content.append(
    addTextElement(
      'p',
      'report-explanation',
      report.explanation || 'There is not enough reliable evidence to verify this claim yet.'
    )
  )

  const sources = Array.isArray(report.sources) ? report.sources : []
  content.append(addTextElement('h2', 'report-sources-heading', 'Sources (' + sources.length + ')'))

  if (sources.length === 0) {
    content.append(addTextElement('p', 'report-empty', 'No sources were returned for this analysis.'))
    return
  }

  const list = document.createElement('div')
  list.className = 'report-sources'
  sources.forEach((source) => list.append(createSource(source)))
  content.append(list)
})
