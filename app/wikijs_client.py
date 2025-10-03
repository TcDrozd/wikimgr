import asyncio
import hashlib
import os
from dataclasses import dataclass
import httpx
from .models import PagePayload

# --- Path policy helpers ------------------------------------------------------
MIN_SEG_LEN = 3
# Common expansions for short segments (customize to taste)
SEG_EXPANSIONS = {
    "ai": "artificial-intelligence",
    "db": "database",
    "qa": "quality-assurance",
    "ci": "continuous-integration",
    "cd": "continuous-delivery",
    "ml": "machine-learning",
}

def normalize_path(raw: str) -> str:
    """Lowercase, strip, collapse slashes, replace spaces with hyphens."""
    parts = [p.strip().replace(" ", "-").lower() for p in raw.split("/") if p.strip()]
    return "/".join(parts)

def enforce_path_policy(path: str) -> str:
    """Ensure each segment is at least MIN_SEG_LEN; expand common short ones.
    Returns a possibly adjusted path. Raises WikiError(400, ...) if still invalid.
    """
    parts = [p for p in path.split("/") if p]
    fixed = []
    for seg in parts:
        s = seg
        if len(s) < MIN_SEG_LEN:
            s = SEG_EXPANSIONS.get(s.lower(), s)
        if len(s) < MIN_SEG_LEN:
            # give a clear message about which segment violates policy
            raise WikiError(400, f"Path segment '{seg}' must be at least {MIN_SEG_LEN} characters. Consider renaming (e.g., 'AI' -> 'artificial-intelligence').")
        fixed.append(s)
    return "/".join(fixed)

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

    @property
    def graphql_url(self) -> str:
        return f"{self.base_url}/graphql"

    async def _gql(self, query: str, variables: dict | None = None) -> dict:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        # retry simple network/5xx with backoff
        for attempt in range(4):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                    resp = await client.post(self.graphql_url, json=payload, headers=headers)
                # GraphQL always returns 200 for app-level errors; inspect body
                data = resp.json()
                if "errors" in data and data["errors"]:
                    # bubble up the first error message
                    msg = data["errors"][0].get("message", "GraphQL error")
                    # treat as 502 (upstream) to keep behavior
                    raise WikiError(502, f"Wiki.js GraphQL error: {msg}")
                return data["data"]
            except httpx.RequestError as e:
                if attempt == 3:
                    raise WikiError(504, f"Network error talking to Wiki.js: {e}") from e
                await asyncio.sleep(0.5 * (2 ** attempt))
        raise WikiError(502, "Wiki.js upstream unavailable after retries")

    async def get_page_by_path(self, path: str, locale: str | None = None) -> dict | None:
        path = enforce_path_policy(normalize_path(path))
        loc = locale or os.getenv("WIKIJS_LOCALE", "en")
        q = """
        query ($path: String!, $locale: String!) {
          pages {
            singleByPath(path: $path, locale: $locale) {
              id
              path
              title
            }
          }
        }
        """
        try:
            data = await self._gql(q, {"path": path, "locale": loc})
            return (data.get("pages") or {}).get("singleByPath")
        except WikiError as e:
            msg = (e.message or "").lower()
            if "does not exist" in msg or "pagenotfound" in msg or "6003" in msg:
                return None
            raise

    async def create_page(self, p: PagePayload) -> dict:
        # normalize/enforce path to avoid server-side errors
        p.path = enforce_path_policy(normalize_path(p.path))
        m = """
        mutation ($path: String!, $title: String!, $content: String!, $desc: String!, $isPrivate: Boolean!, $locale: String!, $tags: [String]!) {
          pages {
            create(
              path: $path,
              title: $title,
              content: $content,
              description: $desc,
              editor: "markdown",
              isPrivate: $isPrivate,
              isPublished: true,
              locale: $locale,
              tags: $tags
            ) {
              responseResult { succeeded message errorCode }
              page { id path title }
            }
          }
        }
        """
        desc = p.description if p.description is not None else ""
        tags = p.tags if getattr(p, "tags", None) else []
        vars = {
            "path": p.path,
            "title": p.title,
            "content": p.content_md,
            "desc": desc,
            "isPrivate": p.is_private,
            "locale": os.getenv("WIKIJS_LOCALE", "en"),
            "tags": tags,
        }
        data = await self._gql(m, vars)
        rr = data["pages"]["create"]["responseResult"]
        if not rr["succeeded"]:
            raise WikiError(502, f"Create failed: {rr['message'] or rr['errorCode']}")
        return data["pages"]["create"]["page"]

    async def update_page(self, page_id: int, p: PagePayload) -> dict:
        m = """
        mutation ($id: Int!, $title: String!, $content: String!, $desc: String!, $isPrivate: Boolean!, $tags: [String]!) {
          pages {
            update(
              id: $id,
              title: $title,
              content: $content,
              description: $desc,
              editor: "markdown",
              isPrivate: $isPrivate,
              isPublished: true,
              tags: $tags
            ) {
              responseResult { succeeded message errorCode }
              page { id path title }
            }
          }
        }
        """
        tags = p.tags if getattr(p, "tags", None) else []
        vars = {
            "id": page_id,
            "title": p.title,
            "content": p.content_md,
            "desc": p.description if p.description is not None else "",
            "isPrivate": p.is_private,
            "tags": tags,
        }
        data = await self._gql(m, vars)
        rr = data["pages"]["update"]["responseResult"]
        if not rr["succeeded"]:
            raise WikiError(502, f"Update failed: {rr['message'] or rr['errorCode']}")
        return data["pages"]["update"]["page"]

    async def upsert_page(self, payload: PagePayload, idem_key: str) -> dict:
        # normalize + enforce path rules
        clean_path = enforce_path_policy(normalize_path(payload.path))
        # update payload path for downstream calls
        payload.path = clean_path
        # idem_key currently unused by Wiki.js; we still compute/accept it for logging/echo.
        existing = await self.get_page_by_path(payload.path, os.getenv("WIKIJS_LOCALE", "en"))
        if existing:
            return await self.update_page(existing["id"], payload)
        return await self.create_page(payload)

def derive_idempotency_key(payload: PagePayload) -> str:
    h = hashlib.sha256()
    h.update(payload.path.encode())
    h.update(b"\x00")
    h.update(payload.title.encode())
    h.update(b"\x00")
    h.update(payload.content_md.encode())
    return h.hexdigest()