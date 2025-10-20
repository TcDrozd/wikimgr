# bulk_ops.py
from __future__ import annotations
import os, re, json, asyncio
from typing import Dict, List, Optional, Tuple
from fastapi import APIRouter, HTTPException
import httpx

router = APIRouter()

# ---- Config ----
# Allow a single base URL to control internal endpoints. Individual endpoint env
# vars still override if set. Default base matches docker-compose (port 8080).
WKMGR_BASE_URL = os.getenv("WKMGR_BASE_URL", "http://127.0.0.1:8080").rstrip('/')

UPSERT_URL = os.getenv("WKMGR_UPSERT_URL", f"{WKMGR_BASE_URL}/pages/upsert")
GET_URL    = os.getenv("WKMGR_GET_URL",    f"{WKMGR_BASE_URL}/wikimgr/get")
DELETE_URL = os.getenv("WKMGR_DELETE_URL", f"{WKMGR_BASE_URL}/wikimgr/delete")

# Optional bearer for your wikimgr internal API
AUTH_BEARER = os.getenv("WKMGR_BEARER", "")

HEADERS = {"Authorization": f"Bearer {AUTH_BEARER}"} if AUTH_BEARER else {}

# ---- Helpers to talk to your existing endpoints ----
async def get_page(path: str) -> Dict:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(GET_URL, params={"path": path}, headers=HEADERS)
        if r.status_code == 404:
            return {}  # not found ok
        if r.is_error:
            raise HTTPException(r.status_code, r.text)
        return r.json()

async def upsert_page(path: str, title: str, content: str, description: str = "") -> Dict:
    payload = {"path": path, "title": title, "content": content, "description": description}
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(UPSERT_URL, json=payload, headers=HEADERS)
        if r.is_error:
            raise HTTPException(r.status_code, r.text)
        return r.json()

async def delete_page(path: str) -> Dict:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(DELETE_URL, json={"path": path}, headers=HEADERS)
        if r.status_code in (404, 410):
            return {"ok": True, "note": "already gone"}
        if r.is_error:
            raise HTTPException(r.status_code, r.text)
        return r.json()

# ---- Relink utility (very safe regex for markdown links to paths) ----
LINK_RE = re.compile(r'\]\((/[^\s)]+)\)')  # matches ](/some/path)

def rewrite_links(md: str, mapping: Dict[str, str]) -> str:
    # exact-path mapping only. For dir moves, extend later.
    def _sub(m):
        old = m.group(1).strip().strip("/")
        new = mapping.get(old)
        if not new:
            return m.group(0)
        # keep leading slash
        return f'](/{"%s" % new.strip("/")})'
    return LINK_RE.sub(_sub, md)

def moved_stub(to_path: str) -> str:
    # works even if Wiki.js doesn't do front-matter redirects
    return (
        f"# Moved\n\n"
        f"This page has moved to **[{to_path}](/{to_path.strip('/')})**.\n\n"
        f"> If you followed a bookmark, please update it."
    )

# ---- Endpoints ----
@router.get("/wikimgr/health")
async def health():
    return {"ok": True}

@router.post("/wikimgr/pages/bulk-move")
async def bulk_move(body: Dict):
    """
    body = {
      "moves": [{"id": 123, "from_path": "old/x", "to_path": "New/X", "merge": false}, ...],
      "dry_run": true|false
    }
    """
    moves: List[Dict] = body.get("moves") or []
    dry = bool(body.get("dry_run"))

    if not moves:
        raise HTTPException(400, "No moves provided")

    report = {"dry_run": dry, "applied": [], "skipped": [], "errors": []}

    for m in moves:
        src = (m.get("from_path") or "").strip("/")
        dst = (m.get("to_path") or "").strip("/")
        merge = bool(m.get("merge"))
        if not src or not dst or src == dst:
            report["skipped"].append({"move": m, "reason": "noop/invalid"})
            continue

        try:
            src_page = await get_page(src)
            if not src_page:
                report["errors"].append({"move": m, "error": "source not found"})
                continue

            title = src_page.get("title") or dst.split("/")[-1].replace("-", " ").title()
            desc  = src_page.get("description") or ""
            content = src_page.get("content") or ""

            if dry:
                report["applied"].append({"from": src, "to": dst, "dry": True})
                continue

            # 1) upsert new
            await upsert_page(dst, title=title, content=content, description=desc)

            # 2) either delete old or replace with stub (redirect-like)
            if merge:
                # leave old as stub pointing to canonical dst
                await upsert_page(src, title=title, content=moved_stub(dst), description="Moved")
            else:
                try:
                    await delete_page(src)
                except HTTPException:
                    # fallback to stub if delete unsupported
                    await upsert_page(src, title=title, content=moved_stub(dst), description="Moved")

            report["applied"].append({"from": src, "to": dst})
        except HTTPException as e:
            report["errors"].append({"move": m, "error": f"{e.status_code}: {e.detail}"})
        except Exception as e:
            report["errors"].append({"move": m, "error": repr(e)})

    return report

@router.post("/wikimgr/pages/bulk-redirect")
async def bulk_redirect(body: Dict):
    """
    body = { "redirects": [{"from_path": "old", "to_path": "New"}, ...] }
    -> creates/overwrites 'from_path' with a stub pointing to 'to_path'
    """
    redirects: List[Dict] = body.get("redirects") or []
    if not redirects:
        raise HTTPException(400, "No redirects provided")

    report = {"applied": [], "errors": []}
    for r in redirects:
        src = (r.get("from_path") or "").strip("/")
        dst = (r.get("to_path") or "").strip("/")
        if not src or not dst or src == dst:
            continue
        try:
            title_guess = src.split("/")[-1].replace("-", " ").title()
            await upsert_page(src, title=title_guess, content=moved_stub(dst), description="Moved")
            report["applied"].append({"from": src, "to": dst})
        except HTTPException as e:
            report["errors"].append({"redirect": r, "error": f"{e.status_code}: {e.detail}"})
        except Exception as e:
            report["errors"].append({"redirect": r, "error": repr(e)})

    return report

@router.post("/wikimgr/pages/bulk-relink")
async def bulk_relink(body: Dict):
    """
    body = {
      "mapping": {"old/path": "New/Path", ...}  # optional; if omitted, expect /wikimgr/pages/inventory.json to be used by your existing code
      "scope": "all" | "touched" | list-of-paths
    }
    strategy: ask your existing "get" to retrieve page content, rewrite internal md links, upsert back.
    """
    mapping: Dict[str, str] = body.get("mapping") or {}
    scope = body.get("scope", "all")

    if not mapping:
        # allow empty mapping for now (no-ops) so you can test wiring
        pass

    # naive scope: rely on an existing inventory endpoint if you have it; else bail
    # Inventory endpoint may be hosted on the same service or separately. Use
    # WKMGR_INVENTORY_JSON to override; otherwise default to the same base but
    # keep the previous path.
    INV_URL = os.getenv("WKMGR_INVENTORY_JSON", f"{os.getenv('WKMGR_INVENTORY_JSON', '')}" )
    if not INV_URL:
        # default to localhost host: the inventory endpoint often lives on the
        # same service under /wikimgr/pages/inventory.json (port 8080), but
        # keep it configurable via WKMGR_INVENTORY_JSON.
        INV_URL = f"{WKMGR_BASE_URL}/wikimgr/pages/inventory.json"
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.get(INV_URL, headers=HEADERS)
        if r.is_error:
            raise HTTPException(500, f"inventory fetch failed: {r.status_code} {r.text}")
        pages = r.json()

    report = {"updated": [], "errors": []}
    for p in pages:
        path = (p.get("path") or "").strip("/")
        if not path:
            continue

        # scope filtering
        if scope == "touched":
            # caller will usually pass a list later; for now treat as 'all'
            pass
        elif isinstance(scope, list) and scope and path not in scope:
            continue

        try:
            cur = await get_page(path)
            if not cur:
                continue
            content = cur.get("content") or ""
            new_md = rewrite_links(content, mapping)
            if new_md != content:
                await upsert_page(path, title=cur.get("title") or path.split("/")[-1], content=new_md, description=cur.get("description") or "")
                report["updated"].append(path)
        except HTTPException as e:
            report["errors"].append({"path": path, "error": f"{e.status_code}: {e.detail}"})
        except Exception as e:
            report["errors"].append({"path": path, "error": repr(e)})

    return report

# Add to bulk_ops.py after the other endpoints
@router.get("/wikimgr/pages/inventory.json")
async def inventory_json(include_content: bool = False):
    """
    Returns a complete list of all pages with metadata.
    Used by bulk-relink and other operations that need page inventory.
    """
    try:
        from app.wikijs_api import refresh_index, get_single
        
        path_to_id = refresh_index()
        
        pages = []
        for path, page_id in path_to_id.items():
            try:
                page_data = get_single(page_id)
                if not include_content:
                    page_data.pop("content", None)
                pages.append(page_data)
            except Exception as e:
                pages.append({
                    "id": page_id,
                    "path": path, 
                    "title": path.split("/")[-1],
                    "error": str(e)
                })
        
        return {
            "count": len(pages),
            "pages": pages
        }
        
    except Exception as e:
        raise HTTPException(500, f"Inventory generation failed: {str(e)}")