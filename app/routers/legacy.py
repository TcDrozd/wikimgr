from __future__ import annotations

from os import getenv
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import JSONResponse

from app.core.services.bulk_service import bulk_move, bulk_redirect, bulk_relink, inventory
from app.core.services.pages_service import delete_page, get_page
from app.deps import require_api_key_legacy
from app.models import (
    BulkMoveRequest,
    BulkMoveResponse,
    BulkRedirectRequest,
    BulkRedirectResponse,
    BulkRelinkRequest,
    BulkRelinkResponse,
    BulkUploadResult,
    DeletePageRequest,
    DeleteReq,
    InventoryResponse,
    PagePayload,
    UploadPageResult,
    UpsertResult,
)
from app.services.upload_service import (
    bulk_upload_workflow,
    execute_upsert,
    resolve_idempotency_key,
    upload_page_workflow,
)

router = APIRouter(tags=["legacy"])


def _set_deprecation_headers(response: Response, successor: str) -> None:
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = f'<{successor}>; rel="successor-version"'


@router.get("/healthz")
async def healthz(response: Response):
    _set_deprecation_headers(response, "/api/v1/health")
    return {"ok": True}


@router.get("/readyz")
async def readyz(response: Response):
    _set_deprecation_headers(response, "/api/v1/ready")
    ready = bool(getenv("WIKIJS_BASE_URL") and getenv("WIKIJS_API_TOKEN"))
    return JSONResponse({"ready": ready}, status_code=200 if ready else 503, headers=response.headers)


@router.post("/pages/upsert", response_model=UpsertResult)
async def legacy_upsert_page(
    payload: PagePayload,
    request: Request,
    response: Response,
    _api_ok: None = Depends(require_api_key_legacy),
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
    legacy_x_idempotency_key: str | None = Header(default=None, alias="x_idempotency_key"),
):
    _set_deprecation_headers(response, "/api/v1/pages/upsert")
    legacy_idem = legacy_x_idempotency_key or request.headers.get("x_idempotency_key")
    idem = resolve_idempotency_key(payload, x_idempotency_key, legacy_idem)
    return await execute_upsert(payload, idem)


@router.post(
    "/pages/upload",
    response_model=UploadPageResult,
    summary="Upload markdown file and upsert page (legacy)",
    description="Accepts multipart/form-data with a .md file and page metadata.",
    responses={400: {"description": "Bad upload input"}, 413: {"description": "Payload too large"}},
)
async def legacy_upload_page(
    request: Request,
    response: Response,
    file: UploadFile | None = File(default=None, description="Markdown file (.md)"),
    path: str | None = Form(default=None, description="Target wiki page path"),
    title: str | None = Form(default=None, description="Page title"),
    description: str = Form(default="", description="Page description"),
    tags: str | None = Form(default=None, description='JSON list string (e.g. ["a","b"]) or CSV'),
    is_private: str | None = Form(default=None, description="Truthy values: 1,true,yes,on"),
    idempotency_key: str | None = Form(default=None, description="Optional request idempotency key"),
    _api_ok: None = Depends(require_api_key_legacy),
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
):
    _set_deprecation_headers(response, "/api/v1/pages/upsert")
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


@router.post(
    "/pages/bulk_upload",
    response_model=BulkUploadResult,
    summary="Bulk upload markdown files (legacy)",
    description="Uploads multiple markdown files and upserts each to base_path/<filename-stem>.",
    responses={400: {"description": "Bad upload input"}, 413: {"description": "Payload too large"}},
)
async def legacy_bulk_upload_pages(
    response: Response,
    files: list[UploadFile] | None = File(default=None, description="Markdown files (.md)"),
    base_path: str | None = Form(default=None, description="Base wiki path for all files"),
    description: str = Form(default="", description="Shared page description"),
    tags: str | None = Form(default=None, description="Shared JSON list string or CSV"),
    is_private: str | None = Form(default=None, description="Shared truthy values: 1,true,yes,on"),
    _api_ok: None = Depends(require_api_key_legacy),
):
    _set_deprecation_headers(response, "/api/v1/pages/upsert")
    return await bulk_upload_workflow(
        files=files,
        base_path=base_path,
        description=description,
        tags=tags,
        is_private=is_private,
    )


@router.get("/wikimgr/get")
def wikimgr_get(
    response: Response,
    path: Optional[str] = Query(default=None),
    id: Optional[int] = Query(default=None),
    _api_ok: None = Depends(require_api_key_legacy),
):
    _set_deprecation_headers(response, "/api/v1/pages")
    try:
        return get_page(path=path, id=id)
    except Exception as e:
        status_code = getattr(e, "status_code", 500)
        message = getattr(e, "message", str(e))
        if status_code == 404:
            raise HTTPException(404, message)
        if status_code == 400:
            status_code = 500
        raise HTTPException(status_code, f"get failed: {message}")


@router.post("/wikimgr/delete")
def wikimgr_delete(req: DeleteReq, response: Response, _api_ok: None = Depends(require_api_key_legacy)):
    _set_deprecation_headers(response, "/api/v1/pages")
    try:
        return delete_page(DeletePageRequest(path=req.path, id=req.id, soft=req.soft))
    except Exception as e:
        status_code = getattr(e, "status_code", 500)
        message = getattr(e, "message", str(e))
        if status_code == 404:
            raise HTTPException(404, message)
        if status_code == 400:
            status_code = 500
        raise HTTPException(status_code, f"delete failed: {message}")


@router.get("/wikimgr/health")
async def wikimgr_health(response: Response):
    _set_deprecation_headers(response, "/api/v1/health")
    return {"ok": True}


@router.post("/wikimgr/pages/bulk-move", response_model=BulkMoveResponse)
async def legacy_bulk_move(
    payload: BulkMoveRequest,
    response: Response,
    _api_ok: None = Depends(require_api_key_legacy),
):
    _set_deprecation_headers(response, "/api/v1/pages/bulk-move")
    return await bulk_move(payload)


@router.post("/wikimgr/pages/bulk-redirect", response_model=BulkRedirectResponse)
async def legacy_bulk_redirect(
    payload: BulkRedirectRequest,
    response: Response,
    _api_ok: None = Depends(require_api_key_legacy),
):
    _set_deprecation_headers(response, "/api/v1/pages/bulk-redirect")
    return await bulk_redirect(payload)


@router.post("/wikimgr/pages/bulk-relink", response_model=BulkRelinkResponse)
async def legacy_bulk_relink(
    payload: BulkRelinkRequest,
    response: Response,
    _api_ok: None = Depends(require_api_key_legacy),
):
    _set_deprecation_headers(response, "/api/v1/pages/bulk-relink")
    return await bulk_relink(payload)


@router.get("/wikimgr/pages/inventory.json", response_model=InventoryResponse)
async def legacy_inventory_json(
    response: Response,
    include_content: bool = False,
    _api_ok: None = Depends(require_api_key_legacy),
):
    _set_deprecation_headers(response, "/api/v1/pages/inventory")
    return inventory(include_content=include_content)
