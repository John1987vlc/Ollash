"""Pydantic models for BlueprintPhase JSON validation.

Kept in a separate module so that importing phase_context.py does NOT pull
in the heavy Pydantic machinery at startup. BlueprintPhase imports these
lazily inside its run() method.
"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class FilePlanModel(BaseModel):
    """Pydantic-validated FilePlan for JSON parsing from LLM output."""

    path: str = Field(..., description="Relative path from project root, e.g. 'src/models/user.py'")
    purpose: str = Field(..., description="One sentence: what this file does")
    exports: List[str] = Field(default_factory=list, description="Public symbols this file exposes")
    imports: List[str] = Field(default_factory=list, description="Other project files this depends on")
    key_logic: str = Field(default="", description="Key algorithms, patterns, or data structures")
    priority: int = Field(default=10, ge=1, le=20, description="Generation order: 1=first, 20=last")


class BlueprintOutput(BaseModel):
    """Complete BlueprintPhase LLM response schema."""

    project_type: str = Field(..., description="One of: web_app, api, cli, library, game, data, unknown")
    tech_stack: List[str] = Field(..., description="Primary technologies, e.g. ['python', 'fastapi']")
    files: List[FilePlanModel] = Field(
        ...,
        max_length=20,
        description="Max 20 files. Order by dependency (depended-on files first).",
    )
