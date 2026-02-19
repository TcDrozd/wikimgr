from os import getenv

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.models import HealthResponse, ReadyResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(ok=True)


@router.get(
    "/ready",
    response_model=ReadyResponse,
    responses={503: {"model": ReadyResponse, "description": "Missing required Wiki.js env vars"}},
)
async def ready():
    missing: list[str] = []
    if not getenv("WIKIJS_BASE_URL"):
        missing.append("WIKIJS_BASE_URL missing")
    if not getenv("WIKIJS_API_TOKEN"):
        missing.append("WIKIJS_API_TOKEN missing")

    if missing:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=ReadyResponse(ready=False, reason="; ".join(missing)).model_dump(),
        )
    return ReadyResponse(ready=True)
