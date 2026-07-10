from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes.config import router as config_router
from backend.config import Settings, _RUNTIME_MODEL_OVERRIDES, get_settings
from backend.dependencies import DependencyContainer


class FakeVectorStore:
    def __init__(self, status: dict) -> None:
        self.status = status

    async def get_stats(self) -> dict:
        return {
            "total_documents": 0,
            "total_chunks": 0,
            "backend": self.status["vector_backend"],
            "storage": self.status,
        }


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


def test_runtime_cache_reset_closes_cached_repository():
    class ClosableRepository:
        def __init__(self) -> None:
            self.close_calls = 0

        def close_sync(self) -> None:
            self.close_calls += 1

    repository = ClosableRepository()
    DependencyContainer._knowledge_repository = repository

    DependencyContainer.reset_runtime_caches()

    assert repository.close_calls == 1
    assert DependencyContainer._knowledge_repository is None


def test_force_new_repository_closes_old_repository_and_invalidates_dependents(monkeypatch):
    class ClosableRepository:
        def __init__(self, *_args, **_kwargs) -> None:
            self.close_calls = 0

        def close_sync(self) -> None:
            self.close_calls += 1

    old_repository = ClosableRepository()
    DependencyContainer._knowledge_repository = old_repository
    DependencyContainer._vector_store = object()
    DependencyContainer._slide_deck_service = object()
    monkeypatch.setattr(
        "backend.infrastructure.repositories.seekdb_repository.SeekDBRepository",
        ClosableRepository,
    )

    new_repository = DependencyContainer.get_knowledge_repository(
        settings=Settings(seekdb_allow_sqlite_fallback=True),
        force_new=True,
    )

    assert new_repository is not old_repository
    assert old_repository.close_calls == 1
    assert DependencyContainer._vector_store is None
    assert DependencyContainer._slide_deck_service is None
    DependencyContainer.reset_runtime_caches()


def test_runtime_config_exposes_actual_vector_backend(monkeypatch, sample_config_file):
    monkeypatch.setenv("NOTEBOOKLM_CONFIG_FILE", str(sample_config_file))
    monkeypatch.setattr(
        DependencyContainer,
        "get_vector_store",
        staticmethod(
            lambda settings=None: FakeVectorStore(
                {"vector_backend": "seekdb", "native_available": True}
            )
        ),
    )
    get_settings.cache_clear()
    DependencyContainer.reset_runtime_caches()

    app = FastAPI()
    app.include_router(config_router, prefix="/api")
    client = TestClient(app)

    response = client.get("/api/config")

    assert response.status_code == 200
    storage = response.json()["storage"]
    assert storage["configured_vector_store_type"] == "seekdb"
    assert storage["vector_store_type"] == "seekdb"
    assert storage["actual_vector_backend"] == "seekdb"
    assert storage["native_available"] is True

    get_settings.cache_clear()
    DependencyContainer.reset_runtime_caches()


def test_runtime_config_exposes_sqlite_fallback_status(monkeypatch, sample_config_file):
    monkeypatch.setenv("NOTEBOOKLM_CONFIG_FILE", str(sample_config_file))
    monkeypatch.setattr(
        DependencyContainer,
        "get_vector_store",
        staticmethod(
            lambda settings=None: FakeVectorStore(
                {"vector_backend": "sqlite_fallback", "native_available": False}
            )
        ),
    )

    app = FastAPI()
    app.include_router(config_router, prefix="/api")
    client = TestClient(app)

    response = client.get("/api/config")

    assert response.status_code == 200
    storage = response.json()["storage"]
    assert storage["configured_vector_store_type"] == "seekdb"
    assert storage["actual_vector_backend"] == "sqlite_fallback"
    assert storage["native_available"] is False


def test_health_exposes_actual_vector_backend(monkeypatch):
    from backend import main as backend_main

    def fake_get_vector_store():
        return FakeVectorStore({"vector_backend": "unavailable", "native_available": False})

    monkeypatch.setattr("backend.dependencies.get_vector_store", fake_get_vector_store)
    client = TestClient(backend_main.app)

    response = client.get("/health")

    assert response.status_code == 200
    storage = response.json()["storage"]
    assert storage["actual_vector_backend"] == "unavailable"
    assert storage["native_available"] is False
