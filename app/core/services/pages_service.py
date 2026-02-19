from __future__ import annotations

from app.core.errors import APIError
from app.core.wikijs_client import WikiError, WikiJSClient, map_wiki_error
from app.models import (
    DeletePageRequest,
    DeletePageResponse,
    GetPageResponse,
    PagePayload,
    UpsertPageRequest,
    UpsertPageResponse,
)
from app.wikijs_client import derive_idempotency_key
from app.wikijs_api import delete_by_id, get_single, resolve_id


def resolve_idempotency_key(
    payload: UpsertPageRequest,
    x_idempotency_key: str | None,
    legacy_x_idempotency_key: str | None,
) -> str:
    if x_idempotency_key:
        return x_idempotency_key
    if legacy_x_idempotency_key:
        return legacy_x_idempotency_key
    page_payload = PagePayload(**payload.model_dump())
    return derive_idempotency_key(page_payload)


async def upsert_page(
    payload: UpsertPageRequest,
    x_idempotency_key: str | None,
    legacy_x_idempotency_key: str | None,
) -> UpsertPageResponse:
    idem = resolve_idempotency_key(payload, x_idempotency_key, legacy_x_idempotency_key)
    page_payload = PagePayload(**payload.model_dump())
    try:
        wikijs_client = WikiJSClient.from_env()
        result = await wikijs_client.upsert_page(page_payload, idem_key=idem)
    except WikiError as e:
        upstream = map_wiki_error(e)
        raise APIError(upstream.status_code, "upstream_error", upstream.message)
    except APIError:
        raise
    except Exception as e:
        raise APIError(502, "upstream_error", str(e))
    return UpsertPageResponse(id=result["id"], path=result["path"], idempotency_key=idem)


def get_page(path: str | None = None, id: int | None = None) -> GetPageResponse:
    try:
        pid = resolve_id(path=path, id=id)
        return GetPageResponse(**get_single(pid))
    except ValueError as e:
        raise APIError(400, "bad_request", str(e))
    except FileNotFoundError as e:
        raise APIError(404, "not_found", str(e))
    except Exception as e:
        raise APIError(502, "upstream_error", f"get failed: {e}")


def delete_page(req: DeletePageRequest) -> DeletePageResponse:
    try:
        pid = resolve_id(path=req.path, id=req.id)
        ok = delete_by_id(pid)
        return DeletePageResponse(ok=ok, hard_deleted=ok, id=pid)
    except ValueError as e:
        raise APIError(400, "bad_request", str(e))
    except FileNotFoundError as e:
        raise APIError(404, "not_found", str(e))
    except Exception as e:
        raise APIError(502, "upstream_error", f"delete failed: {e}")
