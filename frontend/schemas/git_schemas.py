"""Request schemas for the Git blueprint (frontend/blueprints/git_views.py)."""

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class GitCommitRequest(BaseModel):
    """Body for POST /git/api/commit."""

    message: str = Field(
        default="Update from Ollash",
        min_length=1,
        max_length=512,
        description="Git commit message.",
    )
    files: List[str] = Field(
        default_factory=lambda: ["."],
        description="List of file paths to stage. Defaults to all ('.') .",
    )

    @field_validator("files", mode="before")
    @classmethod
    def files_must_not_be_empty(cls, v: List[str]) -> List[str]:
        if isinstance(v, list) and len(v) == 0:
            return ["."]
        return v


class GitDiffRequest(BaseModel):
    """Query parameters for GET /git/api/diff.

    Note: validated from request.args via model_validate().
    """

    file: str = Field(
        ...,
        min_length=1,
        description="Relative path to the file to diff.",
    )
