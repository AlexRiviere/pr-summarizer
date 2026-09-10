# Manual testing guide

## 1. Set up environment

```bash
cp backend/.env.example backend/.env
# edit backend/.env and fill in GITHUB_TOKEN and OPENAI_API_KEY
```

`GITHUB_TOKEN` is optional for public repos but strongly recommended (60 req/hr
unauthenticated vs. 5000 req/hr authenticated). `OPENAI_API_KEY` is required.

## 2. Run the server

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

Visit http://127.0.0.1:8000/docs for interactive Swagger UI, or http://127.0.0.1:8000/health
to confirm the server is up.

## 3. Try it

```bash
curl -X POST http://127.0.0.1:8000/api/summarize \
  -H "Content-Type: application/json" \
  -d '{"url": "https://github.com/fastapi/fastapi/pull/12000"}'
```

Pick any real, public PR URL you like.

## Edge cases worth trying

- **Malformed URL** (not a PR URL, e.g. a repo URL or issue URL) -> expect 400.
- **Non-existent PR** (valid repo, huge PR number) -> expect 404.
- **Private repo without access** -> expect 404 (GitHub returns 404, not 403, for
  private repos you can't see).
- **No GITHUB_TOKEN set** -> should still work for public repos, just lower rate limit.
- **Very large PR** (hundreds of changed files / huge diff) -> diff should be
  truncated to 15,000 chars and `diff_truncated: true` in the response.
- **PR with empty description** -> should still summarize fine.
- **Missing OPENAI_API_KEY** -> expect 500 with a clear message, not a crash.
- **Bad OPENAI_API_KEY** -> expect a 4xx/5xx surfaced from the OpenAI error handling,
  not a raw traceback.
- **Rate limited GitHub token** -> expect 403 with a clear message.
