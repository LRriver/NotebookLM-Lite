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

    def _existing_collection(self, source_id: str) -> Any | None:
        try:
            return self._collection(source_id)
        except Exception as exc:
            if self._is_missing_collection_error(exc):
                return None
            raise

    @staticmethod
    def _is_missing_collection_error(exc: Exception) -> bool:
        if isinstance(exc, KeyError):
            return True
        message = str(exc).lower()
        missing_markers = (
            "not found",
            "not exist",
            "doesn't exist",
            "failed to resolve collection metadata",
        )
        return "collection" in message and any(marker in message for marker in missing_markers)

    @staticmethod
    def _collection_ids(collection: Any) -> list[str]:
        result = collection.get(include=[])
        ids = result.get("ids", [])
        if isinstance(ids, str):
            return [ids]
        return list(ids or [])

    def upsert_source_chunks(self, source_id: str, chunks: list[KnowledgeChunk]) -> None:
        existing_collection = self._existing_collection(source_id)
        if not chunks:
            if existing_collection is None:
                return
            existing_ids = self._collection_ids(existing_collection)
            if existing_ids:
                existing_collection.delete(ids=existing_ids)
                existing_collection.refresh_index()
            return

        dimension = self._first_embedding_dimension(chunks)
        embeddings: list[list[float]] = []
        metadatas: list[dict[str, Any]] = []
        for chunk in chunks:
            if chunk.source_id != source_id:
                raise ValueError("chunk.source_id must match source_id")
            if not chunk.embedding or len(chunk.embedding) != dimension:
                raise ValueError("All chunks must have same-dimension non-empty embeddings")
            embeddings.append(chunk.embedding)
            metadata = dict(chunk.metadata)
            metadata["source_id"] = chunk.source_id
            metadata["chunk_index"] = chunk.chunk_index
            metadata["payload"] = chunk.model_dump_json()
            metadatas.append(metadata)

        if existing_collection is not None:
            existing_dimension = getattr(existing_collection, "dimension", None)
            if existing_dimension is not None and existing_dimension != dimension:
                raise ValueError(
                    f"Existing SeekDB collection dimension {existing_dimension} "
                    f"does not match chunk embedding dimension {dimension}"
                )
            collection = existing_collection
            existing_ids = self._collection_ids(collection)
        else:
            collection = self._collection(source_id, dimension=dimension)
            existing_ids = []

        new_ids = [chunk.id for chunk in chunks]
        collection.upsert(
            ids=new_ids,
            documents=[chunk.content for chunk in chunks],
            metadatas=metadatas,
            embeddings=embeddings,
        )
        collection.refresh_index()
        new_id_set = set(new_ids)
        stale_ids = [chunk_id for chunk_id in existing_ids if chunk_id not in new_id_set]
        if stale_ids:
            collection.delete(ids=stale_ids)
            collection.refresh_index()

    def delete_source_chunks(self, source_id: str, chunk_ids: list[str]) -> None:
        if not chunk_ids:
            return
        try:
            collection = self._existing_collection(source_id)
            if collection is None:
                return
            collection.delete(ids=chunk_ids)
            collection.refresh_index()
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
            collection = self._collection(source_id)
            query_result = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                include=include,
            )
            results.extend(self._rows_to_results(query_result, score_mode="distance"))

        return sorted(results, key=lambda item: item["score"], reverse=True)[:top_k]

    def hybrid_search(
        self,
        query_text: str,
        query_embedding: list[float],
        source_ids: list[str],
        top_k: int,
    ) -> list[dict[str, Any]]:
        if not query_embedding:
            raise ValueError("Query embedding is required")
        query_text = query_text.strip()
        if not query_text:
            return self.search(query_embedding, source_ids, top_k)
        if top_k <= 0 or not source_ids:
            return []

        results: list[dict[str, Any]] = []
        include = ["documents", "metadatas", "distances"]
        n_results = max(top_k, 1)
        for source_id in source_ids:
            collection = self._collection(source_id)
            collection_hybrid_search = getattr(collection, "hybrid_search", None)
            if not callable(collection_hybrid_search):
                return self.search(query_embedding, source_ids, top_k)

            query_result = collection_hybrid_search(
                query={"where_document": {"$contains": query_text}, "n_results": n_results},
                knn={"query_embeddings": query_embedding, "n_results": n_results},
                rank={"rrf": {}},
                n_results=n_results,
                include=include,
            )
            results.extend(self._rows_to_results(query_result, score_mode="similarity"))

        return sorted(results, key=lambda item: item["score"], reverse=True)[:top_k]

    @staticmethod
    def _result_group(value: Any) -> list[Any]:
        if not value:
            return []
        first = value[0]
        return first if isinstance(first, list) else value

    def _rows_to_results(self, query_result: dict[str, Any], score_mode: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        ids = self._result_group(query_result.get("ids", []))
        distances = self._result_group(query_result.get("distances", []))
        metadatas = self._result_group(query_result.get("metadatas", []))
        for index, _chunk_id in enumerate(ids):
            try:
                metadata = metadatas[index]
                chunk = KnowledgeChunk.model_validate_json(metadata["payload"])
            except Exception as exc:
                raise ValueError("Malformed SeekDB chunk result payload") from exc
            raw_score = float(distances[index]) if index < len(distances) else 0.0
            if score_mode == "distance":
                score = 1.0 / (1.0 + max(raw_score, 0.0))
            else:
                score = raw_score
            results.append({"chunk": chunk, "score": score, "backend": "seekdb"})
        return results

    def status(self) -> dict[str, Any]:
        return {
            "vector_backend": "seekdb",
            "seekdb_path": str(self.path),
            "native_available": True,
        }
