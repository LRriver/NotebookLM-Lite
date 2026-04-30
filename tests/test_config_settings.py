from __future__ import annotations


def test_loads_yaml_model_profiles_without_using_local_config(sample_config_file):
    from backend.config import load_settings

    settings = load_settings(sample_config_file)

    assert settings.api.models.text_model.model == "test-text-model"
    assert settings.api.models.text_model.thinking.type == "disabled"
    assert settings.api.models.embedding_model.model == "test-embedding-model"
    assert settings.api.models.rerank_model.model == "test-rerank-model"
    assert settings.api.models.audio_model.base_url == "https://audio.example.test/v1"
    assert settings.api.models.audio_model.voice == "test-audio-model:alex"
    assert settings.api.models.audio_model.response_format == "mp3"
    assert settings.api.models.audio_model.stream is True
    assert settings.vector_store_type == "seekdb"
    assert settings.seekdb_path == "./data/test_seekdb.db"
    assert settings.chunk_size == 512
    assert settings.chunk_overlap == 64
    assert settings.chunking.provider == "chonkie"
    assert settings.chunking.tokenizer == "character"
    assert settings.upload_dir == "./uploads-test"
    assert settings.output_dir == "./output-test"


def test_default_settings_do_not_require_local_secrets(monkeypatch):
    from backend.config import get_settings

    monkeypatch.setenv("NOTEBOOKLM_CONFIG_FILE", "/tmp/notebooklm-lite-missing-config.yaml")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.api.models.text_model.api_key == ""
    assert settings.api.models.audio_model.api_key == ""
