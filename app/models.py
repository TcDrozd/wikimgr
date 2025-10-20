from pydantic import BaseModel, Field
from typing import Optional

class PagePayload(BaseModel):
    path: str = Field(..., description="Wiki.js path like 'AI/Tools/Ollama'")
    title: str
    content_md: str = Field(..., description="Markdown content")
    description: str | None = None
    is_private: bool = False

class UpsertResult(BaseModel):
    id: int
    path: str
    idempotency_key: str

class DeleteReq(BaseModel):
    path: Optional[str] = None
    id: Optional[int] = None
    soft: bool = True  # if true, replace with moved stub instead of deleting