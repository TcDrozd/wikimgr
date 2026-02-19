from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query

from app.core.auth import require_api_key
from app.core.services.pages_service import delete_page, get_page, upsert_page
from app.models import (
    DeletePageRequest,
    DeletePageResponse,
    ErrorResponse,
    GetPageResponse,
    UpsertPageRequest,
    UpsertPageResponse,
)

router = APIRouter(
    prefix="/pages",
    tags=["pages"],
    dependencies=[Depends(require_api_key)],
)

ERROR_RESPONSES = {
    400: {"model": ErrorResponse},
    401: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    502: {"model": ErrorResponse},
    504: {"model": ErrorResponse},
}


@router.post(
    "/upsert",
    response_model=UpsertPageResponse,
    responses=ERROR_RESPONSES,
)
async def upsert_page_endpoint(
    payload: UpsertPageRequest,
    x_idempotency_key: Annotated[str | None, Header(alias="X-Idempotency-Key")] = None,
    legacy_x_idempotency_key: Annotated[str | None, Header(alias="x_idempotency_key")] = None,
) -> UpsertPageResponse:
    return await upsert_page(payload, x_idempotency_key, legacy_x_idempotency_key)


@router.get(
    "",
    response_model=GetPageResponse,
    responses=ERROR_RESPONSES,
)
def get_page_by_path(path: str = Query(..., description="Wiki page path")) -> GetPageResponse:
    return get_page(path=path)


@router.get(
    "/{id:int}",
    response_model=GetPageResponse,
    responses=ERROR_RESPONSES,
)
def get_page_by_id(id: int) -> GetPageResponse:
    return get_page(id=id)


@router.delete(
    "/{id:int}",
    response_model=DeletePageResponse,
    responses=ERROR_RESPONSES,
)
def delete_page_by_id(id: int) -> DeletePageResponse:
    return delete_page(DeletePageRequest(id=id))


@router.delete(
    "",
    response_model=DeletePageResponse,
    responses=ERROR_RESPONSES,
)
def delete_page_by_path(path: str = Query(..., description="Wiki page path")) -> DeletePageResponse:
    return delete_page(DeletePageRequest(path=path))
