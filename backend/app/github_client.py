import re

import httpx

from .config import GITHUB_TOKEN
from .errors import GitHubAPIError, InvalidPRUrlError
from .models import ChangedFile, PullRequestContext

PR_URL_RE = re.compile(
    r"^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/pull/(?P<number>\d+)/?"
)

GITHUB_API_BASE = "https://api.github.com"
REQUEST_TIMEOUT = 15.0
MAX_FILES = 300


def parse_pr_url(url: str) -> tuple[str, str, int]:
    url = url.strip()
    match = PR_URL_RE.match(url)
    if not match:
        raise InvalidPRUrlError(
            "Invalid GitHub PR URL. Expected format: "
            "https://github.com/{owner}/{repo}/pull/{number}"
        )
    return match.group("owner"), match.group("repo"), int(match.group("number"))


def _headers(accept: str) -> dict:
    headers = {"Accept": accept, "X-GitHub-Api-Version": "2022-11-28"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers


async def fetch_pr_context(url: str) -> PullRequestContext:
    owner, repo, number = parse_pr_url(url)
    base_path = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{number}"

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        pr_data = await _get_json(client, base_path, _headers("application/vnd.github+json"))
        files_data = await _get_files(client, base_path, owner, repo, number)
        diff_text = await _get_diff(client, base_path)

    changed_files = [
        ChangedFile(
            filename=f["filename"],
            status=f["status"],
            additions=f["additions"],
            deletions=f["deletions"],
            changes=f["changes"],
        )
        for f in files_data
    ]

    # pr_data["changed_files"] is GitHub's authoritative total file count for the PR,
    # independent of how many we actually fetched/kept below the MAX_FILES cap.
    total_changed_files = pr_data.get("changed_files", len(changed_files))
    files_truncated = total_changed_files > len(changed_files)

    return PullRequestContext(
        owner=owner,
        repo=repo,
        number=number,
        title=pr_data.get("title") or "",
        description=pr_data.get("body") or "",
        author=(pr_data.get("user") or {}).get("login") or "unknown",
        changed_files=changed_files,
        total_changed_files=total_changed_files,
        files_truncated=files_truncated,
        diff=diff_text,
        diff_truncated=False,
    )


async def _get_json(client: httpx.AsyncClient, url: str, headers: dict, params: dict | None = None):
    try:
        response = await client.get(url, headers=headers, params=params)
    except httpx.TimeoutException as exc:
        raise GitHubAPIError("Timed out while contacting the GitHub API.", 504) from exc
    except httpx.RequestError as exc:
        raise GitHubAPIError(f"Could not reach the GitHub API: {exc}", 502) from exc

    if response.status_code == 404:
        raise GitHubAPIError(
            "Pull request not found. Check that the URL is correct and the repo is public "
            "(or that GITHUB_TOKEN has access to it).",
            404,
        )
    if response.status_code in (401, 403):
        raise GitHubAPIError(
            "GitHub API authentication/rate-limit error. Check GITHUB_TOKEN and rate limits.",
            response.status_code,
        )
    if response.status_code >= 400:
        raise GitHubAPIError(
            f"GitHub API error ({response.status_code}): {response.text[:300]}",
            response.status_code,
        )

    try:
        return response.json()
    except ValueError as exc:
        raise GitHubAPIError("GitHub API returned an unparsable response.", 502) from exc


async def _get_files(client: httpx.AsyncClient, base_path: str, owner: str, repo: str, number: int) -> list[dict]:
    files: list[dict] = []
    page = 1
    headers = _headers("application/vnd.github+json")
    while len(files) < MAX_FILES:
        data = await _get_json(
            client, f"{base_path}/files", headers, params={"per_page": 100, "page": page}
        )
        if not data:
            break
        files.extend(data)
        if len(data) < 100:
            break
        page += 1
    return files[:MAX_FILES]


async def _get_diff(client: httpx.AsyncClient, base_path: str) -> str:
    headers = _headers("application/vnd.github.v3.diff")
    try:
        response = await client.get(base_path, headers=headers)
    except httpx.TimeoutException as exc:
        raise GitHubAPIError("Timed out while fetching the PR diff.", 504) from exc
    except httpx.RequestError as exc:
        raise GitHubAPIError(f"Could not reach the GitHub API: {exc}", 502) from exc

    if response.status_code >= 400:
        raise GitHubAPIError(
            f"GitHub API error while fetching diff ({response.status_code}): {response.text[:300]}",
            response.status_code,
        )
    return response.text
