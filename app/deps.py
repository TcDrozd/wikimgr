import os
from fastapi import Header, HTTPException, status

API_KEY = os.getenv("WIKIMGR_API_KEY", "")

async def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    if not API_KEY:
        return  # disabled in dev if unset
    if x_api_key != API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
