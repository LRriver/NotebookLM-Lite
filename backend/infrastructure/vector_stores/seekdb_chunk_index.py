"""Native SeekDB vector index for knowledge chunks."""

from __future__ import annotations

import hashlib
import importlib
import logging
from pathlib import Path
from typing import Any

from ...domain.source import KnowledgeChunk

logger = logging.getLogger(__name__)


class SeekDBUnavailableError(RuntimeError):
    """Raised when the native pyseekdb chunk index cannot be initialized."""


class SeekDBChunkIndex:
    """Source-scoped native pyseekdb chunk vector index."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        try:
            self.pyseekdb = importlib.import_module("pyseekdb")
            self.client = self.pyseekdb.Client(path=str(self.path))
        except Exception as exc:
            raise SeekDBUnavailableError("Native SeekDB chunk index is unavailable") from exc

    def collection_name(self, source_id: str) -> str:
        digest = hashlib.sha1(source_id.encode("utf-8")).hexdigest()[:16]
        return f"chunks_{digest}"

    def _first_embedding_dimension(self, chunks: list[KnowledgeChunk]) -> int:
        if not chunks:
            raise ValueError("At least one chunk with an embedding is required")
        embedding = chunks[0].embedding
        if not embedding:
            raise ValueError("Chunk embeddings must be non-empty")
        return len(embedding)

    def _collection(self, source_id: str, dimension: int | None = None) -> Any:
        name = self.collection_name(source_id)
        if dimension is None:
            return self.client.get_collection(name=name, embedding_function=None)
        configuration = self.pyseekdb.HNSWConfiguration(dimension=dimension)
        return self.client.get_or_create_collection(
            name=name,
            configuration=configuration,
            embedding_function=None,
        )

    def upsert_source_chunks(self, source_id: str, chunks: list[KnowledgeChunk]) -> None:
        dimension = self._first_embedding_dimension(chunks)
        embeddings: list[list[float]] = []
        metadatas: list[dict[str, Any]] = []
        for chunk in chunks:
            if not chunk.embedding or len(chunk.embedding) != dimension:
                raise ValueError("All chunks must have same-dimension non-empty embeddings")
            embeddings.append(chunk.embedding)
            metadata = dict(chunk.metadata)
            metadata.setdefault("source_id", chunk.source_id)
            metadata.setdefault("chunk_index", chunk.chunk_index)
            metadata["payload"] = chunk.model_dump_json()
            metadatas.append(metadata)

        collection = self._collection(source_id, dimension=dimension)
        collection.upsert(
            ids=[chunk.id for chunk in chunks],
            documents=[chunk.content for chunk in chunks],
            metadatas=metadatas,
            embeddings=embeddings,
        )
        collection.refresh_index()

    def delete_source_chunks(self, source_id: str, chunk_ids: list[str]) -> None:
        if not chunk_ids:
            return
        try:
            collection = self._collection(source_id)
            collection.delete(ids=chunk_ids)
        except Exception as exc:
            logger.warning("Failed to delete SeekDB chunks for source %s: %s", source_id, exc)

    def search(
        self,
        query_embedding: list[float],
        source_ids: list[str],
        top_k: int,
    ) -> list[dict[str, Any]]:
        if not query_embedding:
            raise ValueError("Query embedding is required")
        if top_k <= 0 or not source_ids:
            return []

        results: list[dict[str, Any]] = []
        include = ["documents", "metadatas", "distances"]
        for source_id in source_ids:
            try:
                collection = self._collection(source_id)
                query_result = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=top_k,
                    include=include,
                )
            except Exception as exc:
                logger.warning("Failed to query SeekDB chunks for source %s: %s", source_id, exc)
                continue

            ids = self._result_group(query_result.get("ids", []))
            distances = self._result_group(query_result.get("distances", []))
            metadatas = self._result_group(query_result.get("metadatas", []))
            for index, _chunk_id in enumerate(ids):
                try:
                    metadata = metadatas[index]
                    chunk = KnowledgeChunk.model_validate_json(metadata["payload"])
                    distance = distances[index] if index < len(distances) else 0.0
                    score = 1.0 / (1.0 + max(float(distance), 0.0))
                    results.append({"chunk": chunk, "score": score, "backend": "seekdb"})
                except Exception as exc:
                    logger.warning("Skipping malformed SeekDB chunk result: %s", exc)

        return sorted(results, key=lambda item: item["score"], reverse=True)[:top_k]

    @staticmethod
    def _result_group(value: Any) -> list[Any]:
        if not value:
            return []
        first = value[0]
        return first if isinstance(first, list) else value

    def status(self) -> dict[str, Any]:
        return {
            "vector_backend": "seekdb",
            "seekdb_path": str(self.path),
            "native_available": True,
        }
