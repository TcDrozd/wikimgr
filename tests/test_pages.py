import pytest
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
