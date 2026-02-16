from app.core.paths import parse_allowed_roots, preflight_analysis


def test_parse_allowed_roots_defaults():
    roots = parse_allowed_roots(None)
    assert roots == ["homelab", "projects", "ai", "personal", "community", "meta"]


def test_preflight_invalid_root_and_keyword_suggestions():
    result = preflight_analysis(
        "/infra/proxmox/cluster",
        allowed_roots=["homelab", "ai"],
        existing_paths=["homelab/proxmox/cluster", "ai/ollama/setup"],
    )

    assert result["normalized"] == "/infra/proxmox/cluster"
    assert result["is_valid_root"] is False
    assert result["root"] == "infra"
    assert "/homelab/proxmox/cluster" in result["suggestions"]


def test_preflight_valid_root():
    result = preflight_analysis(
        "AI Tools/Ollama",
        allowed_roots=["homelab", "ai"],
        existing_paths=["ai/ollama/setup", "homelab/gpu-vm/ollama"],
    )

    assert result["normalized"] == "/ai-tools/ollama"
    assert result["is_valid_root"] is False
    assert result["root"] == "ai-tools"

    valid = preflight_analysis(
        "/ai/ollama",
        allowed_roots=["homelab", "ai"],
        existing_paths=["ai/ollama/setup", "homelab/gpu-vm/ollama"],
    )
    assert valid["is_valid_root"] is True
    assert valid["root"] == "ai"
