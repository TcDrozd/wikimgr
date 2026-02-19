from __future__ import annotations

import re
from typing import Any

from app.core.errors import APIError
from app.core.services.pages_service import get_page, upsert_page
from app.models import (
    BulkMoveAppliedItem,
    BulkMoveRequest,
    BulkMoveResponse,
    BulkMoveSkippedItem,
    BulkRedirectAppliedItem,
    BulkRedirectRequest,
    BulkRedirectResponse,
    BulkRelinkRequest,
    BulkRelinkResponse,
    DeletePageRequest,
    InventoryPage,
    InventoryResponse,
    UpsertPageRequest,
)
from app.wikijs_api import get_single, refresh_index


LINK_RE = re.compile(r"\]\((/[^\s)]+)\)")


def rewrite_links(md: str, mapping: dict[str, str]) -> str:
    def _sub(match: re.Match[str]) -> str:
        old = match.group(1).strip().strip("/")
        new = mapping.get(old)
        if not new:
            return match.group(0)
        return f'](/{new.strip("/")})'

    return LINK_RE.sub(_sub, md)


def moved_stub(to_path: str) -> str:
    return (
        "# Moved\n\n"
        f"This page has moved to **[{to_path}](/{to_path.strip('/')})**.\n\n"
        "> If you followed a bookmark, please update it."
    )


async def bulk_move(req: BulkMoveRequest) -> BulkMoveResponse:
    if not req.moves:
        raise APIError(400, "bad_request", "No moves provided")

    report = BulkMoveResponse(dry_run=req.dry_run)

    for move in req.moves:
        src = (move.from_path or "").strip("/")
        dst = (move.to_path or "").strip("/")
        if not src or not dst or src == dst:
            report.skipped.append(BulkMoveSkippedItem(move=move, reason="noop/invalid"))
            continue

        try:
            src_page = get_page(path=src)
            title = src_page.title or dst.split("/")[-1].replace("-", " ").title()
            desc = src_page.description or ""
            content = src_page.content or ""

            if req.dry_run:
                report.applied.append(
                    BulkMoveAppliedItem.model_validate({"from": src, "to": dst, "dry": True})
                )
                continue

            await upsert_page(
                UpsertPageRequest(
                    path=dst,
                    title=title,
                    content=content,
                    description=desc,
                    tags=[],
                    is_private=False,
                ),
                x_idempotency_key=None,
                legacy_x_idempotency_key=None,
            )

            if move.merge:
                await upsert_page(
                    UpsertPageRequest(
                        path=src,
                        title=title,
                        content=moved_stub(dst),
                        description="Moved",
                        tags=[],
                        is_private=False,
                    ),
                    x_idempotency_key=None,
                    legacy_x_idempotency_key=None,
                )
            else:
                from app.core.services.pages_service import delete_page

                try:
                    delete_page(DeletePageRequest(path=src))
                except APIError:
                    await upsert_page(
                        UpsertPageRequest(
                            path=src,
                            title=title,
                            content=moved_stub(dst),
                            description="Moved",
                            tags=[],
                            is_private=False,
                        ),
                        x_idempotency_key=None,
                        legacy_x_idempotency_key=None,
                    )

            report.applied.append(BulkMoveAppliedItem.model_validate({"from": src, "to": dst}))
        except APIError as e:
            report.errors.append({"move": move, "error": f"{e.status_code}: {e.message}"})
        except Exception as e:
            report.errors.append({"move": move, "error": repr(e)})

    return report


async def bulk_redirect(req: BulkRedirectRequest) -> BulkRedirectResponse:
    if not req.redirects:
        raise APIError(400, "bad_request", "No redirects provided")

    report = BulkRedirectResponse()
    for redirect in req.redirects:
        src = (redirect.from_path or "").strip("/")
        dst = (redirect.to_path or "").strip("/")
        if not src or not dst or src == dst:
            continue
        try:
            title_guess = src.split("/")[-1].replace("-", " ").title()
            await upsert_page(
                UpsertPageRequest(
                    path=src,
                    title=title_guess,
                    content=moved_stub(dst),
                    description="Moved",
                    tags=[],
                    is_private=False,
                ),
                x_idempotency_key=None,
                legacy_x_idempotency_key=None,
            )
            report.applied.append(BulkRedirectAppliedItem.model_validate({"from": src, "to": dst}))
        except APIError as e:
            report.errors.append({"redirect": redirect, "error": f"{e.status_code}: {e.message}"})
        except Exception as e:
            report.errors.append({"redirect": redirect, "error": repr(e)})

    return report


async def bulk_relink(req: BulkRelinkRequest) -> BulkRelinkResponse:
    normalized_mapping = {
        str(k).strip("/"): str(v).strip("/")
        for k, v in req.mapping.items()
        if str(k).strip("/") and str(v).strip("/")
    }

    inventory = inventory(include_content=False)
    pages = inventory.pages

    report = BulkRelinkResponse()
    for page in pages:
        path = (page.path or "").strip("/")
        if not path:
            continue

        scope = req.scope
        if isinstance(scope, list) and scope and path not in scope:
            continue

        try:
            cur = get_page(path=path)
            content = cur.content or ""
            new_md = rewrite_links(content, normalized_mapping)
            if new_md != content:
                await upsert_page(
                    UpsertPageRequest(
                        path=path,
                        title=cur.title or path.split("/")[-1],
                        content=new_md,
                        description=cur.description or "",
                        tags=[],
                        is_private=False,
                    ),
                    x_idempotency_key=None,
                    legacy_x_idempotency_key=None,
                )
                report.updated.append(path)
        except APIError as e:
            report.errors.append({"path": path, "error": f"{e.status_code}: {e.message}"})
        except Exception as e:
            report.errors.append({"path": path, "error": repr(e)})

    return report


def inventory(include_content: bool = False) -> InventoryResponse:
    try:
        path_to_id = refresh_index()
        pages: list[InventoryPage] = []
        for path, page_id in path_to_id.items():
            try:
                page_data: dict[str, Any] = get_single(page_id)
                if not include_content:
                    page_data.pop("content", None)
                pages.append(InventoryPage(**page_data))
            except Exception as e:
                pages.append(
                    InventoryPage(
                        id=page_id,
                        path=path,
                        title=path.split("/")[-1],
                        error=str(e),
                    )
                )

        return InventoryResponse(count=len(pages), pages=pages)
    except Exception as e:
        raise APIError(502, "upstream_error", f"Inventory generation failed: {e}")
