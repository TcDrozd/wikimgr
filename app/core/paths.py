from __future__ import annotations

import os
import re


_SEGMENT_SEP_RE = re.compile(r"[ _]+")
_SEGMENT_BAD_RE = re.compile(r"[^a-z0-9-]+")
_MULTI_HYPHEN_RE = re.compile(r"-{2,}")
_SLASH_RE = re.compile(r"/+")
_ALLOWED_ROOTS_DEFAULT = [
    "homelab",
    "projects",
    "ai",
    "personal",
    "community",
    "meta",
]


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


def root_from_path(path: str) -> str | None:
    normalized = normalize_path(path)
    if normalized == "/":
        return None
    return normalized.strip("/").split("/")[0]


def parse_allowed_roots(raw: str | None) -> list[str]:
    if not raw:
        return list(_ALLOWED_ROOTS_DEFAULT)
    roots: list[str] = []
    seen: set[str] = set()
    for item in raw.split(","):
        seg = normalize_segment(item)
        if seg and seg not in seen:
            seen.add(seg)
            roots.append(seg)
    return roots or list(_ALLOWED_ROOTS_DEFAULT)


def configured_allowed_roots() -> list[str]:
    return parse_allowed_roots(os.getenv("WIKIMGR_ALLOWED_ROOTS"))


def _keyword_root_suggestions(normalized: str, allowed_roots: list[str]) -> list[str]:
    hints: list[str] = []
    if "gpu-vm" in normalized or "proxmox" in normalized:
        hints.append("homelab")
    if "openwebui" in normalized or "ollama" in normalized:
        hints.extend(["ai", "homelab"])

    out: list[str] = []
    for root in hints:
        if root in allowed_roots and root not in out:
            out.append(root)
    return out


def _segment_overlap_score(path_a: str, path_b: str) -> int:
    seg_a = {s for s in normalize_path(path_a).strip("/").split("/") if s}
    seg_b = {s for s in normalize_path(path_b).strip("/").split("/") if s}
    if not seg_a or not seg_b:
        return 0
    return len(seg_a.intersection(seg_b))


def preflight_analysis(
    raw_path: str, *, allowed_roots: list[str], existing_paths: list[str]
) -> dict:
    normalized = normalize_path(raw_path)
    root = root_from_path(normalized)
    is_valid_root = bool(root and root in allowed_roots)
    warnings: list[str] = []
    if normalized == "/":
        warnings.append("Path normalizes to root '/' and should include a page slug.")
    elif root and not is_valid_root:
        warnings.append(f"Root '{root}' is not in allowed roots.")

    suggestions: list[str] = []
    suffix = normalized[len(f"/{root}") :] if root else normalized
    if suffix in ("", "/"):
        suffix = ""

    if not is_valid_root and normalized != "/":
        for suggested_root in _keyword_root_suggestions(normalized, allowed_roots):
            candidate = f"/{suggested_root}{suffix}"
            if candidate not in suggestions:
                suggestions.append(candidate)

    scored: list[tuple[int, str]] = []
    for path in existing_paths:
        candidate = normalize_path(path)
        score = _segment_overlap_score(normalized, candidate)
        if score > 0:
            scored.append((score, candidate))

    for _, candidate in sorted(scored, key=lambda item: (-item[0], item[1])):
        if candidate not in suggestions:
            suggestions.append(candidate)
        if len(suggestions) >= 5:
            break

    return {
        "input": raw_path,
        "normalized": normalized,
        "is_valid_root": is_valid_root,
        "root": root,
        "allowed_roots": allowed_roots,
        "suggestions": suggestions,
        "warnings": warnings,
    }
