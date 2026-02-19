from typing import Any, Literal, Optional

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


class UploadPageResult(BaseModel):
    ok: bool = True
    idempotency_key: str
    page: UpsertResult


class BulkUploadSuccess(BaseModel):
    filename: str
    idempotency_key: str
    page: UpsertResult


class BulkUploadFailure(BaseModel):
    filename: str
    reason: str


class BulkUploadResult(BaseModel):
    ok: bool
    base_path: str
    successes: list[BulkUploadSuccess] = Field(default_factory=list)
    failures: list[BulkUploadFailure] = Field(default_factory=list)


class DeleteReq(BaseModel):
    path: Optional[str] = None
    id: Optional[int] = None
    soft: bool = True  # if true, replace with moved stub instead of deleting


class PreflightReq(BaseModel):
    path: str = Field(..., description="Raw wiki path to validate and normalize.")


class PreflightResult(BaseModel):
    input: str
    normalized: str
    is_valid_root: bool
    root: str | None = None
    allowed_roots: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ContentTreeStats(BaseModel):
    page_count: int
    root_counts: dict[str, int] = Field(default_factory=dict)


class ContentTreeResult(BaseModel):
    roots: dict[str, dict] = Field(default_factory=dict)
    tree_text: str
    stats: ContentTreeStats


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    ok: bool = True


class ReadyResponse(BaseModel):
    ready: bool
    reason: str | None = None


class UpsertPageRequest(BaseModel):
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
        if self.content is None:
            self.content = self.content_md
        if self.content_md is None:
            self.content_md = self.content
        return self


class UpsertPageResponse(BaseModel):
    id: int
    path: str
    idempotency_key: str


class GetPageResponse(BaseModel):
    id: int
    path: str
    title: str
    description: str = ""
    isPrivate: bool | None = None
    createdAt: str = ""
    updatedAt: str = ""
    content: str = ""


class DeletePageRequest(BaseModel):
    path: str | None = None
    id: int | None = None
    soft: bool = True


class DeletePageResponse(BaseModel):
    ok: bool
    hard_deleted: bool
    id: int


class BulkMoveItem(BaseModel):
    from_path: str
    to_path: str
    merge: bool = False


class BulkMoveRequest(BaseModel):
    moves: list[BulkMoveItem]
    dry_run: bool = False


class BulkMoveAppliedItem(BaseModel):
    from_: str = Field(..., alias="from")
    to: str
    dry: bool | None = None

    model_config = {"populate_by_name": True}


class BulkMoveSkippedItem(BaseModel):
    move: BulkMoveItem
    reason: str


class BulkMoveErrorItem(BaseModel):
    move: BulkMoveItem
    error: str


class BulkMoveResponse(BaseModel):
    dry_run: bool
    applied: list[BulkMoveAppliedItem] = Field(default_factory=list)
    skipped: list[BulkMoveSkippedItem] = Field(default_factory=list)
    errors: list[BulkMoveErrorItem] = Field(default_factory=list)


class BulkRedirectItem(BaseModel):
    from_path: str
    to_path: str


class BulkRedirectRequest(BaseModel):
    redirects: list[BulkRedirectItem]


class BulkRedirectAppliedItem(BaseModel):
    from_: str = Field(..., alias="from")
    to: str

    model_config = {"populate_by_name": True}


class BulkRedirectErrorItem(BaseModel):
    redirect: BulkRedirectItem
    error: str


class BulkRedirectResponse(BaseModel):
    applied: list[BulkRedirectAppliedItem] = Field(default_factory=list)
    errors: list[BulkRedirectErrorItem] = Field(default_factory=list)


class BulkRelinkRequest(BaseModel):
    mapping: dict[str, str] = Field(default_factory=dict)
    scope: Literal["all", "touched"] | list[str] = "all"


class BulkRelinkErrorItem(BaseModel):
    path: str
    error: str


class BulkRelinkResponse(BaseModel):
    updated: list[str] = Field(default_factory=list)
    errors: list[BulkRelinkErrorItem] = Field(default_factory=list)


class InventoryPage(BaseModel):
    id: int
    path: str
    title: str
    description: str = ""
    isPrivate: bool | None = None
    createdAt: str = ""
    updatedAt: str = ""
    content: str | None = None
    error: str | None = None


class InventoryResponse(BaseModel):
    count: int
    pages: list[InventoryPage] = Field(default_factory=list)
