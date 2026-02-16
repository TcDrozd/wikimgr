from __future__ import annotations

import re


_SEGMENT_SEP_RE = re.compile(r"[ _]+")
_SEGMENT_BAD_RE = re.compile(r"[^a-z0-9-]+")
_MULTI_HYPHEN_RE = re.compile(r"-{2,}")
_SLASH_RE = re.compile(r"/+")


def normalize_segment(raw: str) -> str:
    segment = (raw or "").strip().lower()
    segment = _SEGMENT_SEP_RE.sub("-", segment)
    segment = _SEGMENT_BAD_RE.sub("-", segment)
    segment = _MULTI_HYPHEN_RE.sub("-", segment)
    return segment.strip("-")


def normalize_path(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        return "/"

    parts = []
    for part in _SLASH_RE.split(value):
        segment = normalize_segment(part)
        if segment:
            parts.append(segment)

    if not parts:
        return "/"
    return "/" + "/".join(parts)
