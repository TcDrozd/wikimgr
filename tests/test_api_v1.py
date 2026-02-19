from fastapi.testclient import TestClient

from app.core.path_policy import enforce_path_policy, normalize_path
from app.main import app
from app.models import InventoryResponse, UpsertPageRequest


client = TestClient(app)


def test_canonical_ready_returns_503_with_reason_when_env_missing(monkeypatch):
    monkeypatch.delenv("WIKIJS_BASE_URL", raising=False)
    monkeypatch.delenv("WIKIJS_API_TOKEN", raising=False)

    r = client.get("/api/v1/ready")
    assert r.status_code == 503
    assert r.json() == {
        "ready": False,
        "reason": "WIKIJS_BASE_URL missing; WIKIJS_API_TOKEN missing",
    }


def test_canonical_auth_enforced_for_non_health_when_key_set(monkeypatch):
    monkeypatch.setenv("WIKIMGR_API_KEY", "secret")

    r = client.get("/api/v1/pages", params={"path": "ai/tools/ollama"})
    assert r.status_code == 401
    body = r.json()
    assert body["code"] == "unauthorized"
    assert body["message"] == "Invalid API key"


def test_legacy_auth_enforced_for_non_health_when_key_set(monkeypatch):
    monkeypatch.setenv("WIKIMGR_API_KEY", "secret")

    r = client.get("/wikimgr/get", params={"path": "ai/tools/ollama"})
    assert r.status_code == 401
    assert r.json() == {"detail": "Invalid API key"}


def test_canonical_upsert_accepts_both_idempotency_headers(monkeypatch):
    seen = {}

    async def fake_upsert_page(self, payload, idem_key):
        seen["idem"] = idem_key
        return {"id": 123, "path": payload.path}

    from app import wikijs_client

    monkeypatch.setattr(wikijs_client.WikiJSClient, "upsert_page", fake_upsert_page)

    r = client.post(
        "/api/v1/pages/upsert",
        headers={"X-Idempotency-Key": "canonical-1", "x_idempotency_key": "legacy-1"},
        json={"path": "AI/Tools/Ollama", "title": "Ollama", "content": "# Hello"},
    )
    assert r.status_code == 200
    assert seen["idem"] == "canonical-1"
    assert r.json()["idempotency_key"] == "canonical-1"


def test_path_policy_expands_short_segments():
    assert enforce_path_policy(normalize_path("ai/tools/ollama")) == "artificial-intelligence/tools/ollama"


def test_upsert_request_requires_content_or_content_md():
    try:
        UpsertPageRequest(path="x/y/z", title="No content")
        assert False, "Expected validation error"
    except Exception as e:
        assert "content" in str(e)


def test_legacy_deprecation_headers():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.headers["Deprecation"] == "true"
    assert r.headers["Link"] == '</api/v1/health>; rel="successor-version"'


def test_inventory_route_not_captured_by_id_route(monkeypatch):
    from app.routers import bulk as bulk_router

    monkeypatch.setattr(
        bulk_router,
        "inventory",
        lambda include_content=False: InventoryResponse(count=0, pages=[]),
    )

    r = client.get("/api/v1/pages/inventory")
    assert r.status_code == 200
    assert r.json()["count"] == 0


def test_non_int_page_id_returns_404_not_validation_error():
    r = client.get("/api/v1/pages/inventory-not-an-id")
    assert r.status_code == 404
