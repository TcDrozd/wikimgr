from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

load_dotenv()

from app.core.errors import APIError
from app.routers.api import api_router
from .log_utils import inject_request_id, setup_logging
from .models import ErrorResponse
from .routers.content import router as content_router
from .routers.legacy import router as legacy_router

app = FastAPI(title="Wiki Manager", version="0.2.0")
setup_logging()
app.include_router(api_router)
app.include_router(legacy_router, prefix="")
app.include_router(content_router, prefix="")


@app.middleware("http")
async def add_req_id(request, call_next):
    return await inject_request_id(request, call_next)


@app.exception_handler(APIError)
async def api_error_handler(_request: Request, exc: APIError):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(code=exc.code, message=exc.message, details=exc.details).model_dump(),
    )
