from __future__ import annotations

from pathlib import Path

import pytest

from backend.core.services.chunking_service import ChunkingService
from backend.domain.source import KnowledgeChunk, KnowledgeSource, SourceKind, SourceStatus
from backend.infrastructure.repositories.seekdb_repository import SeekDBRepository
from backend.infrastructure.vector_stores.seekdb_vector_store import SeekDBVectorStore


def sqlite_fallback_repo(path: Path) -> SeekDBRepository:
    return SeekDBRepository(path, native_chunk_index=None, allow_sqlite_vector_fallback=True)


def test_chonkie_chunker_returns_offsets_and_counts():
    pytest.importorskip("chonkie")
    service = ChunkingService(
        chunk_size=24,
        chunk_overlap=4,
        provider="chonkie",
        tokenizer="character",
    )

    chunks = service.chunk("Alpha beta gamma delta epsilon zeta eta theta.")

    assert len(chunks) >= 2
    assert chunks[0].text.startswith("Alpha")
    assert chunks[0].start_index == 0
    assert chunks[0].end_index and chunks[0].end_index > chunks[0].start_index
    assert chunks[0].token_count and chunks[0].token_count > 0


@pytest.mark.asyncio
async def test_seekdb_vector_store_applies_reranker(tmp_path: Path):
    class ReverseReranker:
        async def rerank(self, query, results, top_k=5):
            reranked = list(reversed(results))[:top_k]
            for index, item in enumerate(reranked):
                item["score"] = 10 - index
            return reranked

    repo = sqlite_fallback_repo(tmp_path / "rerank.db")
    source = KnowledgeSource(
        id="source-1",
        kind=SourceKind.TEXT,
        title="Rerank source",
        status=SourceStatus.READY,
        chunk_count=2,
    )
    await repo.save_source(source)
    await repo.save_chunks(
        source.id,
        [
            KnowledgeChunk(
                id="chunk-a",
                source_id=source.id,
                content="alpha first chunk",
                chunk_index=0,
                metadata={"source_title": source.title},
            ),
            KnowledgeChunk(
                id="chunk-b",
                source_id=source.id,
                content="alpha second chunk",
                chunk_index=1,
                metadata={"source_title": source.title},
            ),
        ],
    )

    store = SeekDBVectorStore(repository=repo, rerank_provider=ReverseReranker())
    results = await store.search("alpha", top_k=2, doc_ids=[source.id])

    assert [item["id"] for item in results] == ["chunk-b", "chunk-a"]
    assert results[0]["score"] == 10


@pytest.mark.asyncio
async def test_seekdb_repository_uses_bm25_for_term_overlap_without_exact_phrase(tmp_path: Path):
    repo = sqlite_fallback_repo(tmp_path / "bm25.db")
    source = KnowledgeSource(
        id="source-bm25",
        kind=SourceKind.TEXT,
        title="HTTPS source",
        status=SourceStatus.READY,
        chunk_count=2,
    )
    await repo.save_source(source)
    await repo.save_chunks(
        source.id,
        [
            KnowledgeChunk(
                id="chunk-http",
                source_id=source.id,
                content="TLS handshake validates a certificate authority before encrypted traffic starts.",
                chunk_index=0,
                metadata={"source_title": source.title},
            ),
            KnowledgeChunk(
                id="chunk-noise",
                source_id=source.id,
                content="Vehicle charging schedule and cabin comfort settings.",
                chunk_index=1,
                metadata={"source_title": source.title},
            ),
        ],
    )

    results = await repo.search_chunks(
        "TLS certificate authority",
        source_ids=[source.id],
        top_k=2,
    )

    assert results
    assert results[0]["chunk"].id == "chunk-http"
    assert results[0]["score"] > 0
