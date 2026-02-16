from typing import Optional
from fastapi import FastAPI, Depends, Header, HTTPException, Query, status, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.wikijs_api import delete_by_id, get_single, resolve_id
from .deps import require_api_key
from .log_utils import setup_logging, inject_request_id
from .models import DeleteReq, PagePayload, UpsertResult
from .wikijs_client import WikiJSClient, WikiError, derive_idempotency_key
from .bulk_ops import router as bulk_ops_router
from dotenv import load_dotenv


load_dotenv()

app = FastAPI(title="Wiki Manager", version="0.2.0")
setup_logging()
app.include_router(bulk_ops_router, prefix="")

@app.middleware("http")
async def add_req_id(request, call_next):
    return await inject_request_id(request, call_next)

@app.get("/healthz")
async def healthz():
    return {"ok": True}

@app.get("/readyz")
async def readyz():
    # Simple readiness check: env presence (token/base_url)
    from os import getenv
    ready = bool(getenv("WIKIJS_BASE_URL") and getenv("WIKIJS_API_TOKEN"))
    return JSONResponse({"ready": ready}, status_code=200 if ready else 503)

@app.post("/pages/upsert", response_model=UpsertResult)
async def upsert_page(
    payload: PagePayload,
    request: Request,
    api_ok: None = Depends(require_api_key),
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
):
    client = WikiJSClient.from_env()
    legacy_idem = request.headers.get("x_idempotency_key")
    idem = x_idempotency_key or legacy_idem or derive_idempotency_key(payload)
    try:
        result = await client.upsert_page(payload, idem_key=idem)
        return UpsertResult(id=result["id"], path=result["path"], idempotency_key=idem)
    except WikiError as e:
        # Map known failures
        raise HTTPException(status_code=e.status, detail=e.message)

@app.get("/wikimgr/get")
def wikimgr_get(path: Optional[str] = Query(default=None), id: Optional[int] = Query(default=None)):
    try:
        pid = resolve_id(path=path, id=id)
        page = get_single(pid)
        return page
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"get failed: {e}")

@app.post("/wikimgr/delete")
def wikimgr_delete(req: DeleteReq):
    try:
        pid = resolve_id(path=req.path, id=req.id)
        ok = delete_by_id(pid)
        return {"ok": ok, "hard_deleted": ok, "id": pid}
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"delete failed: {e}")
