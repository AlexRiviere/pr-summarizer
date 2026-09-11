# PR Summary Bot

Paste a GitHub pull request URL and get back an AI-generated summary: what changed, which
files were touched, an overall risk level, and any potential bugs or improvements the model
noticed in the diff.

- **Backend**: FastAPI, fetches PR metadata/files/diff from the GitHub API and asks OpenAI
  (`gpt-4o-mini`) for a structured summary. No database — everything is in-memory, per request.
- **Frontend**: React (Vite), a single form + result view.

## Project structure

```
backend/
  app/
    main.py           FastAPI app, POST /api/summarize, GET /health
    github_client.py  PR URL parsing + fetching (title, description, files, diff) from GitHub
    openai_client.py  Prompt building, character-budget truncation, OpenAI call
    models.py         Pydantic request/response schemas
    errors.py         Typed error classes for GitHub/OpenAI failures
    config.py         Env vars and tunable limits
  requirements.txt
  .env.example
  tests/manual_test.md  Manual test checklist / edge cases

frontend/
  src/
    App.jsx    Form + result rendering, client-side URL validation
    api.js     fetch wrapper for the backend
    App.css / index.css
  .env.example
```

## Prerequisites

- Python 3.11+ and `pip`
- Node.js 18+ and `npm`
- A [GitHub personal access token](https://github.com/settings/tokens) (optional but
  recommended — raises the GitHub API rate limit from 60/hr to 5,000/hr)
- An [OpenAI API key](https://platform.openai.com/api-keys) (required)

## Setup

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# edit .env and fill in GITHUB_TOKEN and OPENAI_API_KEY
uvicorn app.main:app --reload --port 8000
```

Check it's alive: `curl http://127.0.0.1:8000/health` → `{"status":"ok"}`.
Interactive API docs: http://127.0.0.1:8000/docs

### Frontend

In a separate terminal:

```bash
cd frontend
npm install
cp .env.example .env   # defaults to http://127.0.0.1:8000, only change if your backend runs elsewhere
npm run dev
```

Open http://localhost:5173/.

## Configuration

### `backend/.env`

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | Yes | Used to call the OpenAI API. Without it, `/api/summarize` returns `500`. |
| `GITHUB_TOKEN` | No | Used as a Bearer token for GitHub API requests. Without it, public repos still work but at the unauthenticated rate limit. |
| `ALLOWED_ORIGINS` | No | Comma-separated list of frontend origins allowed to call the API (CORS). Defaults to `http://localhost:5173,http://127.0.0.1:5173` (the Vite dev server). |

### `frontend/.env`

| Variable | Required | Description |
|---|---|---|
| `VITE_API_BASE_URL` | No | Backend base URL. Defaults to `http://127.0.0.1:8000`. |

### Tunables (`backend/app/config.py`)

These bound the size of what gets sent to OpenAI, to control cost/latency and stay within
context limits on unusually large PRs:

- `MAX_DIFF_CHARS` (15,000) — hard ceiling on diff size in the prompt.
- `MAX_DESCRIPTION_CHARS` / `MAX_FILES_SUMMARY_CHARS` (4,000 each) — caps on the PR
  description and the file-stats summary.
- `MAX_PROMPT_CHARS` (20,000) — total budget across description + files summary + diff;
  description and files summary are reserved first, and whatever's left (up to
  `MAX_DIFF_CHARS`) goes to the diff.
- `MAX_FILES` (`github_client.py`, 300) — cap on how many changed files are fetched from
  GitHub per PR.

When any of these caps are hit, the API response includes `diff_truncated`/`truncation_note`
and/or `files_truncated`/`files_truncation_note` so the frontend can warn that the summary may
not reflect the full change.

## API

### `POST /api/summarize`

Request:
```json
{ "url": "https://github.com/{owner}/{repo}/pull/{number}" }
```

Response:
```json
{
  "summary": "...",
  "changed_files": ["src/foo.py (modified, ...)", "..."],
  "risk_level": "low | medium | high",
  "potential_issues": ["...", "..."],
  "diff_truncated": false,
  "truncation_note": null,
  "files_truncated": false,
  "files_truncation_note": null
}
```

Errors return `{"detail": "..."}` with an appropriate status code: `400` (malformed URL),
`404` (PR not found / inaccessible), `401`/`403` (GitHub auth/rate limit), `500`/`502`/`504`
(server misconfiguration or upstream GitHub/OpenAI failures).

### `GET /health`

Returns `{"status": "ok"}`.

## Testing it yourself

See `backend/tests/manual_test.md` for a full checklist (malformed URLs, non-existent PRs,
private repos, huge diffs, missing/bad API keys, etc).

A few real PR URLs that exercise different states:

| State | URL |
|---|---|
| Normal PR, low risk | `https://github.com/pallets/flask/pull/5555` |
| Large diff (triggers `diff_truncated`) | `https://github.com/nodejs/node/pull/65656` |
| Non-existent PR (404) | `https://github.com/pallets/flask/pull/999999999` |
| Malformed URL (client-side validation, no network call) | `not-a-github-url` |

`files_truncated` (a PR with more than `MAX_FILES` changed files) is rare in the wild — to see
it locally, temporarily lower `MAX_FILES` in `backend/app/github_client.py`, restart the
backend, and use a PR with more files than that. Remember to set it back to `300` afterward.
