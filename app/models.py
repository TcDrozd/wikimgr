from pydantic import BaseModel, Field

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