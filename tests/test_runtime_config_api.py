from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes.config import router as config_router
from backend.config import Settings, _RUNTIME_MODEL_OVERRIDES, get_settings
from backend.dependencies import DependencyContainer


def test_runtime_config_is_redacted_and_preserves_blank_keys(monkeypatch, sample_config_file):
    monkeypatch.setenv("NOTEBOOKLM_CONFIG_FILE", str(sample_config_file))
    _RUNTIME_MODEL_OVERRIDES.clear()
    get_settings.cache_clear()
    DependencyContainer.reset_runtime_caches()

    app = FastAPI()
    app.include_router(config_router, prefix="/api")
    client = TestClient(app)

    loaded = client.get("/api/config")
    assert loaded.status_code == 200
    payload = loaded.json()
    assert payload["models"]["text_model"]["api_key_set"] is True
    assert "api_key" not in payload["models"]["text_model"]
    assert payload["models"]["image_model"]["api_key_set"] is True
    assert payload["models"]["edit_model"]["api_key_set"] is True
    assert "api_key" not in payload["models"]["image_model"]
    assert "api_key" not in payload["models"]["edit_model"]

    saved = client.post(
        "/api/config",
        json={
            "models": {
                "text_model": {
                    "model": "new-text-model",
                    "base_url": "https://new.example.test/v1",
                    "api_key": "",
                    "adapter": "openai_chat",
                }
            }
        },
    )
    assert saved.status_code == 200
    updated = saved.json()
    assert updated["models"]["text_model"]["model"] == "new-text-model"
    assert updated["models"]["text_model"]["api_key_set"] is True

    _RUNTIME_MODEL_OVERRIDES.clear()
    get_settings.cache_clear()
    DependencyContainer.reset_runtime_caches()


def test_runtime_cache_reset_recreates_knowledge_repository_with_new_storage_settings(tmp_path):
    DependencyContainer.reset_runtime_caches()
    first_settings = Settings(
        seekdb_path=str(tmp_path / "first.db"),
        seekdb_allow_sqlite_fallback=True,
    )
    first_repo = DependencyContainer.get_knowledge_repository(settings=first_settings)

    DependencyContainer.reset_runtime_caches()
    second_settings = Settings(
        seekdb_path=str(tmp_path / "second.db"),
        seekdb_allow_sqlite_fallback=False,
    )
    second_repo = DependencyContainer.get_knowledge_repository(settings=second_settings)

    try:
        assert second_repo is not first_repo
        assert second_repo.db_path == tmp_path / "second.db"
        assert second_repo.allow_sqlite_vector_fallback is False
    finally:
        DependencyContainer.reset_runtime_caches()
