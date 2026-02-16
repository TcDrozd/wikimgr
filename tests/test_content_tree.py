from fastapi.testclient import TestClient

from app.content_tree import build_tree
from app.main import app


client = TestClient(app)


def test_build_tree_ignores_empty_segments_and_sorts():
    paths = [
        "homelab/gpu-vm/ollama",
        "/homelab//network/",
        "ai/tools",
        "ai//agents",
        "",
    ]

    tree = build_tree(paths)

    assert list(tree.keys()) == ["ai", "homelab"]
    assert list(tree["ai"].keys()) == ["agents", "tools"]
    assert list(tree["homelab"].keys()) == ["gpu-vm", "network"]


def test_content_tree_endpoint(monkeypatch):
    fake_pages = [
        {"id": 1, "path": "homelab/gpu-vm", "title": "GPU VM"},
        {"id": 2, "path": "homelab/network", "title": "Network"},
        {"id": 3, "path": "ai/ollama", "title": "Ollama"},
    ]

    from app.routers import content as content_router

    monkeypatch.setattr(content_router, "list_pages", lambda limit=1000: fake_pages)

    r = client.get("/content/tree")

    assert r.status_code == 200
    body = r.json()
    assert body["stats"]["page_count"] == 3
    assert body["stats"]["root_counts"] == {"ai": 1, "homelab": 2}
    assert sorted(body["roots"].keys()) == ["ai", "homelab"]
    assert sorted(body["roots"]["homelab"].keys()) == ["gpu-vm", "network"]


def test_content_preflight_endpoint(monkeypatch):
    fake_pages = [
        {"id": 1, "path": "homelab/proxmox/cluster", "title": "Cluster"},
        {"id": 2, "path": "ai/ollama/setup", "title": "Ollama"},
    ]
    from app.routers import content as content_router

    monkeypatch.setattr(content_router, "list_pages", lambda limit=1000: fake_pages)
    monkeypatch.setenv("WIKIMGR_ALLOWED_ROOTS", "homelab,ai,projects")

    r = client.post("/content/preflight", json={"path": "/infra/proxmox/cluster"})

    assert r.status_code == 200
    body = r.json()
    assert body["normalized"] == "/infra/proxmox/cluster"
    assert body["is_valid_root"] is False
    assert body["root"] == "infra"
    assert "/homelab/proxmox/cluster" in body["suggestions"]
