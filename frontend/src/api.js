const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

export async function summarizePR(url) {
  let response

  try {
    response = await fetch(`${API_BASE_URL}/api/summarize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    })
  } catch {
    throw new Error(
      `Could not reach the backend at ${API_BASE_URL}. Make sure the server is running.`
    )
  }

  let data = null
  try {
    data = await response.json()
  } catch {
    // response had no/invalid JSON body; fall through to status-based error below
  }

  if (!response.ok) {
    const detail = data && typeof data.detail === 'string' ? data.detail : null
    throw new Error(detail || `Request failed with status ${response.status}.`)
  }

  if (!data) {
    throw new Error('Server returned an empty response.')
  }

  return data
}
