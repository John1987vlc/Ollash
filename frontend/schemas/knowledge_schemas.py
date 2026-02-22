"""Request schemas for the Knowledge blueprint.

Note: The upload endpoint uses multipart/form-data, so Pydantic validation is
applied to the form fields rather than a JSON body.
"""

from pydantic import BaseModel, Field


class DocumentQueryParams(BaseModel):
    """Optional query parameters for GET /api/knowledge/documents."""

    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
