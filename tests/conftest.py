from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


@pytest.fixture()
def sample_config_file(tmp_path: Path) -> Path:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
api:
  models:
    text_model:
      model: test-text-model
      base_url: https://example.test/v1
      api_key: test-text-key
      adapter: openai_chat
      thinking:
        type: disabled
    embedding_model:
      model: test-embedding-model
      base_url: https://example.test/v1
      api_key: test-embedding-key
      adapter: openai_embedding
    rerank_model:
      model: test-rerank-model
      base_url: https://rerank.example.test/v1
      api_key: test-rerank-key
      adapter: openai_rerank
    audio_model:
      model: test-audio-model
      base_url: https://audio.example.test/v1
      api_key: test-audio-key
      voice: test-audio-model:alex
      response_format: mp3
      stream: true
storage:
  vector_store_type: seekdb
  seekdb_path: ./data/test_seekdb.db
documents:
  chunk_size: 512
  chunk_overlap: 64
  chunking:
    provider: chonkie
    tokenizer: character
paths:
  upload_dir: ./uploads-test
  output_dir: ./output-test
""".strip(),
        encoding="utf-8",
    )
    return config_path


class FakeLiteLLMClient:
    def __init__(self) -> None:
        self.completion_calls: list[dict[str, Any]] = []
        self.embedding_calls: list[dict[str, Any]] = []
        self.responses: list[Any] = []
        self.embedding_response: list[float] = [0.1, 0.2, 0.3]

    def push_response(self, response: Any) -> None:
        self.responses.append(response)

    async def completion(self, **kwargs: Any) -> Any:
        self.completion_calls.append(kwargs)
        if self.responses:
            return self.responses.pop(0)
        return {"choices": [{"message": {"content": "ok"}}]}

    async def embedding(self, **kwargs: Any) -> Any:
        self.embedding_calls.append(kwargs)
        return {"data": [{"embedding": self.embedding_response}]}


class FakeRepository:
    def __init__(self) -> None:
        self.sources: dict[str, Any] = {}
        self.chunks: dict[str, list[Any]] = {}
        self.artifacts: dict[str, Any] = {}
        self.jobs: dict[str, Any] = {}

    async def save_source(self, source: Any) -> Any:
        self.sources[source.id] = source
        return source

    async def get_source(self, source_id: str) -> Any | None:
        return self.sources.get(source_id)

    async def list_sources(self) -> list[Any]:
        return list(self.sources.values())

    async def save_chunks(self, source_id: str, chunks: list[Any]) -> None:
        self.chunks[source_id] = chunks

    async def get_chunks(self, source_id: str) -> list[Any]:
        return self.chunks.get(source_id, [])

    async def delete_source(self, source_id: str) -> bool:
        self.sources.pop(source_id, None)
        self.chunks.pop(source_id, None)
        return True


@pytest.fixture()
def fake_litellm_client() -> FakeLiteLLMClient:
    return FakeLiteLLMClient()


@pytest.fixture()
def fake_repository() -> FakeRepository:
    return FakeRepository()
