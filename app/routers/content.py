from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.content_tree import build_tree
from app.wikijs_api import list_pages

router = APIRouter(prefix="/content", tags=["content"])


@router.get("/tree")
def content_tree():
    try:
        pages = list_pages(limit=1000)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"list pages failed: {e}")

    paths = [item.get("path", "") for item in pages]
    tree = build_tree(paths)

    roots = [path.strip("/").split("/")[0] for path in paths if path and path.strip("/")]
    root_counts = {key: roots.count(key) for key in sorted(set(roots))}

    return {
        "roots": tree,
        "stats": {
            "page_count": len(paths),
            "root_counts": root_counts,
        },
    }
