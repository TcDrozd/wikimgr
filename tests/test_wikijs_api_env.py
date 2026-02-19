from app import wikijs_api


class _FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"data": {"pages": {"list": []}}}


class _FakeClient:
    def __init__(self, *args, **kwargs):
        self.last_url = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, headers, json):
        self.last_url = url
        assert url == "http://example.test/graphql"
        assert headers["Authorization"] == "Bearer token-1"
        return _FakeResponse()


def test_wikijs_api_uses_runtime_env(monkeypatch):
    monkeypatch.setenv("WIKIJS_BASE_URL", "http://example.test")
    monkeypatch.setenv("WIKIJS_API_TOKEN", "token-1")
    monkeypatch.setattr(wikijs_api.httpx, "Client", _FakeClient)

    pages = wikijs_api.list_pages(limit=1)
    assert pages == []
