from __future__ import annotations

import os
from typing import Annotated

from fastapi import Security
from fastapi.security import APIKeyHeader

from app.core.errors import APIError


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(
    x_api_key: Annotated[str | None, Security(api_key_header)],
) -> None:
    expected = os.getenv("WIKIMGR_API_KEY", "")
    if not expected:
        return
    if x_api_key != expected:
        raise APIError(status_code=401, code="unauthorized", message="Invalid API key")
