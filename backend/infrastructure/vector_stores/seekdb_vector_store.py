"""Compatibility vector-store adapter over the knowledge repository."""

from __future__ import annotations

from typing import Any, Optional

from ...core.interfaces.knowledge_repository import KnowledgeRepositoryInterface
from ...core.interfaces.vector_store import VectorStoreInterface
from ...domain.source import KnowledgeChunk, KnowledgeSource, SourceKind, SourceStatus


class SeekDBVectorStore(VectorStoreInterface):
    """Bridge old document/RAG paths to the new source repository."""

    def __init__(
        self,
        repository: KnowledgeRepositoryInterface,
        embedding_provider=None,
        rerank_provider=None,
    ) -> None:
        self.repository = repository
        self.embedding_provider = embedding_provider
        self.rerank_provider = rerank_provider

    async def add_chunks(
        self,
        doc_id: str,
        chunks: list[dict[str, Any]],
        embeddings: Optional[list[list[float]]] = None,
    ) -> None:
        self._validate_strict_native_write(chunks, embeddings)

        existing = await self.repository.get_source(doc_id)
        created_source = existing is None
        if existing is None:
            existing = KnowledgeSource(
                id=doc_id,
                kind=SourceKind.FILE,
                title=chunks[0].get("metadata", {}).get("filename", doc_id) if chunks else doc_id,
                status=SourceStatus.READY,
            )
            await self.repository.save_source(existing)

        knowledge_chunks = []
        for index, item in enumerate(chunks):
            metadata = item.get("metadata", {})
            knowledge_chunks.append(
                KnowledgeChunk(
                    id=f"{doc_id}_chunk_{index}",
                    source_id=doc_id,
                    content=item.get("content", ""),
                    chunk_index=index,
                    embedding=embeddings[index] if embeddings and index < len(embeddings) else None,
                    metadata={"source_id": doc_id, "chunk_index": index, **metadata},
                )
            )
        try:
            await self.repository.save_chunks(doc_id, knowledge_chunks)
        except Exception:
            if created_source:
                await self._rollback_created_source(doc_id)
            raise

    def _validate_strict_native_write(
        self,
        chunks: list[dict[str, Any]],
        embeddings: Optional[list[list[float]]],
    ) -> None:
        if getattr(self.repository, "allow_sqlite_vector_fallback", True):
            return
        if getattr(self.repository, "native_chunk_index", None) is None:
            raise RuntimeError(
                "native SeekDB vector index is unavailable; "
                "enable seekdb_allow_sqlite_fallback for SQLite fallback"
            )
        if not chunks:
            return

        provided_embeddings = embeddings or []
        has_missing_embedding = len(provided_embeddings) < len(chunks) or any(
            embedding is None or len(embedding) == 0 for embedding in provided_embeddings[: len(chunks)]
        )
        if has_missing_embedding:
            raise RuntimeError("native SeekDB chunk writes require embeddings for all chunks")

    async def _rollback_created_source(self, doc_id: str) -> None:
        rollback_metadata = getattr(self.repository, "delete_source_metadata_only", None)
        if rollback_metadata is not None:
            await rollback_metadata(doc_id)
            return
        await self.repository.delete_source(doc_id)

    async def search(
        self,
        query: str,
        top_k: int = 5,
        doc_ids: Optional[list[str]] = None,
        **kwargs,
    ) -> list[dict[str, Any]]:
        query_embedding = None
        if self.embedding_provider:
            query_embedding = await self.embedding_provider.embed(query)
        results = await self.repository.search_chunks(
            query,
            source_ids=doc_ids,
            top_k=top_k,
            query_embedding=query_embedding,
            rerank_provider=self.rerank_provider,
        )
        return [
            {
                "id": item["chunk"].id,
                "content": item["chunk"].content,
                "metadata": item["chunk"].metadata,
                "score": item["score"],
            }
            for item in results
        ]

    async def delete_document(self, doc_id: str) -> bool:
        return await self.repository.delete_source(doc_id)

    async def get_document_chunks(self, doc_id: str) -> list[dict[str, Any]]:
        chunks = await self.repository.get_chunks(doc_id)
        return [
            {
                "id": chunk.id,
                "content": chunk.content,
                "metadata": chunk.metadata,
                "score": 1.0,
            }
            for chunk in chunks
        ]

    async def get_stats(self) -> dict[str, Any]:
        sources = await self.repository.list_sources()
        chunk_count = sum(source.chunk_count for source in sources)
        return {"total_documents": len(sources), "total_chunks": chunk_count, "backend": "seekdb"}
