from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.models import (
    BulkUploadFailure,
    BulkUploadResult,
    BulkUploadSuccess,
    PagePayload,
    UploadPageResult,
    UpsertResult,
)
from app.upload_utils import (
    parse_boolish,
    parse_tags,
    read_upload_utf8,
    upload_idempotency_key,
    validate_required_form_field,
    validate_upload_file,
)
from app.wikijs_client import WikiError, WikiJSClient, derive_idempotency_key


async def execute_upsert(
    payload: PagePayload,
    idem: str,
    client: WikiJSClient | None = None,
) -> UpsertResult:
    wikijs_client = client or WikiJSClient.from_env()
    try:
        result = await wikijs_client.upsert_page(payload, idem_key=idem)
        return UpsertResult(id=result["id"], path=result["path"], idempotency_key=idem)
    except WikiError as e:
        raise HTTPException(status_code=e.status, detail=e.message)


def resolve_idempotency_key(
    payload: PagePayload,
    header_idempotency_key: str | None,
    legacy_idempotency_key: str | None,
) -> str:
    return header_idempotency_key or legacy_idempotency_key or derive_idempotency_key(payload)


async def upload_page_workflow(
    *,
    file: UploadFile | None,
    path: str | None,
    title: str | None,
    description: str,
    tags: str | None,
    is_private: str | None,
    form_idempotency_key: str | None,
    header_idempotency_key: str | None,
    legacy_idempotency_key: str | None,
) -> UploadPageResult:
    validated_file = validate_upload_file(file)
    clean_path = validate_required_form_field(path, "path")
    clean_title = validate_required_form_field(title, "title")
    content_md = await read_upload_utf8(validated_file)
    parsed_tags = parse_tags(tags)
    parsed_private = parse_boolish(is_private)

    idem = (
        header_idempotency_key
        or legacy_idempotency_key
        or (form_idempotency_key.strip() if form_idempotency_key else None)
        or upload_idempotency_key(clean_path, clean_title, content_md)
    )

    payload = PagePayload(
        path=clean_path,
        title=clean_title,
        content_md=content_md,
        description=description or "",
        is_private=parsed_private,
        tags=parsed_tags,
    )
    upserted = await execute_upsert(payload, idem)
    return UploadPageResult(ok=True, idempotency_key=idem, page=upserted)


async def bulk_upload_workflow(
    *,
    files: list[UploadFile] | None,
    base_path: str | None,
    description: str,
    tags: str | None,
    is_private: str | None,
) -> BulkUploadResult:
    clean_base_path = validate_required_form_field(base_path, "base_path").strip("/")
    if not files:
        raise HTTPException(status_code=400, detail="at least one file is required")

    parsed_tags = parse_tags(tags)
    parsed_private = parse_boolish(is_private)
    client = WikiJSClient.from_env()
    successes: list[BulkUploadSuccess] = []
    failures: list[BulkUploadFailure] = []

    for file in files:
        filename = file.filename or "unknown"
        try:
            validated_file = validate_upload_file(file)
            content_md = await read_upload_utf8(validated_file)
            stem = Path(filename).stem.strip()
            if not stem:
                raise HTTPException(status_code=400, detail="filename must include a title stem")
            full_path = f"{clean_base_path}/{stem}"
            idem = upload_idempotency_key(full_path, stem, content_md)
            payload = PagePayload(
                path=full_path,
                title=stem,
                content_md=content_md,
                description=description or "",
                is_private=parsed_private,
                tags=parsed_tags,
            )
            upserted = await execute_upsert(payload, idem, client=client)
            successes.append(BulkUploadSuccess(filename=filename, idempotency_key=idem, page=upserted))
        except HTTPException as e:
            failures.append(BulkUploadFailure(filename=filename, reason=str(e.detail)))

    return BulkUploadResult(
        ok=len(failures) == 0,
        base_path=clean_base_path,
        successes=successes,
        failures=failures,
    )
