import hashlib
import json

from fastapi import HTTPException, UploadFile


TRUTHY_VALUES = {"1", "true", "yes", "on"}


def parse_boolish(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in TRUTHY_VALUES


def parse_tags(raw_tags: str | None) -> list[str]:
    if raw_tags is None:
        return []
    text = raw_tags.strip()
    if not text:
        return []

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return [tag.strip() for tag in text.split(",") if tag.strip()]

    if not isinstance(parsed, list):
        raise HTTPException(status_code=400, detail="tags JSON must be a list of strings")
    return [str(tag).strip() for tag in parsed if str(tag).strip()]


def upload_idempotency_key(path: str, title: str, content_md: str) -> str:
    h = hashlib.sha256()
    h.update(path.encode())
    h.update(b"\x00")
    h.update(title.encode())
    h.update(b"\x00")
    h.update(content_md.encode())
    return h.hexdigest()


def validate_upload_file(file: UploadFile | None) -> UploadFile:
    if file is None:
        raise HTTPException(status_code=400, detail="file is required")
    filename = file.filename or ""
    if not filename.lower().endswith(".md"):
        raise HTTPException(status_code=400, detail="file must have a .md extension")
    return file


def validate_required_form_field(value: str | None, name: str) -> str:
    if value is None or not value.strip():
        raise HTTPException(status_code=400, detail=f"{name} is required")
    return value.strip()


async def read_upload_utf8(file: UploadFile) -> str:
    raw = await file.read()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="file must decode as UTF-8")
