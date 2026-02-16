from typing import Optional

from dotenv import load_dotenv
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import JSONResponse

from app.wikijs_api import delete_by_id, get_single, resolve_id
from .bulk_ops import router as bulk_ops_router
from .deps import require_api_key
from .log_utils import inject_request_id, setup_logging
from .models import DeleteReq, PagePayload, UploadPageResult, UpsertResult, BulkUploadResult
from .services.upload_service import (
    bulk_upload_workflow,
    execute_upsert,
    resolve_idempotency_key,
    upload_page_workflow,
)


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
    legacy_idem = request.headers.get("x_idempotency_key")
    idem = resolve_idempotency_key(payload, x_idempotency_key, legacy_idem)
    return await execute_upsert(payload, idem)


@app.post(
    "/pages/upload",
    response_model=UploadPageResult,
    summary="Upload markdown file and upsert page",
    description="Accepts multipart/form-data with a .md file and page metadata.",
    responses={400: {"description": "Bad upload input"}, 413: {"description": "Payload too large"}},
)
async def upload_page(
    request: Request,
    file: UploadFile | None = File(default=None, description="Markdown file (.md)"),
    path: str | None = Form(default=None, description="Target wiki page path"),
    title: str | None = Form(default=None, description="Page title"),
    description: str = Form(default="", description="Page description"),
    tags: str | None = Form(default=None, description='JSON list string (e.g. ["a","b"]) or CSV'),
    is_private: str | None = Form(default=None, description="Truthy values: 1,true,yes,on"),
    idempotency_key: str | None = Form(default=None, description="Optional request idempotency key"),
    api_ok: None = Depends(require_api_key),
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
):
    return await upload_page_workflow(
        file=file,
        path=path,
        title=title,
        description=description,
        tags=tags,
        is_private=is_private,
        form_idempotency_key=idempotency_key,
        header_idempotency_key=x_idempotency_key,
        legacy_idempotency_key=request.headers.get("x_idempotency_key"),
    )


@app.post(
    "/pages/bulk_upload",
    response_model=BulkUploadResult,
    summary="Bulk upload markdown files",
    description="Uploads multiple markdown files and upserts each to base_path/<filename-stem>.",
    responses={400: {"description": "Bad upload input"}, 413: {"description": "Payload too large"}},
)
async def bulk_upload_pages(
    files: list[UploadFile] | None = File(default=None, description="Markdown files (.md)"),
    base_path: str | None = Form(default=None, description="Base wiki path for all files"),
    description: str = Form(default="", description="Shared page description"),
    tags: str | None = Form(default=None, description="Shared JSON list string or CSV"),
    is_private: str | None = Form(default=None, description="Shared truthy values: 1,true,yes,on"),
    api_ok: None = Depends(require_api_key),
):
    return await bulk_upload_workflow(
        files=files,
        base_path=base_path,
        description=description,
        tags=tags,
        is_private=is_private,
    )


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
