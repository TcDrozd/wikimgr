from app.core.paths import normalize_path, normalize_segment


def test_normalize_path_examples():
    assert normalize_path("AI Tools") == "/ai-tools"
    assert normalize_path("/Homelab//GPU VM/Ollama/") == "/homelab/gpu-vm/ollama"
    assert normalize_path("  homelab / ai_tools  ") == "/homelab/ai-tools"
    assert normalize_path("/---Weird___Name---/") == "/weird-name"


def test_normalize_path_root_behavior():
    assert normalize_path("") == "/"
    assert normalize_path("///") == "/"
    assert normalize_path(" / / ") == "/"


def test_normalize_segment_special_chars():
    assert normalize_segment("  GPU__VM ++ beta  ") == "gpu-vm-beta"
