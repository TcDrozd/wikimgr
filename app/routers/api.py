from fastapi import APIRouter

from app.routers.bulk import router as bulk_router
from app.routers.health import router as health_router
from app.routers.pages import router as pages_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(bulk_router)
api_router.include_router(pages_router)
