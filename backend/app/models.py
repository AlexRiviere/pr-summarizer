from typing import Literal

from pydantic import BaseModel, Field


class SummarizeRequest(BaseModel):
    url: str = Field(..., description="Full GitHub pull request URL")


class ChangedFile(BaseModel):
    filename: str
    status: str
    additions: int
    deletions: int
    changes: int


class PullRequestContext(BaseModel):
    owner: str
    repo: str
    number: int
    title: str
    description: str
    author: str
    changed_files: list[ChangedFile]
    diff: str
    diff_truncated: bool


class SummarizeResponse(BaseModel):
    summary: str
    changed_files: list[str]
    risk_level: Literal["low", "medium", "high"]
    potential_issues: list[str]
    diff_truncated: bool = False
    truncation_note: str | None = None
