from __future__ import annotations

from collections.abc import Iterable


def _sorted_tree(node: dict[str, dict]) -> dict[str, dict]:
    return {key: _sorted_tree(node[key]) for key in sorted(node)}


def build_tree(paths: list[str] | Iterable[str]) -> dict[str, dict]:
    tree: dict[str, dict] = {}
    for raw_path in paths:
        current = tree
        for segment in (part.strip() for part in str(raw_path).split("/")):
            if not segment:
                continue
            current = current.setdefault(segment, {})
    return _sorted_tree(tree)
