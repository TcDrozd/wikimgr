import asyncio
import hashlib
import os
from dataclasses import dataclass
import httpx
from .models import PagePayload

class WikiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message

@dataclass
class WikiJSClient:
    base_url: str
    token: str
    timeout_s: int = 10

    @classmethod
    def from_env(cls):
        base = os.getenv("WIKIJS_BASE_URL", "").rstrip("/")
        tok = os.getenv("WIKIJS_API_TOKEN", "")
        if not base or not tok:
            raise WikiError(503, "Wiki.js env not configured")
        return cls(base, tok)

    async def upsert_page(self, payload: PagePayload, idem_key: str) -> dict:
        # Example: pretend there is an upsert endpoint
        url = f"{self.base_url}/api/pages/upsert"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "X-Idempotency-Key": idem_key,
        }
        data = {
            "path": payload.path,
            "title": payload.title,
            "content": payload.content_md,
            "description": payload.description,
            "isPrivate": payload.is_private,
        }
        # Retry w/ exponential backoff
        for attempt in range(4):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                    resp = await client.post(url, json=data, headers=headers)
                if resp.status_code in (200, 201):
                    return resp.json()
                if 400 <= resp.status_code < 500:
                    raise WikiError(resp.status_code, f"Wiki.js client error: {resp.text}")
                # else 5xx — retry
                await asyncio.sleep(0.5 * (2 ** attempt))
            except httpx.RequestError as e:
                if attempt == 3:
                    raise WikiError(504, f"Network error talking to Wiki.js: {e}") from e
                await asyncio.sleep(0.5 * (2 ** attempt))
        raise WikiError(502, "Wiki.js upstream unavailable after retries")

def derive_idempotency_key(payload: PagePayload) -> str:
    h = hashlib.sha256()
    h.update(payload.path.encode())
    h.update(b"\x00")
    h.update(payload.title.encode())
    h.update(b"\x00")
    h.update(payload.content_md.encode())
    return h.hexdigest()