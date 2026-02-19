import os

from fastapi import Header, HTTPException, status

from app.core.auth import require_api_key


async def require_api_key_legacy(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    expected = os.getenv("WIKIMGR_API_KEY", "")
    if not expected:
        return
    if x_api_key != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


__all__ = ["require_api_key", "require_api_key_legacy"]
