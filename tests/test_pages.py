import asyncio
import json
import os
import pytest
from fastapi.testclient import TestClient
from wikimgr.app.main import app

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
    from wikimgr.app import wikijs_client
    monkeypatch.setattr(wikijs_client.WikiJSClient, "upsert_page", fake_upsert_page)

    payload = {
        "path": "AI/Tools/Ollama",
        "title": "Ollama",
        "content_md": "# Hello",
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
    from wikimgr.app.wikijs_client import WikiError, WikiJSClient
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