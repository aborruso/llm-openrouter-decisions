import json

import pytest

CATALOG = {
    "data": [
        {
            "id": "typesafe/jev-1.14",
            "architecture": {"input_modalities": ["text", "image"]},
        },
        {
            "id": "microsoft/microsoft-decision-1",
            "architecture": {"input_modalities": ["text"]},
        },
    ]
}


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    user_dir = tmp_path / "llm"
    user_dir.mkdir()
    (user_dir / "openrouter_decisions_models.json").write_text(json.dumps(CATALOG))
    monkeypatch.setenv("LLM_USER_PATH", str(user_dir))
    monkeypatch.setenv("OPENROUTER_KEY", "test-openrouter-secret")
