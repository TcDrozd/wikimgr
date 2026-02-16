import pytest
import hashlib
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("WIKIJS_BASE_URL", "http://wikijs.local")
    monkeypatch.setenv("WIKIJS_API_TOKEN", "test-token")
    # Disable API key during tests
    monkeypatch.delenv("WIKIMGR_API_KEY", raising=False)

client = TestClient(app)

def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json()["ok"] is True

def test_upsert_happy(monkeypatch):
    async def fake_upsert_page(self, payload, idem_key):
        return {"id": 123, "path": payload.path}
    from app import wikijs_client
    monkeypatch.setattr(wikijs_client.WikiJSClient, "upsert_page", fake_upsert_page)

    payload = {
        "path": "AI/Tools/Ollama",
        "title": "Ollama",
        "content": "# Hello",
        "description": "desc",
        "is_private": False
    }
    r = client.post("/pages/upsert", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == 123
    assert body["path"] == "AI/Tools/Ollama"
    assert "idempotency_key" in body

def test_upsert_edge_upstream_fail(monkeypatch):
    from app.wikijs_client import WikiError, WikiJSClient
    async def boom(self, payload, idem_key):
        raise WikiError(503, "upstream down")
    monkeypatch.setattr(WikiJSClient, "upsert_page", boom)

    r = client.post("/pages/upsert", json={
        "path": "AI/Tools/Fail",
        "title": "Fail",
        "content_md": "# x"
    })
    assert r.status_code == 503
    assert "upstream" in r.json()["detail"]

def test_upsert_requires_content():
    r = client.post("/pages/upsert", json={
        "path": "AI/Tools/Fail",
        "title": "Fail"
    })
    assert r.status_code == 422


def test_upsert_honors_x_idempotency_key(monkeypatch):
    async def fake_upsert_page(self, payload, idem_key):
        return {"id": 123, "path": payload.path}

    from app import wikijs_client

    monkeypatch.setattr(wikijs_client.WikiJSClient, "upsert_page", fake_upsert_page)

    r = client.post(
        "/pages/upsert",
        headers={"X-Idempotency-Key": "manual-key-123"},
        json={"path": "AI/Tools/Ollama", "title": "Ollama", "content": "# Hello"},
    )
    assert r.status_code == 200
    assert r.json()["idempotency_key"] == "manual-key-123"


def test_upsert_accepts_large_plain_text_block(monkeypatch):
    async def fake_upsert_page(self, payload, idem_key):
        assert payload.content == payload.content_md
        return {"id": 321, "path": payload.path}

    from app import wikijs_client

    monkeypatch.setattr(wikijs_client.WikiJSClient, "upsert_page", fake_upsert_page)

    large_text = ("Line 1: plain text treated as markdown\\n" * 2000).strip()
    r = client.post(
        "/pages/upsert",
        json={
            "path": "AI/Tools/Large-Text",
            "title": "Large Text",
            "content": large_text,
            "description": "bulk text import",
        },
    )
    assert r.status_code == 200
    assert r.json()["id"] == 321


def test_upload_enforces_md_extension():
    r = client.post(
        "/pages/upload",
        data={"path": "AI/Tools/Ollama", "title": "Ollama"},
        files={"file": ("note.txt", b"# Hello", "text/plain")},
    )
    assert r.status_code == 400
    assert ".md extension" in r.json()["detail"]


def test_upload_enforces_utf8():
    r = client.post(
        "/pages/upload",
        data={"path": "AI/Tools/Ollama", "title": "Ollama"},
        files={"file": ("note.md", b"\xff\xfe\xfa", "text/markdown")},
    )
    assert r.status_code == 400
    assert "UTF-8" in r.json()["detail"]


def test_upload_parses_tags_json(monkeypatch):
    seen = {}

    async def fake_upsert_page(self, payload, idem_key):
        seen["tags"] = payload.tags
        return {"id": 11, "path": payload.path}

    from app import wikijs_client

    monkeypatch.setattr(wikijs_client.WikiJSClient, "upsert_page", fake_upsert_page)

    r = client.post(
        "/pages/upload",
        data={"path": "AI/Tools/Ollama", "title": "Ollama", "tags": '["a","b"]'},
        files={"file": ("note.md", b"# Hello", "text/markdown")},
    )
    assert r.status_code == 200
    assert seen["tags"] == ["a", "b"]


def test_upload_parses_tags_csv(monkeypatch):
    seen = {}

    async def fake_upsert_page(self, payload, idem_key):
        seen["tags"] = payload.tags
        return {"id": 12, "path": payload.path}

    from app import wikijs_client

    monkeypatch.setattr(wikijs_client.WikiJSClient, "upsert_page", fake_upsert_page)

    r = client.post(
        "/pages/upload",
        data={"path": "AI/Tools/Ollama", "title": "Ollama", "tags": "a, b ,c"},
        files={"file": ("note.md", b"# Hello", "text/markdown")},
    )
    assert r.status_code == 200
    assert seen["tags"] == ["a", "b", "c"]


def test_upload_idempotency_generation_is_deterministic(monkeypatch):
    seen = {}

    async def fake_upsert_page(self, payload, idem_key):
        seen["idem"] = idem_key
        return {"id": 13, "path": payload.path}

    from app import wikijs_client

    monkeypatch.setattr(wikijs_client.WikiJSClient, "upsert_page", fake_upsert_page)
    content = "# Hello"

    r = client.post(
        "/pages/upload",
        data={"path": "AI/Tools/Ollama", "title": "Ollama"},
        files={"file": ("note.md", content.encode("utf-8"), "text/markdown")},
    )
    assert r.status_code == 200
    expected = hashlib.sha256(b"AI/Tools/Ollama\x00Ollama\x00# Hello").hexdigest()
    assert seen["idem"] == expected
    assert r.json()["idempotency_key"] == expected


def test_upload_hits_internal_upsert(monkeypatch):
    seen = {}

    async def fake_upsert_page(self, payload, idem_key):
        seen["path"] = payload.path
        seen["title"] = payload.title
        seen["content_md"] = payload.content_md
        seen["is_private"] = payload.is_private
        seen["idem"] = idem_key
        return {"id": 14, "path": payload.path}

    from app import wikijs_client

    monkeypatch.setattr(wikijs_client.WikiJSClient, "upsert_page", fake_upsert_page)

    r = client.post(
        "/pages/upload",
        headers={"X-Idempotency-Key": "header-idem-1"},
        data={
            "path": "AI/Tools/Ollama",
            "title": "Ollama",
            "description": "desc",
            "is_private": "yes",
            "idempotency_key": "form-idem-ignored",
        },
        files={"file": ("note.md", b"# Hello", "text/markdown")},
    )
    assert r.status_code == 200
    assert seen["path"] == "AI/Tools/Ollama"
    assert seen["title"] == "Ollama"
    assert seen["content_md"] == "# Hello"
    assert seen["is_private"] is True
    assert seen["idem"] == "header-idem-1"
