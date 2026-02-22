"""Request schemas for the Operations blueprint."""

from pydantic import BaseModel, Field


class JobCreateRequest(BaseModel):
    """Body for POST /operations/api/jobs."""

    name: str = Field(
        default="Untitled Task",
        min_length=1,
        max_length=255,
        description="Human-readable name for the scheduled job.",
    )
    cron: str = Field(
        default="* * * * *",
        description="Cron expression (5 or 6 fields).",
    )


class DagPreviewRequest(BaseModel):
    """Body for POST /operations/api/dag/preview."""

    task: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Free-text task description to generate a DAG preview for.",
    )
