# wikijs_api.py
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

import httpx

WIKIJS_BASE_URL = os.getenv("WIKIJS_BASE_URL", "http://192.168.50.208:3000")
GRAPHQL_URL = f"{WIKIJS_BASE_URL.rstrip('/')}/graphql"
WIKIJS_API_TOKEN = os.getenv("WIKIJS_API_TOKEN", "")

HEADERS = {
    "Authorization": f"Bearer {WIKIJS_API_TOKEN}" if WIKIJS_API_TOKEN else "",
    "Content-Type": "application/json",
    "Accept": "application/json",
}
if not HEADERS["Authorization"]:
    HEADERS.pop("Authorization", None)

# Queries
QUERY_LIST = """{ pages { list(orderBy: TITLE) { id path title } } }"""

QUERY_SINGLE_FULL = """
query One($id:Int!) {
  pages {
    single(id:$id) {
      id path title description isPrivate createdAt updatedAt
      content
    }
  }
}
"""

# Some Wiki.js versions expose contentRaw instead of content; fallback query:
QUERY_SINGLE_RAW = """
query One($id:Int!) {
  pages {
    single(id:$id) {
      id path title description isPrivate createdAt updatedAt
      contentRaw
    }
  }
}
"""

QUERY_SEARCH = """
query Find($q:String!) {
  pages { search(query:$q) { id path title } }
}
"""

# Mutations (delete varies by version; try and fall back)
MUTATION_DELETE = """
mutation Del($id:Int!) {
  pages { delete(id:$id) { operation { succeeded } } }
}
"""


def _post(query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    with httpx.Client(timeout=60) as c:
        r = c.post(
            GRAPHQL_URL,
            headers=HEADERS,
            json={"query": query, "variables": variables or {}},
        )
    r.raise_for_status()
    data = r.json()
    if data.get("errors"):
        raise RuntimeError(json.dumps(data["errors"]))
    return data["data"]


# In-process cache: path -> id
_PATH_ID_CACHE: Dict[str, int] = {}


def refresh_index() -> Dict[str, int]:
    data = _post(QUERY_LIST)
    mapping = {
        item["path"].strip("/"): int(item["id"]) for item in data["pages"]["list"]
    }
    _PATH_ID_CACHE.clear()
    _PATH_ID_CACHE.update(mapping)
    return _PATH_ID_CACHE


def list_pages(limit: int = 1000) -> list[Dict[str, Any]]:
    data = _post(QUERY_LIST)
    pages = []
    for item in data["pages"]["list"][:limit]:
        pages.append(
            {
                "id": int(item["id"]),
                "path": item["path"].strip("/"),
                "title": item.get("title") or "",
            }
        )
    return pages


def resolve_id(path: Optional[str] = None, id: Optional[int] = None) -> int:
    if id is not None:
        return int(id)
    if not path:
        raise ValueError("path or id is required")
    norm = path.strip("/")
    # cache hit?
    if norm in _PATH_ID_CACHE:
        return _PATH_ID_CACHE[norm]
    # try search exact match
    try:
        data = _post(QUERY_SEARCH, {"q": norm.split("/")[-1]})
        for item in data["pages"]["search"]:
            if item["path"].strip("/") == norm:
                _PATH_ID_CACHE[norm] = int(item["id"])
                return int(item["id"])
    except Exception:
        pass
    # fallback: full index
    mapping = refresh_index()
    if norm in mapping:
        return mapping[norm]
    raise FileNotFoundError(f"Page not found: {norm}")


def get_single(id: int) -> Dict[str, Any]:
    # try content first
    try:
        d = _post(QUERY_SINGLE_FULL, {"id": id})
        s = d["pages"]["single"]
        if s is None:
            raise FileNotFoundError(f"id {id} missing")
        return {
            "id": s["id"],
            "path": s["path"].strip("/"),
            "title": s.get("title") or "",
            "description": s.get("description") or "",
            "isPrivate": s.get("isPrivate"),
            "createdAt": s.get("createdAt") or "",
            "updatedAt": s.get("updatedAt") or "",
            "content": s.get("content") or "",
        }
    except Exception:
        # fallback: contentRaw
        d = _post(QUERY_SINGLE_RAW, {"id": id})
        s = d["pages"]["single"]
        if s is None:
            raise FileNotFoundError(f"id {id} missing")
        return {
            "id": s["id"],
            "path": s["path"].strip("/"),
            "title": s.get("title") or "",
            "description": s.get("description") or "",
            "isPrivate": s.get("isPrivate"),
            "createdAt": s.get("createdAt") or "",
            "updatedAt": s.get("updatedAt") or "",
            "content": s.get("contentRaw") or "",
        }


def delete_by_id(id: int) -> bool:
    try:
        d = _post(MUTATION_DELETE, {"id": id})
        ok = d["pages"]["delete"]["operation"]["succeeded"]
        return bool(ok)
    except Exception:
        # some versions/roles don't expose delete; upstream may forbid it
        return False
