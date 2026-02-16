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


def render_tree_text(tree: dict[str, dict]) -> str:
    lines = ["."]

    def _walk(node: dict[str, dict], prefix: str) -> None:
        keys = sorted(node)
        for idx, key in enumerate(keys):
            is_last = idx == len(keys) - 1
            branch = "`-- " if is_last else "|-- "
            lines.append(f"{prefix}{branch}{key}")
            child_prefix = f"{prefix}{'    ' if is_last else '|   '}"
            _walk(node[key], child_prefix)

    _walk(tree, "")
    return "\n".join(lines)
