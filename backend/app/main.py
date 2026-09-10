import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import ALLOWED_ORIGINS
from .errors import GitHubAPIError, InvalidPRUrlError, OpenAIAPIError
from .github_client import fetch_pr_context
from .models import SummarizeRequest, SummarizeResponse
from .openai_client import summarize_pr

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pr_summary_bot")

app = FastAPI(title="PR Summary Bot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/summarize", response_model=SummarizeResponse)
async def summarize(request: SummarizeRequest):
    try:
        ctx = await fetch_pr_context(request.url)
    except InvalidPRUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GitHubAPIError as exc:
        logger.warning("GitHub API error: %s", exc.message)
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    try:
        return await summarize_pr(ctx)
    except OpenAIAPIError as exc:
        logger.warning("OpenAI API error: %s", exc.message)
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
