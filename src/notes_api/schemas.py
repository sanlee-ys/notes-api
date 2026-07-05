"""Pydantic request/response schemas for the notes API.

Input validation (length caps, tag limits) lives here so bad input is
rejected at the edge with a 422 before any service or database code runs.
``NoteResponse`` reads straight off the ORM model via ``from_attributes``.
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class NoteRequest(BaseModel):
    """Payload for creating or fully updating a note."""

    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1, max_length=10000)
    tags: list[str] = Field(default_factory=list)
    published_at: datetime | None = Field(
        default=None,
        description="The article's publication date (ISO 8601). Omit for notes "
        "with no inherent date.",
    )

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        """Reject more than 20 tags or any tag longer than 50 characters."""
        if len(v) > 20:
            raise ValueError("cannot have more than 20 tags")
        for tag in v:
            if len(tag) > 50:
                raise ValueError(f"tag '{tag}' exceeds 50 characters")
        return v


class TagsRequest(BaseModel):
    """Payload for replacing a note's tags."""

    tags: list[str] = Field(default_factory=list)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        """Reject more than 20 tags or any tag longer than 50 characters."""
        if len(v) > 20:
            raise ValueError("cannot have more than 20 tags")
        for tag in v:
            if len(tag) > 50:
                raise ValueError(f"tag '{tag}' exceeds 50 characters")
        return v


class NoteResponse(BaseModel):
    """A note as returned by the API, built directly from the ORM model."""

    id: int
    title: str
    content: str
    tags: list[str]
    enrichment_status: str
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
