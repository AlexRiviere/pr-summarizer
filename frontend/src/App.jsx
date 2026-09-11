import { useState } from 'react'
import { summarizePR } from './api'
import './App.css'

const PR_URL_PATTERN = /^https?:\/\/github\.com\/[^/\s]+\/[^/\s]+\/pull\/\d+\/?$/

const RISK_LABELS = {
  low: 'Low risk',
  medium: 'Medium risk',
  high: 'High risk',
}

function RiskBadge({ level }) {
  const label = RISK_LABELS[level] || level
  return <span className={`risk-badge risk-${level}`}>{label}</span>
}

function ResultSections({ result }) {
  return (
    <div className="result">
      <div className="result-header">
        <h2>Summary</h2>
        <RiskBadge level={result.risk_level} />
      </div>

      {(result.diff_truncated || result.files_truncated) && (
        <div className="notice">
          {result.truncation_note && <p>{result.truncation_note}</p>}
          {result.files_truncation_note && <p>{result.files_truncation_note}</p>}
        </div>
      )}

      <section className="result-section">
        <p>{result.summary}</p>
      </section>

      <section className="result-section">
        <h3>Changed files</h3>
        {result.changed_files.length > 0 ? (
          <ul>
            {result.changed_files.map((file, i) => (
              <li key={i}>{file}</li>
            ))}
          </ul>
        ) : (
          <p className="muted">No file details available.</p>
        )}
      </section>

      <section className="result-section">
        <h3>Potential issues</h3>
        {result.potential_issues.length > 0 ? (
          <ul>
            {result.potential_issues.map((issue, i) => (
              <li key={i}>{issue}</li>
            ))}
          </ul>
        ) : (
          <p className="muted">No potential issues flagged.</p>
        )}
      </section>
    </div>
  )
}

export default function App() {
  const [url, setUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    const trimmedUrl = url.trim()

    setError(null)
    setResult(null)

    if (!trimmedUrl) {
      setError('Please paste a GitHub pull request URL.')
      return
    }
    if (!PR_URL_PATTERN.test(trimmedUrl)) {
      setError(
        'That doesn\'t look like a GitHub PR URL. Expected format: https://github.com/{owner}/{repo}/pull/{number}'
      )
      return
    }

    setLoading(true)

    try {
      const data = await summarizePR(trimmedUrl)
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>PR Summary Bot</h1>
        <p className="subtitle">
          Paste a GitHub pull request URL to get an AI-generated summary, risk assessment, and
          potential issues.
        </p>
      </header>

      <form onSubmit={handleSubmit} className="pr-form">
        <textarea
          aria-label="GitHub pull request URL"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://github.com/owner/repo/pull/123"
          rows={3}
          disabled={loading}
        />
        <button type="submit" disabled={loading}>
          {loading ? 'Summarizing…' : 'Summarize PR'}
        </button>
      </form>

      {error && <div className="error">{error}</div>}

      {loading && (
        <div className="loading">
          <div className="spinner" />
          <span>Fetching PR details and generating summary…</span>
        </div>
      )}

      {result && !loading && <ResultSections result={result} />}
    </div>
  )
}
