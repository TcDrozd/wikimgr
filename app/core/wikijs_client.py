from __future__ import annotations

from dataclasses import dataclass

from app.wikijs_client import WikiError, WikiJSClient


@dataclass
class UpstreamError(Exception):
    status_code: int
    message: str


class UpstreamGraphQLError(UpstreamError):
    pass


class UpstreamNetworkError(UpstreamError):
    pass


def map_wiki_error(err: WikiError) -> UpstreamError:
    message = err.message or "Wiki.js upstream error"
    if err.status == 504:
        return UpstreamNetworkError(status_code=504, message=message)
    return UpstreamGraphQLError(status_code=502 if err.status >= 500 else err.status, message=message)


__all__ = [
    "WikiJSClient",
    "WikiError",
    "UpstreamError",
    "UpstreamGraphQLError",
    "UpstreamNetworkError",
    "map_wiki_error",
]
