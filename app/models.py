from typing import Optional

from pydantic import BaseModel, Field, model_validator, field_validator

class PagePayload(BaseModel):
    path: str = Field(..., description="Wiki.js path like 'AI/Tools/Ollama'")
    title: str
    content: str | None = Field(
        default=None,
        description="Primary page text content (can be markdown, plain text, or mixed text).",
    )
    content_md: str | None = Field(
        default=None,
        description="Legacy markdown field kept for backward compatibility.",
    )
    description: str | None = None
    is_private: bool = False
    tags: list[str] = Field(default_factory=list)

    @field_validator("content", "content_md", mode="before")
    @classmethod
    def _coerce_content_fields(cls, value):
        if value is None:
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, (bytes, bytearray)):
            return value.decode("utf-8", errors="replace")
        return str(value)

    @model_validator(mode="after")
    def _validate_and_normalize_content(self):
        if self.content is None and self.content_md is None:
            raise ValueError("One of 'content' or 'content_md' is required.")
        # Keep one canonical value for downstream code paths.
        if self.content is None:
            self.content = self.content_md
        if self.content_md is None:
            self.content_md = self.content
        return self

class UpsertResult(BaseModel):
    id: int
    path: str
    idempotency_key: str

class DeleteReq(BaseModel):
    path: Optional[str] = None
    id: Optional[int] = None
    soft: bool = True  # if true, replace with moved stub instead of deleting
