from fastapi import APIRouter, Depends

from app.core.auth import require_api_key
from app.core.services.bulk_service import bulk_move, bulk_redirect, bulk_relink, inventory
from app.models import (
    BulkMoveRequest,
    BulkMoveResponse,
    BulkRedirectRequest,
    BulkRedirectResponse,
    BulkRelinkRequest,
    BulkRelinkResponse,
    ErrorResponse,
    InventoryResponse,
)

router = APIRouter(
    prefix="/pages",
    tags=["bulk"],
    dependencies=[Depends(require_api_key)],
)

ERROR_RESPONSES = {
    400: {"model": ErrorResponse},
    401: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    502: {"model": ErrorResponse},
    504: {"model": ErrorResponse},
}


@router.post("/bulk-move", response_model=BulkMoveResponse, responses=ERROR_RESPONSES)
async def bulk_move_endpoint(payload: BulkMoveRequest) -> BulkMoveResponse:
    return await bulk_move(payload)


@router.post("/bulk-redirect", response_model=BulkRedirectResponse, responses=ERROR_RESPONSES)
async def bulk_redirect_endpoint(payload: BulkRedirectRequest) -> BulkRedirectResponse:
    return await bulk_redirect(payload)


@router.post("/bulk-relink", response_model=BulkRelinkResponse, responses=ERROR_RESPONSES)
async def bulk_relink_endpoint(payload: BulkRelinkRequest) -> BulkRelinkResponse:
    return await bulk_relink(payload)


@router.get("/inventory", response_model=InventoryResponse, responses=ERROR_RESPONSES)
def inventory_endpoint(include_content: bool = False) -> InventoryResponse:
    return inventory(include_content=include_content)
