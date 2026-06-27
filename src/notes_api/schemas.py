from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class NoteRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1, max_length=10000)
    tags: list[str] = Field(default_factory=list)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        if len(v) > 20:
            raise ValueError("cannot have more than 20 tags")
        for tag in v:
            if len(tag) > 50:
                raise ValueError(f"tag '{tag}' exceeds 50 characters")
        return v


class TagsRequest(BaseModel):
    tags: list[str] = Field(default_factory=list)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        if len(v) > 20:
            raise ValueError("cannot have more than 20 tags")
        for tag in v:
            if len(tag) > 50:
                raise ValueError(f"tag '{tag}' exceeds 50 characters")
        return v


class NoteResponse(BaseModel):
    id: int
    title: str
    content: str
    tags: list[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
