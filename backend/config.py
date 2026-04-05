"""Application configuration.

Settings support environment variables and a local YAML file. The committed
``config_example.yaml`` documents the YAML shape; local ``config.yaml`` may
contain secrets and must remain ignored.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Optional

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ThinkingConfig(BaseModel):
    """Optional model thinking controls passed to compatible providers."""

    type: Literal["enabled", "disabled"] = "enabled"


class ModelProfile(BaseModel):
    """Reusable model profile loaded from config.yaml."""

    model: str = ""
    base_url: str = ""
    api_key: str = ""
    adapter: str = "openai_chat"
    thinking: Optional[ThinkingConfig] = None
    voice: Optional[str] = None
    response_format: str = "mp3"
    stream: bool = True


class ModelProfiles(BaseModel):
    """Configured model roles."""

    text_model: ModelProfile = Field(default_factory=ModelProfile)
    embedding_model: ModelProfile = Field(
        default_factory=lambda: ModelProfile(
            model="text-embedding-3-small",
            adapter="openai_embedding",
        )
    )
    rerank_model: ModelProfile = Field(default_factory=ModelProfile)
    audio_model: ModelProfile = Field(default_factory=ModelProfile)
    image_model: ModelProfile = Field(default_factory=ModelProfile)
    edit_model: ModelProfile = Field(default_factory=ModelProfile)


class ApiConfig(BaseModel):
    """API model configuration."""

    models: ModelProfiles = Field(default_factory=ModelProfiles)


class ChunkingConfig(BaseModel):
    """Chunking controls."""

    provider: Literal["chonkie", "simple"] = "chonkie"
    tokenizer: str = "character"


_RUNTIME_MODEL_OVERRIDES: dict[str, Any] = {}


class Settings(BaseSettings):
    """应用配置"""
    
    # 应用设置
    app_name: str = "NotebookLM-Lite"
    app_version: str = "2.0.0"
    debug: bool = False
    
    # 服务器设置
    host: str = "0.0.0.0"
    port: int = 8000
    
    # 向量数据库设置
    vector_store_type: Literal["chroma", "faiss", "seekdb"] = "seekdb"
    chroma_persist_dir: str = "./data/chroma"
    seekdb_path: str = "./data/seekdb.db"
    
    # 嵌入模型设置 (OpenAI API)
    embedding_model: str = "text-embedding-3-small"
    
    # 文件上传设置
    upload_dir: str = "./uploads"
    output_dir: str = "./output"
    max_upload_size_mb: int = 50
    
    # 文档处理设置
    chunk_size: int = 1000
    chunk_overlap: int = 200
    
    # 默认 LLM 设置
    default_llm_provider: Literal["openai", "google", "litellm"] = "litellm"
    default_llm_model: str = "gpt-4o"
    
    # 默认 TTS 设置
    default_tts_provider: Literal["openai", "dashscope"] = "openai"
    
    # 播客设置
    chars_per_minute: int = 200  # 中文语速
    max_podcast_iterations: int = 5  # 最大迭代次数
    api: ApiConfig = Field(default_factory=ApiConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config file must contain a YAML mapping: {path}")
    return data


def _flatten_config(data: dict[str, Any]) -> dict[str, Any]:
    """Map grouped YAML sections to Settings fields while preserving nesting."""

    flattened: dict[str, Any] = {}

    if api := data.get("api"):
        flattened["api"] = api

    storage = data.get("storage") or {}
    if isinstance(storage, dict):
        for key in ("vector_store_type", "chroma_persist_dir", "seekdb_path"):
            if key in storage:
                flattened[key] = storage[key]

    documents = data.get("documents") or {}
    if isinstance(documents, dict):
        for key in ("chunk_size", "chunk_overlap", "max_upload_size_mb"):
            if key in documents:
                flattened[key] = documents[key]
        if chunking := documents.get("chunking"):
            flattened["chunking"] = chunking

    paths = data.get("paths") or {}
    if isinstance(paths, dict):
        for key in ("upload_dir", "output_dir"):
            if key in paths:
                flattened[key] = paths[key]

    server = data.get("server") or {}
    if isinstance(server, dict):
        for key in ("host", "port", "debug"):
            if key in server:
                flattened[key] = server[key]

    podcast = data.get("podcast") or {}
    if isinstance(podcast, dict):
        for key in ("chars_per_minute", "max_podcast_iterations"):
            if key in podcast:
                flattened[key] = podcast[key]

    # Allow direct Settings fields as a fallback for simple deployments.
    for key, value in data.items():
        if key not in {"api", "storage", "documents", "paths", "server", "podcast"}:
            flattened.setdefault(key, value)

    return flattened


def load_settings(config_path: str | os.PathLike[str] | None = None) -> Settings:
    """Load settings from an optional YAML file plus environment variables."""

    path: Optional[Path]
    if config_path is not None:
        path = Path(config_path)
    elif env_path := os.getenv("NOTEBOOKLM_CONFIG_FILE"):
        path = Path(env_path)
    else:
        path = Path("config.yaml")

    yaml_values = _flatten_config(_read_yaml(path)) if path else {}
    settings = Settings(**yaml_values)
    if _RUNTIME_MODEL_OVERRIDES:
        model_values = settings.api.models.model_dump()
        for name, profile in _RUNTIME_MODEL_OVERRIDES.items():
            if isinstance(profile, dict) and name in model_values:
                model_values[name] = {**model_values[name], **profile}
        settings.api.models = ModelProfiles.model_validate(model_values)

    text_model = settings.api.models.text_model
    embedding_model = settings.api.models.embedding_model
    if text_model.model:
        settings.default_llm_model = text_model.model
    if embedding_model.model:
        settings.embedding_model = embedding_model.model

    return settings


def update_runtime_model_profiles(model_profiles: dict[str, Any]) -> Settings:
    """Update in-memory model profiles from the frontend settings panel."""

    allowed = set(ModelProfiles.model_fields)
    for name, value in model_profiles.items():
        if name in allowed and isinstance(value, dict):
            cleaned = {
                key: item
                for key, item in value.items()
                if not (key == "api_key" and item == "")
            }
            _RUNTIME_MODEL_OVERRIDES[name] = {
                **_RUNTIME_MODEL_OVERRIDES.get(name, {}),
                **cleaned,
            }
    get_settings.cache_clear()
    return get_settings()


@lru_cache()
def get_settings() -> Settings:
    """获取应用配置（单例）"""
    return load_settings()
