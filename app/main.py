from fastapi import FastAPI, Depends, Header, HTTPException, status
from fastapi.responses import JSONResponse
from .deps import require_api_key
from .logging import setup_logging, inject_request_id
from .models import PagePayload, UpsertResult
from .wikijs_client import WikiJSClient, WikiError, derive_idempotency_key
from dotenv import load_dotenv


load_dotenv()

app = FastAPI(title="Wiki Manager", version="0.2.0")
setup_logging()

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
    api_ok: None = Depends(require_api_key),
    x_idempotency_key: str | None = Header(default=None, convert_underscores=False),
):
    client = WikiJSClient.from_env()
    idem = x_idempotency_key or derive_idempotency_key(payload)
    try:
        result = await client.upsert_page(payload, idem_key=idem)
        return UpsertResult(id=result["id"], path=result["path"], idempotency_key=idem)
    except WikiError as e:
        # Map known failures
        raise HTTPException(status_code=e.status, detail=e.message)