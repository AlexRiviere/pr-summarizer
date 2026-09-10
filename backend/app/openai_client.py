import json

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI

from .config import (
    MAX_DESCRIPTION_CHARS,
    MAX_DIFF_CHARS,
    MAX_FILES_SUMMARY_CHARS,
    MAX_PROMPT_CHARS,
    OPENAI_API_KEY,
    OPENAI_MODEL,
)
from .errors import OpenAIAPIError
from .models import PullRequestContext, SummarizeResponse

RESPONSE_SCHEMA = {
    "name": "pr_summary",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "A clear, well-formatted summary of what changed in this PR.",
            },
            "changed_files": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of file paths changed, optionally with a brief note per file.",
            },
            "risk_level": {
                "type": "string",
                "enum": ["low", "medium", "high"],
                "description": "Overall risk level of merging this PR.",
            },
            "potential_issues": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Potential bugs, regressions, or improvement suggestions found in the diff.",
            },
        },
        "required": ["summary", "changed_files", "risk_level", "potential_issues"],
        "additionalProperties": False,
    },
}

SYSTEM_PROMPT = (
    "You are an expert code reviewer. You will be given metadata and the unified diff for a "
    "GitHub pull request. Produce a structured summary of the change, list the files touched, "
    "assess an overall risk level, and call out concrete potential bugs, regressions, or "
    "improvements a reviewer should check. Base every claim strictly on the diff and metadata "
    "provided - do not invent details. If the diff was truncated, note that your review may not "
    "cover the full change."
)


def _truncate(text: str, limit: int) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return text[:limit], True


def _build_user_prompt(ctx: PullRequestContext) -> tuple[str, bool, int, int]:
    """Build the prompt within a single total character budget (MAX_PROMPT_CHARS).

    Description and the files summary are truncated to their own fixed caps first;
    whatever budget remains (capped at MAX_DIFF_CHARS) is given to the diff, so a
    very long description/file list can't silently blow out the prompt size.
    Returns (prompt, diff_truncated, original_diff_chars, diff_chars_used).
    """
    description, _ = _truncate(ctx.description or "(no description provided)", MAX_DESCRIPTION_CHARS)

    files_summary = "\n".join(
        f"- {f.filename} ({f.status}, +{f.additions}/-{f.deletions})" for f in ctx.changed_files
    ) or "(no file stats available)"
    files_summary, _ = _truncate(files_summary, MAX_FILES_SUMMARY_CHARS)

    reserved_chars = len(description) + len(files_summary)
    diff_budget = max(0, min(MAX_DIFF_CHARS, MAX_PROMPT_CHARS - reserved_chars))
    original_diff_chars = len(ctx.diff)
    diff, diff_truncated = _truncate(ctx.diff, diff_budget)

    parts = [
        f"Repository: {ctx.owner}/{ctx.repo}",
        f"PR #{ctx.number}: {ctx.title}",
        f"Author: {ctx.author}",
        "Description:",
        description,
        "",
        "Changed files:",
        files_summary,
        "",
        "Unified diff:",
        diff,
    ]
    if diff_truncated:
        parts.append(
            "\n[NOTE: The diff above was truncated to the first "
            f"{len(diff)} characters because it exceeded the prompt size budget.]"
        )
    if ctx.files_truncated:
        parts.append(
            f"\n[NOTE: This PR changed {ctx.total_changed_files} files, but only the first "
            f"{len(ctx.changed_files)} are listed above and reflected in the diff.]"
        )
    return "\n".join(parts), diff_truncated, original_diff_chars, len(diff)


async def summarize_pr(ctx: PullRequestContext) -> SummarizeResponse:
    if not OPENAI_API_KEY:
        raise OpenAIAPIError(
            "OPENAI_API_KEY is not configured on the server.", 500
        )

    user_prompt, truncated, original_diff_chars, diff_chars_used = _build_user_prompt(ctx)

    try:
        async with AsyncOpenAI(api_key=OPENAI_API_KEY) as client:
            response = await client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_schema", "json_schema": RESPONSE_SCHEMA},
                temperature=0.2,
            )
    except APITimeoutError as exc:
        raise OpenAIAPIError("Timed out while contacting the OpenAI API.", 504) from exc
    except APIConnectionError as exc:
        raise OpenAIAPIError(f"Could not reach the OpenAI API: {exc}", 502) from exc
    except APIStatusError as exc:
        raise OpenAIAPIError(
            f"OpenAI API error ({exc.status_code}): {exc.message}", exc.status_code
        ) from exc

    choice = response.choices[0] if response.choices else None
    content = choice.message.content if choice and choice.message else None
    if not content:
        raise OpenAIAPIError("OpenAI API returned an empty response.", 502)

    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise OpenAIAPIError("OpenAI API returned malformed JSON.", 502) from exc

    try:
        result = SummarizeResponse(**payload)
    except Exception as exc:
        raise OpenAIAPIError(f"OpenAI API response did not match expected schema: {exc}", 502) from exc

    result.diff_truncated = truncated
    if truncated:
        result.truncation_note = (
            f"The diff was too large to fully analyze ({original_diff_chars:,} characters) "
            f"and was truncated to {diff_chars_used:,} characters before being sent "
            "to the model. This summary may not reflect changes past that point."
        )

    result.files_truncated = ctx.files_truncated
    if ctx.files_truncated:
        result.files_truncation_note = (
            f"This PR changed {ctx.total_changed_files:,} files, but only the first "
            f"{len(ctx.changed_files):,} were fetched and analyzed. The changed_files list "
            "and diff above do not cover the full change."
        )
    return result
