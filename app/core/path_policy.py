from __future__ import annotations

from app.wikijs_client import SEG_EXPANSIONS, MIN_SEG_LEN, normalize_path as _normalize_path
from app.wikijs_client import enforce_path_policy as _enforce_path_policy


def normalize_path(raw: str) -> str:
    return _normalize_path(raw)


def enforce_path_policy(path: str) -> str:
    return _enforce_path_policy(path)


__all__ = [
    "MIN_SEG_LEN",
    "SEG_EXPANSIONS",
    "normalize_path",
    "enforce_path_policy",
]
