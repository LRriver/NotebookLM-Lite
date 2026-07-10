from __future__ import annotations

from pathlib import Path

import pytest

from backend.core.services.chunking_service import ChunkingService
from backend.domain.source import KnowledgeChunk, KnowledgeSource, SourceKind, SourceStatus
from backend.infrastructure.repositories.seekdb_repository import SeekDBRepository
from backend.infrastructure.vector_stores.seekdb_vector_store import SeekDBVectorStore


def sqlite_fallback_repo(path: Path) -> SeekDBRepository:
    return SeekDBRepository(path, native_chunk_index=None, allow_sqlite_vector_fallback=True)


class RecordingNativeIndex:
    def __init__(self) -> None:
        self.upserts = []
        self.chunks_by_source = {}

    def upsert_source_chunks(self, source_id, chunks):
        self.upserts.append((source_id, chunks))
        self.chunks_by_source[source_id] = list(chunks)

    def get_source_chunks(self, source_id):
        return list(self.chunks_by_source.get(source_id, []))

    def search(self, query_embedding, source_ids, top_k):
        return []

    def status(self):
        return {"vector_backend": "seekdb", "native_available": True}


class FailingNativeIndex(RecordingNativeIndex):
    def upsert_source_chunks(self, source_id, chunks):
        super().upsert_source_chunks(source_id, chunks)
        raise RuntimeError("native write failed")


class HybridRecordingIndex:
    def __init__(self) -> None:
        self.calls = []
        self.upserts = []
        self.chunks_by_source = {}

    def upsert_source_chunks(self, source_id, chunks):
        self.upserts.append((source_id, chunks))
        self.chunks_by_source[source_id] = list(chunks)

    def get_source_chunks(self, source_id):
        return list(self.chunks_by_source.get(source_id, []))

    def hybrid_search(self, query_text, query_embedding, source_ids, top_k):
        self.calls.append((query_text, query_embedding, source_ids, top_k))
        return [
            {
                "chunk": KnowledgeChunk(
                    id="hybrid_chunk",
                    source_id=source_ids[0],
                    content="hybrid TLS result",
                    chunk_index=0,
                    embedding=[0.1, 0.2, 0.3],
                    metadata={"source_id": source_ids[0]},
                ),
                "score": 0.88,
                "backend": "seekdb",
            }
        ]

    def search(self, query_embedding, source_ids, top_k):
        raise AssertionError("hybrid_search should be preferred when query text is available")


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


@pytest.mark.asyncio
async def test_seekdb_repository_prefers_native_hybrid_search(tmp_path: Path):
    native_index = HybridRecordingIndex()
    repo = SeekDBRepository(
        tmp_path / "hybrid.db",
        native_chunk_index=native_index,
        allow_sqlite_vector_fallback=False,
    )
    source = KnowledgeSource(id="src-hybrid", kind=SourceKind.TEXT, title="Hybrid")
    await repo.save_source(source)
    await repo.save_chunks(
        source.id,
        [
            KnowledgeChunk(
                id="seed-hybrid",
                source_id=source.id,
                content="seed hybrid content",
                chunk_index=0,
                embedding=[0.1, 0.2, 0.3],
                metadata={"source_id": source.id},
            )
        ],
    )

    results = await repo.search_chunks(
        "TLS handshake",
        source_ids=[source.id],
        top_k=1,
        query_embedding=[0.1, 0.2, 0.3],
    )

    assert native_index.calls == [("TLS handshake", [0.1, 0.2, 0.3], [source.id], 1)]
    assert results[0]["chunk"].id == "hybrid_chunk"


@pytest.mark.asyncio
async def test_seekdb_repository_reranks_native_hybrid_results(tmp_path: Path):
    class TwoResultHybridIndex(HybridRecordingIndex):
        def hybrid_search(self, query_text, query_embedding, source_ids, top_k):
            self.calls.append((query_text, query_embedding, source_ids, top_k))
            return [
                {
                    "chunk": KnowledgeChunk(
                        id="hybrid-a",
                        source_id=source_ids[0],
                        content="first hybrid result",
                        chunk_index=0,
                        embedding=[0.1, 0.2, 0.3],
                        metadata={"source_id": source_ids[0]},
                    ),
                    "score": 0.9,
                    "backend": "seekdb",
                },
                {
                    "chunk": KnowledgeChunk(
                        id="hybrid-b",
                        source_id=source_ids[0],
                        content="second hybrid result",
                        chunk_index=1,
                        embedding=[0.2, 0.3, 0.4],
                        metadata={"source_id": source_ids[0]},
                    ),
                    "score": 0.8,
                    "backend": "seekdb",
                },
            ]

    class ReverseReranker:
        async def rerank(self, query, results, top_k=5):
            return list(reversed(results))[:top_k]

    native_index = TwoResultHybridIndex()
    repo = SeekDBRepository(
        tmp_path / "hybrid-rerank.db",
        native_chunk_index=native_index,
        allow_sqlite_vector_fallback=False,
    )
    source = KnowledgeSource(id="src-hybrid-rerank", kind=SourceKind.TEXT, title="Hybrid rerank")
    await repo.save_source(source)
    await repo.save_chunks(
        source.id,
        [
            KnowledgeChunk(
                id="seed-hybrid-rerank",
                source_id=source.id,
                content="seed hybrid rerank content",
                chunk_index=0,
                embedding=[0.1, 0.2, 0.3],
                metadata={"source_id": source.id},
            )
        ],
    )

    results = await repo.search_chunks(
        "TLS handshake",
        source_ids=[source.id],
        top_k=2,
        query_embedding=[0.1, 0.2, 0.3],
        rerank_provider=ReverseReranker(),
    )

    assert [item["chunk"].id for item in results] == ["hybrid-b", "hybrid-a"]


@pytest.mark.asyncio
async def test_seekdb_vector_store_add_chunks_does_not_leave_ready_source_on_strict_native_failure(
    tmp_path: Path,
):
    repo = SeekDBRepository(
        tmp_path / "strict-add.db",
        native_chunk_index=RecordingNativeIndex(),
        allow_sqlite_vector_fallback=False,
    )
    store = SeekDBVectorStore(repository=repo)

    with pytest.raises(RuntimeError, match="embeddings|native SeekDB"):
        await store.add_chunks(
            "doc-strict",
            [{"content": "strict native content", "metadata": {"filename": "strict.txt"}}],
        )

    assert await repo.get_source("doc-strict") is None
    assert await repo.get_chunks("doc-strict") == []


@pytest.mark.asyncio
async def test_seekdb_vector_store_add_chunks_rolls_back_new_source_when_native_save_fails(
    tmp_path: Path,
):
    repo = SeekDBRepository(
        tmp_path / "strict-valid-embeddings.db",
        native_chunk_index=FailingNativeIndex(),
        allow_sqlite_vector_fallback=False,
    )
    store = SeekDBVectorStore(repository=repo)

    with pytest.raises(RuntimeError, match="native write failed"):
        await store.add_chunks(
            "doc-native-fail",
            [{"content": "strict native content", "metadata": {"filename": "strict.txt"}}],
            embeddings=[[0.1, 0.2, 0.3]],
        )

    assert await repo.get_source("doc-native-fail") is None
    assert await repo.get_chunks("doc-native-fail") == []
