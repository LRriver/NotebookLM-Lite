from __future__ import annotations

import logging
from pathlib import Path
import sqlite3
from types import ModuleType, SimpleNamespace
import sys
import threading

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes.sources import router as sources_router
from backend.core.services.source_service import SourceService
from backend.config import Settings, get_settings
from backend.domain.source import KnowledgeChunk, KnowledgeSource, SourceKind
from backend.dependencies import get_source_service
from backend.infrastructure.parsers.docling_parser import DoclingParser
from backend.infrastructure.repositories.seekdb_repository import SeekDBRepository


def test_repository_migrates_legacy_chunk_schema_with_vector_state(tmp_path: Path):
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE sources (
            id TEXT PRIMARY KEY, status TEXT NOT NULL, payload TEXT NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE chunks (
            id TEXT PRIMARY KEY, source_id TEXT NOT NULL, content TEXT NOT NULL,
            chunk_index INTEGER NOT NULL, embedding TEXT, payload TEXT NOT NULL
        );
        """
    )
    conn.close()

    repo = SeekDBRepository(
        db_path,
        native_chunk_index=RecordingNativeIndex(),
        allow_sqlite_vector_fallback=False,
    )

    columns = {row["name"] for row in repo._conn.execute("PRAGMA table_info(chunks)").fetchall()}
    assert "vector_state" in columns
    state_columns = {
        row["name"] for row in repo._conn.execute("PRAGMA table_info(chunk_index_state)").fetchall()
    }
    assert "embedding_profile" in state_columns


@pytest.mark.asyncio
async def test_backfill_recognizes_pre_vector_state_strict_native_rows(tmp_path: Path):
    db_path = tmp_path / "legacy-strict.db"
    source = KnowledgeSource(id="src-legacy-strict", kind=SourceKind.TEXT, title="Legacy strict")
    native_chunk = KnowledgeChunk(
        id="chunk-legacy-strict",
        source_id=source.id,
        content="already stored natively",
        chunk_index=0,
        embedding=[0.1, 0.2, 0.3],
        metadata={"source_id": source.id},
    )
    sqlite_chunk = native_chunk.model_copy(update={"embedding": None})
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE sources (
            id TEXT PRIMARY KEY, status TEXT NOT NULL, payload TEXT NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE chunks (
            id TEXT PRIMARY KEY, source_id TEXT NOT NULL, content TEXT NOT NULL,
            chunk_index INTEGER NOT NULL, embedding TEXT, payload TEXT NOT NULL
        );
        """
    )
    conn.execute(
        "INSERT INTO sources VALUES (?, ?, ?, ?, ?)",
        (
            source.id,
            source.status.value,
            source.model_dump_json(),
            source.created_at.isoformat(),
            source.updated_at.isoformat(),
        ),
    )
    conn.execute(
        "INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?)",
        (
            sqlite_chunk.id,
            sqlite_chunk.source_id,
            sqlite_chunk.content,
            sqlite_chunk.chunk_index,
            None,
            sqlite_chunk.model_dump_json(),
        ),
    )
    conn.commit()
    conn.close()
    native_index = RecordingNativeIndex()
    native_index.chunks_by_source[source.id] = [native_chunk]
    repo = SeekDBRepository(db_path, native_chunk_index=native_index, allow_sqlite_vector_fallback=False)

    written = await repo.backfill_native_chunks()

    assert written == 0
    assert native_index.upserts == []
    assert [chunk.id for chunk in native_index.get_source_chunks(source.id)] == [native_chunk.id]
    state = repo._conn.execute(
        "SELECT vector_state FROM chunks WHERE source_id = ?",
        (source.id,),
    ).fetchone()["vector_state"]
    assert state == "seekdb"


class RecordingNativeIndex:
    def __init__(self) -> None:
        self.upserts = []
        self.deletes = []
        self.searches = []
        self.text_searches = []
        self.chunks_by_source = {}
        self.get_source_calls = []

    def upsert_source_chunks(self, source_id, chunks):
        self.upserts.append((source_id, chunks))
        self.chunks_by_source[source_id] = list(chunks)

    def get_source_chunks(self, source_id):
        self.get_source_calls.append(source_id)
        return list(self.chunks_by_source.get(source_id, []))

    def delete_source_chunks(self, source_id, chunk_ids):
        self.deletes.append((source_id, chunk_ids))

    def search(self, query_embedding, source_ids, top_k):
        self.searches.append((query_embedding, source_ids, top_k))
        return [
            {
                "chunk": KnowledgeChunk(
                    id="native_chunk",
                    source_id=source_ids[0],
                    content="native search result",
                    chunk_index=0,
                    embedding=[0.1, 0.2, 0.3],
                    metadata={"source_id": source_ids[0]},
                ),
                "score": 0.99,
                "backend": "seekdb",
            }
        ]

    def text_search(self, query_text, source_ids, top_k):
        self.text_searches.append((query_text, source_ids, top_k))
        return [
            {
                "chunk": KnowledgeChunk(
                    id="native_text_chunk",
                    source_id=source_ids[0],
                    content="native fulltext result",
                    chunk_index=0,
                    embedding=[0.1, 0.2, 0.3],
                    metadata={"source_id": source_ids[0]},
                ),
                "score": 0.97,
                "backend": "seekdb",
            }
        ]

    def status(self):
        return {"vector_backend": "seekdb", "native_available": True}


class StaleAwareNativeIndex(RecordingNativeIndex):
    def __init__(self) -> None:
        super().__init__()
        self.cleared_sources: set[str] = set()

    def upsert_source_chunks(self, source_id, chunks):
        super().upsert_source_chunks(source_id, chunks)
        if chunks == []:
            self.cleared_sources.add(source_id)

    def search(self, query_embedding, source_ids, top_k):
        self.searches.append((query_embedding, source_ids, top_k))
        if source_ids[0] in self.cleared_sources:
            return []
        return [
            {
                "chunk": KnowledgeChunk(
                    id="stale_native_chunk",
                    source_id=source_ids[0],
                    content="stale native search result",
                    chunk_index=0,
                    embedding=[0.1, 0.2, 0.3],
                    metadata={"source_id": source_ids[0]},
                ),
                "score": 0.99,
                "backend": "seekdb",
            }
        ]


class FailingNativeIndex(RecordingNativeIndex):
    def __init__(self, message: str = "native write failed") -> None:
        super().__init__()
        self.message = message

    def upsert_source_chunks(self, source_id, chunks):
        self.upserts.append((source_id, chunks))
        raise RuntimeError(self.message)


class ProbeFailingNativeIndex(RecordingNativeIndex):
    def probe(self):
        raise RuntimeError("native probe failed")


class FailOnceNativeIndex(RecordingNativeIndex):
    def __init__(self, source_id: str, existing_chunks: list[KnowledgeChunk]) -> None:
        super().__init__()
        self.chunks_by_source[source_id] = list(existing_chunks)
        self.fail_next_upsert = True

    def upsert_source_chunks(self, source_id, chunks):
        if self.fail_next_upsert:
            self.fail_next_upsert = False
            self.chunks_by_source[source_id] = list(chunks)
            raise RuntimeError("native write failed")
        super().upsert_source_chunks(source_id, chunks)


class PartialWriteAndRestoreFailingNativeIndex(RecordingNativeIndex):
    def __init__(self) -> None:
        super().__init__()
        self.failures_remaining = 0

    def upsert_source_chunks(self, source_id, chunks):
        if self.failures_remaining == 2:
            self.failures_remaining -= 1
            self.chunks_by_source[source_id] = list(chunks)
            raise RuntimeError("partial native write")
        if self.failures_remaining == 1:
            self.failures_remaining -= 1
            raise RuntimeError("native restore failed")
        super().upsert_source_chunks(source_id, chunks)


class DimensionCheckingNativeIndex(RecordingNativeIndex):
    def search(self, query_embedding, source_ids, top_k):
        bad_source_ids = [
            source_id
            for source_id, chunks in self.upserts
            if source_id in source_ids
            and chunks
            and len(chunks[0].embedding or []) != len(query_embedding)
        ]
        if bad_source_ids:
            raise ValueError(f"dimension mismatch for {bad_source_ids}")
        return super().search(query_embedding, source_ids, top_k)


class QueryFailingNativeIndex(RecordingNativeIndex):
    def search(self, query_embedding, source_ids, top_k):
        self.searches.append((query_embedding, source_ids, top_k))
        raise KeyError("collection not found")


class DeterministicEmbeddingProvider:
    def __init__(self) -> None:
        self.calls = []

    async def embed(self, content):
        self.calls.append(content)
        if isinstance(content, str):
            return [0.1, 0.2, 0.3]
        return [[0.1, 0.2, 0.3] for _ in content]


@pytest.mark.asyncio
async def test_repository_uses_seekdb_native_index_for_chunk_save_and_search(tmp_path: Path, caplog):
    native_index = RecordingNativeIndex()
    repo = SeekDBRepository(
        tmp_path / "knowledge.db",
        native_chunk_index=native_index,
        allow_sqlite_vector_fallback=False,
    )
    source = KnowledgeSource(id="src-native", kind=SourceKind.TEXT, title="Native")
    await repo.save_source(source)
    await repo.save_chunks(
        source.id,
        [
            KnowledgeChunk(
                id="chunk-native",
                source_id=source.id,
                content="native indexed content",
                chunk_index=0,
                embedding=[0.1, 0.2, 0.3],
                metadata={"source_id": source.id},
            )
        ],
    )

    with caplog.at_level(logging.WARNING):
        results = await repo.search_chunks(
            "native indexed",
            source_ids=[source.id],
            top_k=1,
            query_embedding=[0.1, 0.2, 0.3],
        )

    assert native_index.upserts[0][0] == source.id
    assert native_index.searches == [([0.1, 0.2, 0.3], [source.id], 1)]
    assert results[0]["chunk"].id == "native_chunk"
    assert "Skipping optional pyseekdb chunk mirror" not in caplog.text


@pytest.mark.asyncio
async def test_repository_search_automatically_migrates_legacy_sqlite_vectors(tmp_path: Path):
    db_path = tmp_path / "knowledge.db"
    source = KnowledgeSource(id="src-auto-migrate", kind=SourceKind.TEXT, title="Auto migrate")
    chunk = KnowledgeChunk(
        id="chunk-auto-migrate",
        source_id=source.id,
        content="legacy vector should migrate before search",
        chunk_index=0,
        embedding=[0.1, 0.2, 0.3],
        metadata={"source_id": source.id},
    )
    legacy_repo = SeekDBRepository(db_path, native_chunk_index=None, allow_sqlite_vector_fallback=True)
    await legacy_repo.save_source(source)
    await legacy_repo.save_chunks(source.id, [chunk])
    await legacy_repo.close()

    native_index = RecordingNativeIndex()
    repo = SeekDBRepository(db_path, native_chunk_index=native_index, allow_sqlite_vector_fallback=False)

    results = await repo.search_chunks(
        "legacy vector",
        source_ids=[source.id],
        top_k=1,
        query_embedding=[0.1, 0.2, 0.3],
    )

    assert native_index.upserts == [(source.id, [chunk])]
    assert native_index.searches == [([0.1, 0.2, 0.3], [source.id], 1)]
    assert results[0]["backend"] == "seekdb"
    row = repo._conn.execute(
        "SELECT embedding, vector_state FROM chunks WHERE source_id = ?",
        (source.id,),
    ).fetchone()
    assert row["embedding"] is None
    assert row["vector_state"] == "seekdb"


@pytest.mark.asyncio
async def test_pending_seekdb_replace_is_recovered_after_process_interruption(
    tmp_path: Path,
    monkeypatch,
):
    db_path = tmp_path / "knowledge.db"
    source = KnowledgeSource(id="src-crash-recovery", kind=SourceKind.TEXT, title="Crash recovery")
    chunk = KnowledgeChunk(
        id="chunk-crash-recovery",
        source_id=source.id,
        content="durable pending replacement",
        chunk_index=0,
        embedding=[0.1, 0.2, 0.3],
        metadata={"source_id": source.id},
    )
    native_index = RecordingNativeIndex()
    repo = SeekDBRepository(db_path, native_chunk_index=native_index, allow_sqlite_vector_fallback=False)
    await repo.save_source(source)

    def interrupt_after_native_write(*_args, **_kwargs):
        raise SystemExit("simulated process interruption")

    monkeypatch.setattr(repo, "_finalize_chunk_replace", interrupt_after_native_write)
    with pytest.raises(SystemExit, match="process interruption"):
        await repo.save_chunks(source.id, [chunk])

    pending = repo._conn.execute(
        "SELECT operation FROM chunk_sync_operations WHERE source_id = ?",
        (source.id,),
    ).fetchone()
    assert pending["operation"] == "replace"
    assert repo._get_sqlite_chunks_sync(source.id) == []
    await repo.close()

    recovered = SeekDBRepository(
        db_path,
        native_chunk_index=native_index,
        allow_sqlite_vector_fallback=False,
    )
    await recovered.initialize_storage()

    assert [item.id for item in await recovered.get_chunks(source.id)] == [chunk.id]
    assert [item.id for item in recovered._get_sqlite_chunks_sync(source.id)] == [chunk.id]
    assert recovered._conn.execute("SELECT COUNT(*) FROM chunk_sync_operations").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_failed_native_compensation_keeps_a_durable_restore_operation(tmp_path: Path):
    db_path = tmp_path / "knowledge.db"
    source = KnowledgeSource(id="src-restore-retry", kind=SourceKind.TEXT, title="Restore retry")
    old_chunk = KnowledgeChunk(
        id="chunk-old-restore-retry",
        source_id=source.id,
        content="old canonical content",
        chunk_index=0,
        embedding=[0.4, 0.5, 0.6],
        metadata={"source_id": source.id},
    )
    new_chunk = KnowledgeChunk(
        id="chunk-new-restore-retry",
        source_id=source.id,
        content="partially written content",
        chunk_index=0,
        embedding=[0.1, 0.2, 0.3],
        metadata={"source_id": source.id},
    )
    native_index = PartialWriteAndRestoreFailingNativeIndex()
    repo = SeekDBRepository(db_path, native_chunk_index=native_index, allow_sqlite_vector_fallback=False)
    await repo.save_source(source)
    await repo.save_chunks(source.id, [old_chunk])
    native_index.failures_remaining = 2

    with pytest.raises(RuntimeError, match="partial native write"):
        await repo.save_chunks(source.id, [new_chunk])

    pending = repo._conn.execute(
        "SELECT operation FROM chunk_sync_operations WHERE source_id = ?",
        (source.id,),
    ).fetchone()
    assert pending["operation"] == "native_restore"
    assert [chunk.id for chunk in native_index.get_source_chunks(source.id)] == [new_chunk.id]
    assert [chunk.id for chunk in repo._get_sqlite_chunks_sync(source.id)] == [old_chunk.id]
    await repo.close()

    recovered = SeekDBRepository(
        db_path,
        native_chunk_index=native_index,
        allow_sqlite_vector_fallback=False,
    )
    await recovered.initialize_storage()

    assert [chunk.id for chunk in native_index.get_source_chunks(source.id)] == [old_chunk.id]
    assert [chunk.id for chunk in recovered._get_sqlite_chunks_sync(source.id)] == [old_chunk.id]
    assert recovered._conn.execute("SELECT COUNT(*) FROM chunk_sync_operations").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_pending_seekdb_delete_is_recovered_after_process_interruption(
    tmp_path: Path,
    monkeypatch,
):
    db_path = tmp_path / "knowledge.db"
    source = KnowledgeSource(id="src-delete-crash", kind=SourceKind.TEXT, title="Delete crash")
    chunk = KnowledgeChunk(
        id="chunk-delete-crash",
        source_id=source.id,
        content="delete must finish after restart",
        chunk_index=0,
        embedding=[0.1, 0.2, 0.3],
        metadata={"source_id": source.id},
    )
    native_index = RecordingNativeIndex()
    repo = SeekDBRepository(db_path, native_chunk_index=native_index, allow_sqlite_vector_fallback=False)
    await repo.save_source(source)
    await repo.save_chunks(source.id, [chunk])

    def interrupt_after_native_delete(*_args, **_kwargs):
        raise SystemExit("simulated delete interruption")

    monkeypatch.setattr(repo, "_finalize_source_delete", interrupt_after_native_delete)
    with pytest.raises(SystemExit, match="delete interruption"):
        await repo.delete_source(source.id)
    assert await repo.get_source(source.id) is not None
    assert repo._conn.execute("SELECT COUNT(*) FROM chunk_sync_operations").fetchone()[0] == 1
    await repo.close()

    recovered = SeekDBRepository(
        db_path,
        native_chunk_index=native_index,
        allow_sqlite_vector_fallback=False,
    )
    await recovered.initialize_storage()

    assert await recovered.get_source(source.id) is None
    assert native_index.get_source_chunks(source.id) == []
    assert recovered._conn.execute("SELECT COUNT(*) FROM chunk_sync_operations").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_native_search_uses_source_state_without_loading_all_chunks(tmp_path: Path):
    source = KnowledgeSource(id="src-lightweight-search", kind=SourceKind.TEXT, title="Lightweight")
    chunk = KnowledgeChunk(
        id="chunk-lightweight-search",
        source_id=source.id,
        content="search should not deserialize the whole collection",
        chunk_index=0,
        embedding=[0.1, 0.2, 0.3],
        metadata={"source_id": source.id},
    )
    native_index = RecordingNativeIndex()
    repo = SeekDBRepository(
        tmp_path / "knowledge.db",
        native_chunk_index=native_index,
        allow_sqlite_vector_fallback=False,
    )
    await repo.save_source(source)
    await repo.save_chunks(source.id, [chunk])
    native_index.get_source_calls.clear()

    await repo.search_chunks(
        "deserialize",
        source_ids=[source.id],
        top_k=1,
        query_embedding=[0.1, 0.2, 0.3],
    )
    await repo.search_chunks("deserialize", source_ids=[source.id], top_k=1)

    assert native_index.get_source_calls == []
    assert native_index.searches == [([0.1, 0.2, 0.3], [source.id], 1)]
    assert native_index.text_searches == [("deserialize", [source.id], 1)]


@pytest.mark.asyncio
async def test_strict_mode_scrubs_vectors_after_fallback_backfill(tmp_path: Path):
    db_path = tmp_path / "knowledge.db"
    source = KnowledgeSource(id="src-mode-switch", kind=SourceKind.TEXT, title="Mode switch")
    chunk = KnowledgeChunk(
        id="chunk-mode-switch",
        source_id=source.id,
        content="fallback vectors must be scrubbed in strict mode",
        chunk_index=0,
        embedding=[0.1, 0.2, 0.3],
        metadata={"source_id": source.id},
    )
    native_index = RecordingNativeIndex()
    fallback_repo = SeekDBRepository(
        db_path,
        native_chunk_index=native_index,
        allow_sqlite_vector_fallback=True,
    )
    await fallback_repo.save_source(source)
    await fallback_repo.save_chunks(source.id, [chunk])
    await fallback_repo.backfill_native_chunks()
    await fallback_repo.close()

    strict_repo = SeekDBRepository(
        db_path,
        native_chunk_index=native_index,
        allow_sqlite_vector_fallback=False,
    )
    await strict_repo.initialize_storage()

    row = strict_repo._conn.execute(
        "SELECT embedding, vector_state FROM chunks WHERE source_id = ?",
        (source.id,),
    ).fetchone()
    assert row["embedding"] is None
    assert row["vector_state"] == "seekdb"


@pytest.mark.asyncio
async def test_strict_native_mode_keeps_vectors_out_of_sqlite(tmp_path: Path):
    native_index = RecordingNativeIndex()
    repo = SeekDBRepository(
        tmp_path / "knowledge.db",
        native_chunk_index=native_index,
        allow_sqlite_vector_fallback=False,
    )
    source = KnowledgeSource(id="src-native-only", kind=SourceKind.TEXT, title="Native only")
    chunk = KnowledgeChunk(
        id="chunk-native-only",
        source_id=source.id,
        content="stored in SeekDB",
        chunk_index=0,
        embedding=[0.1, 0.2, 0.3],
        metadata={"source_id": source.id},
    )
    await repo.save_source(source)

    await repo.save_chunks(source.id, [chunk])

    sqlite_row = repo._conn.execute(
        "SELECT embedding, payload, vector_state FROM chunks WHERE source_id = ?",
        (source.id,),
    ).fetchone()
    assert sqlite_row is not None
    assert sqlite_row["embedding"] is None
    assert '"embedding":null' in sqlite_row["payload"]
    assert sqlite_row["vector_state"] == "seekdb"
    loaded = await repo.get_chunks(source.id)
    assert [item.id for item in loaded] == [chunk.id]
    assert loaded[0].embedding == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_repository_requires_embeddings_when_native_seekdb_is_primary(tmp_path: Path):
    repo = SeekDBRepository(
        tmp_path / "knowledge.db",
        native_chunk_index=RecordingNativeIndex(),
        allow_sqlite_vector_fallback=False,
    )
    source = KnowledgeSource(id="src-native-no-embedding", kind=SourceKind.TEXT, title="Native No Embedding")
    await repo.save_source(source)

    with pytest.raises((RuntimeError, ValueError), match="embedding|native SeekDB"):
        await repo.save_chunks(
            source.id,
            [
                KnowledgeChunk(
                    id="chunk-native-no-embedding",
                    source_id=source.id,
                    content="native primary requires an embedding",
                    chunk_index=0,
                    metadata={"source_id": source.id},
                )
            ],
        )


@pytest.mark.asyncio
async def test_repository_requires_native_seekdb_for_vector_save_unless_fallback_enabled(tmp_path: Path):
    repo = SeekDBRepository(
        tmp_path / "knowledge.db",
        native_chunk_index=None,
        allow_sqlite_vector_fallback=False,
    )
    source = KnowledgeSource(id="src-no-native", kind=SourceKind.TEXT, title="No Native")
    await repo.save_source(source)

    with pytest.raises(RuntimeError, match="native SeekDB vector index is unavailable"):
        await repo.save_chunks(
            source.id,
            [
                KnowledgeChunk(
                    id="chunk-no-native",
                    source_id=source.id,
                    content="content",
                    chunk_index=0,
                    embedding=[0.1, 0.2, 0.3],
                    metadata={"source_id": source.id},
                )
            ],
        )
    with pytest.raises(RuntimeError, match="native SeekDB vector index is unavailable"):
        await repo.get_chunks(source.id)
    assert repo._get_sqlite_chunks_sync(source.id) == []


@pytest.mark.asyncio
async def test_strict_empty_save_with_native_unavailable_keeps_existing_sqlite_chunks(tmp_path: Path):
    db_path = tmp_path / "knowledge.db"
    source = KnowledgeSource(id="src-strict-empty", kind=SourceKind.TEXT, title="Strict Empty")
    old_chunk = KnowledgeChunk(
        id="chunk-old",
        source_id=source.id,
        content="existing sqlite content",
        chunk_index=0,
        metadata={"source_id": source.id},
    )
    seed_repo = SeekDBRepository(db_path, native_chunk_index=None, allow_sqlite_vector_fallback=True)
    await seed_repo.save_source(source)
    await seed_repo.save_chunks(source.id, [old_chunk])
    await seed_repo.close()

    repo = SeekDBRepository(db_path, native_chunk_index=None, allow_sqlite_vector_fallback=False)

    with pytest.raises(RuntimeError, match="native SeekDB vector index is unavailable"):
        await repo.save_chunks(source.id, [])

    with pytest.raises(RuntimeError, match="native SeekDB vector index is unavailable"):
        await repo.get_chunks(source.id)
    assert [chunk.id for chunk in repo._get_sqlite_chunks_sync(source.id)] == ["chunk-old"]


@pytest.mark.asyncio
async def test_repository_requires_native_seekdb_for_non_vector_chunk_save_unless_fallback_enabled(tmp_path: Path):
    repo = SeekDBRepository(
        tmp_path / "knowledge.db",
        native_chunk_index=None,
        allow_sqlite_vector_fallback=False,
    )
    source = KnowledgeSource(id="src-no-native-text", kind=SourceKind.TEXT, title="No Native Text")
    await repo.save_source(source)

    with pytest.raises(RuntimeError, match="native SeekDB vector index is unavailable"):
        await repo.save_chunks(
            source.id,
            [
                KnowledgeChunk(
                    id="chunk-no-native-text",
                    source_id=source.id,
                    content="content without an embedding",
                    chunk_index=0,
                    metadata={"source_id": source.id},
                )
            ],
        )


@pytest.mark.asyncio
async def test_repository_uses_native_fulltext_when_query_embedding_is_unavailable(tmp_path: Path):
    native_index = RecordingNativeIndex()
    repo = SeekDBRepository(
        tmp_path / "knowledge.db",
        native_chunk_index=native_index,
        allow_sqlite_vector_fallback=False,
    )
    source = KnowledgeSource(id="src-native-query", kind=SourceKind.TEXT, title="Native Query")
    await repo.save_source(source)
    await repo.save_chunks(
        source.id,
        [
            KnowledgeChunk(
                id="chunk-native-query",
                source_id=source.id,
                content="native query content",
                chunk_index=0,
                embedding=[0.1, 0.2, 0.3],
                metadata={"source_id": source.id},
            )
        ],
    )

    results = await repo.search_chunks("native query", source_ids=[source.id], top_k=1)

    assert native_index.text_searches == [("native query", [source.id], 1)]
    assert results[0]["chunk"].id == "native_text_chunk"
    assert results[0]["backend"] == "seekdb"


@pytest.mark.asyncio
async def test_strict_native_get_chunks_rejects_unavailable_seekdb(tmp_path: Path):
    repo = SeekDBRepository(
        tmp_path / "knowledge.db",
        native_chunk_index=None,
        allow_sqlite_vector_fallback=False,
    )

    with pytest.raises(RuntimeError, match="native SeekDB vector index is unavailable"):
        await repo.get_chunks("src-missing-native")


@pytest.mark.asyncio
async def test_repository_does_not_search_sqlite_bm25_without_explicit_fallback(tmp_path: Path):
    repo = SeekDBRepository(
        tmp_path / "knowledge.db",
        native_chunk_index=None,
        allow_sqlite_vector_fallback=True,
    )
    source = KnowledgeSource(id="src-bm25-disabled", kind=SourceKind.TEXT, title="BM25 Disabled")
    await repo.save_source(source)
    await repo.save_chunks(
        source.id,
        [
            KnowledgeChunk(
                id="chunk-bm25-disabled",
                source_id=source.id,
                content="Needle lexical content",
                chunk_index=0,
                metadata={"source_id": source.id},
            )
        ],
    )
    repo.allow_sqlite_vector_fallback = False

    with pytest.raises(RuntimeError, match="native SeekDB vector index is unavailable"):
        await repo.search_chunks("Needle", source_ids=[source.id], top_k=1)


@pytest.mark.asyncio
async def test_fallback_no_embedding_save_clears_native_chunks_and_uses_sqlite_search(tmp_path: Path):
    native_index = StaleAwareNativeIndex()
    repo = SeekDBRepository(
        tmp_path / "knowledge.db",
        native_chunk_index=native_index,
        allow_sqlite_vector_fallback=True,
    )
    source = KnowledgeSource(id="src-fallback-clear", kind=SourceKind.TEXT, title="Fallback Clear")
    await repo.save_source(source)

    await repo.save_chunks(
        source.id,
        [
            KnowledgeChunk(
                id="chunk-fallback-clear",
                source_id=source.id,
                content="Fresh fallback lexical content",
                chunk_index=0,
                metadata={"source_id": source.id},
            )
        ],
    )

    sqlite_results = await repo.search_chunks("Fresh fallback", source_ids=[source.id], top_k=1)
    vector_results = await repo.search_chunks(
        "stale native",
        source_ids=[source.id],
        top_k=1,
        query_embedding=[0.1, 0.2, 0.3],
    )

    assert native_index.upserts == [(source.id, [])]
    assert sqlite_results[0]["chunk"].id == "chunk-fallback-clear"
    assert vector_results == []


@pytest.mark.asyncio
async def test_delete_source_clears_native_chunks_even_when_sqlite_ids_are_stale(tmp_path: Path):
    db_path = tmp_path / "knowledge.db"
    source = KnowledgeSource(id="src-delete-clear", kind=SourceKind.TEXT, title="Delete Clear")
    seed_repo = SeekDBRepository(db_path, native_chunk_index=None, allow_sqlite_vector_fallback=True)
    await seed_repo.save_source(source)
    await seed_repo.save_chunks(
        source.id,
        [
            KnowledgeChunk(
                id="sqlite-only-chunk",
                source_id=source.id,
                content="sqlite-only content",
                chunk_index=0,
                metadata={"source_id": source.id},
            )
        ],
    )
    await seed_repo.close()
    native_index = StaleAwareNativeIndex()
    repo = SeekDBRepository(db_path, native_chunk_index=native_index, allow_sqlite_vector_fallback=True)

    await repo.delete_source(source.id)
    stale_results = await repo.search_chunks(
        "stale native",
        source_ids=[source.id],
        top_k=1,
        query_embedding=[0.1, 0.2, 0.3],
    )

    assert (source.id, []) in native_index.upserts
    assert stale_results == []


@pytest.mark.asyncio
async def test_delete_source_requires_native_seekdb_before_sqlite_mutation(tmp_path: Path):
    db_path = tmp_path / "knowledge.db"
    source = KnowledgeSource(id="src-strict-delete", kind=SourceKind.TEXT, title="Strict Delete")
    old_chunk = KnowledgeChunk(
        id="chunk-strict-delete",
        source_id=source.id,
        content="existing sqlite metadata",
        chunk_index=0,
        embedding=[0.1, 0.2, 0.3],
        metadata={"source_id": source.id},
    )
    seed_repo = SeekDBRepository(db_path, native_chunk_index=None, allow_sqlite_vector_fallback=True)
    await seed_repo.save_source(source)
    await seed_repo.save_chunks(source.id, [old_chunk])
    await seed_repo.close()
    repo = SeekDBRepository(db_path, native_chunk_index=None, allow_sqlite_vector_fallback=False)

    with pytest.raises(RuntimeError, match="native SeekDB vector index is unavailable"):
        await repo.delete_source(source.id)

    assert await repo.get_source(source.id) is not None
    with pytest.raises(RuntimeError, match="native SeekDB vector index is unavailable"):
        await repo.get_chunks(source.id)
    assert [chunk.id for chunk in repo._get_sqlite_chunks_sync(source.id)] == ["chunk-strict-delete"]


@pytest.mark.asyncio
async def test_native_upsert_failure_rolls_back_sqlite_chunk_replacement(tmp_path: Path):
    db_path = tmp_path / "knowledge.db"
    source = KnowledgeSource(id="src-native-rollback", kind=SourceKind.TEXT, title="Native Rollback")
    old_chunk = KnowledgeChunk(
        id="chunk-old",
        source_id=source.id,
        content="old sqlite content",
        chunk_index=0,
        embedding=[0.4, 0.5, 0.6],
        metadata={"source_id": source.id},
    )
    seed_repo = SeekDBRepository(db_path, native_chunk_index=None, allow_sqlite_vector_fallback=True)
    await seed_repo.save_source(source)
    await seed_repo.save_chunks(source.id, [old_chunk])
    await seed_repo.close()
    native_index = FailOnceNativeIndex(source.id, [old_chunk])
    repo = SeekDBRepository(
        db_path,
        native_chunk_index=native_index,
        allow_sqlite_vector_fallback=False,
    )

    with pytest.raises(RuntimeError, match="native write failed"):
        await repo.save_chunks(
            source.id,
            [
                KnowledgeChunk(
                    id="chunk-new",
                    source_id=source.id,
                    content="new sqlite content",
                    chunk_index=0,
                    embedding=[0.1, 0.2, 0.3],
                    metadata={"source_id": source.id},
                )
            ],
        )

    assert [chunk.id for chunk in await repo.get_chunks(source.id)] == ["chunk-old"]
    assert [chunk.id for chunk in repo._get_sqlite_chunks_sync(source.id)] == ["chunk-old"]


@pytest.mark.asyncio
async def test_delete_source_restores_native_chunks_when_sqlite_delete_fails(tmp_path: Path):
    source = KnowledgeSource(id="src-delete-compensation", kind=SourceKind.TEXT, title="Delete compensation")
    old_chunk = KnowledgeChunk(
        id="chunk-delete-compensation",
        source_id=source.id,
        content="must survive a failed delete",
        chunk_index=0,
        embedding=[0.1, 0.2, 0.3],
        metadata={"source_id": source.id},
    )
    native_index = RecordingNativeIndex()
    repo = SeekDBRepository(
        tmp_path / "knowledge.db",
        native_chunk_index=native_index,
        allow_sqlite_vector_fallback=False,
    )
    await repo.save_source(source)
    await repo.save_chunks(source.id, [old_chunk])
    repo._conn.execute(
        """
        CREATE TRIGGER fail_source_delete BEFORE DELETE ON sources
        BEGIN SELECT RAISE(ABORT, 'delete failed'); END
        """
    )

    with pytest.raises(Exception, match="delete failed"):
        await repo.delete_source(source.id)

    assert await repo.get_source(source.id) is not None
    assert [chunk.id for chunk in await repo.get_chunks(source.id)] == [old_chunk.id]


@pytest.mark.asyncio
async def test_strict_native_rejects_mixed_dimension_embeddings_before_sqlite_mutation(
    tmp_path: Path,
):
    db_path = tmp_path / "knowledge.db"
    source = KnowledgeSource(id="src-mixed-dim", kind=SourceKind.TEXT, title="Mixed Dimension")
    old_chunk = KnowledgeChunk(
        id="chunk-old",
        source_id=source.id,
        content="old sqlite content",
        chunk_index=0,
        embedding=[0.4, 0.5, 0.6],
        metadata={"source_id": source.id},
    )
    seed_repo = SeekDBRepository(db_path, native_chunk_index=None, allow_sqlite_vector_fallback=True)
    await seed_repo.save_source(source)
    await seed_repo.save_chunks(source.id, [old_chunk])
    await seed_repo.close()
    native_index = StaleAwareNativeIndex()
    repo = SeekDBRepository(
        db_path,
        native_chunk_index=native_index,
        allow_sqlite_vector_fallback=False,
    )

    with pytest.raises(RuntimeError, match="same-dimension embeddings"):
        await repo.save_chunks(
            source.id,
            [
                KnowledgeChunk(
                    id="chunk-new-a",
                    source_id=source.id,
                    content="new sqlite content a",
                    chunk_index=0,
                    embedding=[0.1, 0.2, 0.3],
                    metadata={"source_id": source.id},
                ),
                KnowledgeChunk(
                    id="chunk-new-b",
                    source_id=source.id,
                    content="new sqlite content b",
                    chunk_index=1,
                    embedding=[0.1, 0.2],
                    metadata={"source_id": source.id},
                ),
            ],
        )

    assert native_index.upserts == []
    assert [chunk.id for chunk in await repo.get_chunks(source.id)] == ["chunk-old"]
    assert [chunk.id for chunk in repo._get_sqlite_chunks_sync(source.id)] == ["chunk-old"]


@pytest.mark.asyncio
async def test_native_clear_failure_rolls_back_fallback_sqlite_chunk_replacement(tmp_path: Path):
    db_path = tmp_path / "knowledge.db"
    source = KnowledgeSource(id="src-clear-rollback", kind=SourceKind.TEXT, title="Clear Rollback")
    old_chunk = KnowledgeChunk(
        id="chunk-old",
        source_id=source.id,
        content="old fallback content",
        chunk_index=0,
        metadata={"source_id": source.id},
    )
    seed_repo = SeekDBRepository(db_path, native_chunk_index=None, allow_sqlite_vector_fallback=True)
    await seed_repo.save_source(source)
    await seed_repo.save_chunks(source.id, [old_chunk])
    await seed_repo.close()
    repo = SeekDBRepository(
        db_path,
        native_chunk_index=FailingNativeIndex("native clear failed"),
        allow_sqlite_vector_fallback=True,
    )

    with pytest.raises(RuntimeError, match="native clear failed"):
        await repo.save_chunks(
            source.id,
            [
                KnowledgeChunk(
                    id="chunk-new",
                    source_id=source.id,
                    content="new fallback content",
                    chunk_index=0,
                    metadata={"source_id": source.id},
                )
            ],
        )

    assert [chunk.id for chunk in await repo.get_chunks(source.id)] == ["chunk-old"]


@pytest.mark.asyncio
async def test_repository_backfills_existing_sqlite_chunks_to_native_index(tmp_path: Path):
    db_path = tmp_path / "knowledge.db"
    fallback_repo = SeekDBRepository(
        db_path,
        native_chunk_index=None,
        allow_sqlite_vector_fallback=True,
    )
    source = KnowledgeSource(id="src-backfill", kind=SourceKind.TEXT, title="Backfill")
    await fallback_repo.save_source(source)
    await fallback_repo.save_chunks(
        source.id,
        [
            KnowledgeChunk(
                id="chunk-backfill",
                source_id=source.id,
                content="backfill content",
                chunk_index=0,
                embedding=[0.1, 0.2, 0.3],
                metadata={"source_id": source.id},
            )
        ],
    )
    await fallback_repo.close()

    native_index = RecordingNativeIndex()
    repo = SeekDBRepository(
        db_path,
        native_chunk_index=native_index,
        allow_sqlite_vector_fallback=False,
    )

    written = await repo.backfill_native_chunks()
    second_written = await repo.backfill_native_chunks()

    assert written == 1
    assert second_written == 0
    assert len(native_index.upserts) == 1
    assert native_index.upserts[0][0] == source.id
    assert native_index.upserts[0][1][0].id == "chunk-backfill"
    assert [chunk.id for chunk in native_index.get_source_chunks(source.id)] == ["chunk-backfill"]
    sqlite_row = repo._conn.execute(
        "SELECT embedding, payload FROM chunks WHERE source_id = ?",
        (source.id,),
    ).fetchone()
    assert sqlite_row["embedding"] is None
    assert '"embedding":null' in sqlite_row["payload"]


@pytest.mark.asyncio
async def test_backfill_restores_native_chunks_when_sqlite_scrub_fails(tmp_path: Path):
    db_path = tmp_path / "knowledge.db"
    source = KnowledgeSource(id="src-backfill-compensation", kind=SourceKind.TEXT, title="Backfill compensation")
    legacy_chunk = KnowledgeChunk(
        id="chunk-legacy",
        source_id=source.id,
        content="legacy vector",
        chunk_index=0,
        embedding=[0.1, 0.2, 0.3],
        metadata={"source_id": source.id},
    )
    previous_native_chunk = KnowledgeChunk(
        id="chunk-native-old",
        source_id=source.id,
        content="previous native vector",
        chunk_index=0,
        embedding=[0.4, 0.5, 0.6],
        metadata={"source_id": source.id},
    )
    fallback_repo = SeekDBRepository(db_path, native_chunk_index=None, allow_sqlite_vector_fallback=True)
    await fallback_repo.save_source(source)
    await fallback_repo.save_chunks(source.id, [legacy_chunk])
    await fallback_repo.close()

    native_index = RecordingNativeIndex()
    native_index.chunks_by_source[source.id] = [previous_native_chunk]
    repo = SeekDBRepository(db_path, native_chunk_index=native_index, allow_sqlite_vector_fallback=False)
    repo._conn.execute(
        """
        CREATE TRIGGER fail_chunk_scrub BEFORE UPDATE ON chunks
        BEGIN SELECT RAISE(ABORT, 'scrub failed'); END
        """
    )

    with pytest.raises(Exception, match="scrub failed"):
        await repo.backfill_native_chunks()

    assert [chunk.id for chunk in native_index.get_source_chunks(source.id)] == [previous_native_chunk.id]
    sqlite_chunk = repo._get_sqlite_chunks_sync(source.id)[0]
    assert sqlite_chunk.embedding == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_repository_backfill_requires_native_index_without_fallback(tmp_path: Path):
    repo = SeekDBRepository(
        tmp_path / "knowledge.db",
        native_chunk_index=None,
        allow_sqlite_vector_fallback=False,
    )

    with pytest.raises(RuntimeError, match="cannot backfill chunks"):
        await repo.backfill_native_chunks()


def test_repository_storage_status_reports_failed_native_probe(tmp_path: Path):
    repo = SeekDBRepository(
        tmp_path / "probe-status.db",
        native_chunk_index=ProbeFailingNativeIndex(),
        allow_sqlite_vector_fallback=False,
    )

    status = repo.storage_status()

    assert status["vector_backend"] == "unavailable"
    assert status["native_available"] is False
    assert "native probe failed" in status["error"]


@pytest.mark.asyncio
async def test_repository_backfill_clears_stale_native_for_fallback_rows_without_embeddings(tmp_path: Path):
    db_path = tmp_path / "knowledge.db"
    source = KnowledgeSource(id="src-backfill-clear", kind=SourceKind.TEXT, title="Backfill Clear")
    fallback_repo = SeekDBRepository(db_path, native_chunk_index=None, allow_sqlite_vector_fallback=True)
    await fallback_repo.save_source(source)
    await fallback_repo.save_chunks(
        source.id,
        [
            KnowledgeChunk(
                id="chunk-plain",
                source_id=source.id,
                content="plain backfill content",
                chunk_index=0,
                metadata={"source_id": source.id},
            )
        ],
    )
    await fallback_repo.close()

    native_index = StaleAwareNativeIndex()
    native_index.chunks_by_source[source.id] = [
        KnowledgeChunk(
            id="stale-native",
            source_id=source.id,
            content="stale native content",
            chunk_index=0,
            embedding=[0.1, 0.2, 0.3],
            metadata={"source_id": source.id},
        )
    ]
    repo = SeekDBRepository(db_path, native_chunk_index=native_index, allow_sqlite_vector_fallback=False)

    written = await repo.backfill_native_chunks()
    second_written = await repo.backfill_native_chunks()
    results = await repo.search_chunks(
        "plain backfill",
        source_ids=[source.id],
        top_k=1,
        query_embedding=[0.1, 0.2, 0.3],
    )

    assert written == 0
    assert second_written == 0
    assert native_index.upserts == [(source.id, [])]
    assert native_index.get_source_chunks(source.id) == []
    state = repo._conn.execute(
        "SELECT vector_state FROM chunks WHERE source_id = ?",
        (source.id,),
    ).fetchone()["vector_state"]
    assert state == "legacy_needs_embedding"
    assert results[0]["chunk"].id == "chunk-plain"
    assert results[0]["backend"] == "sqlite_legacy_text"


@pytest.mark.asyncio
async def test_strict_backfill_keeps_unembedded_legacy_sources_lexically_searchable_and_retryable(
    tmp_path: Path,
):
    db_path = tmp_path / "knowledge.db"
    source = KnowledgeSource(id="src-legacy-lexical", kind=SourceKind.TEXT, title="Legacy lexical")
    fallback_repo = SeekDBRepository(db_path, native_chunk_index=None, allow_sqlite_vector_fallback=True)
    await fallback_repo.save_source(source)
    await fallback_repo.save_chunks(
        source.id,
        [
            KnowledgeChunk(
                id="chunk-legacy-lexical",
                source_id=source.id,
                content="Asterion protocol preserves lexical retrieval",
                chunk_index=0,
                metadata={"source_id": source.id},
            )
        ],
    )
    await fallback_repo.close()

    repo = SeekDBRepository(
        db_path,
        native_chunk_index=RecordingNativeIndex(),
        allow_sqlite_vector_fallback=False,
    )
    await repo.initialize_storage()
    results = await repo.search_chunks(
        "Asterion protocol",
        source_ids=[source.id],
        top_k=1,
        query_embedding=[0.1, 0.2, 0.3],
    )

    assert results[0]["chunk"].id == "chunk-legacy-lexical"
    assert results[0]["backend"] == "sqlite_legacy_text"
    state = repo._conn.execute(
        "SELECT storage_mode FROM chunk_index_state WHERE source_id = ?",
        (source.id,),
    ).fetchone()
    assert state["storage_mode"] == "sqlite_legacy"
    assert repo._get_repository_meta("native_chunk_migration_v2") is None
    chunks = await repo.get_chunks(source.id)
    assert [chunk.id for chunk in chunks] == ["chunk-legacy-lexical"]


@pytest.mark.asyncio
async def test_repository_native_search_skips_legacy_sources_without_embeddings_after_backfill(
    tmp_path: Path,
):
    db_path = tmp_path / "knowledge.db"
    embedded_source = KnowledgeSource(id="src-embedded", kind=SourceKind.TEXT, title="Embedded")
    plain_source = KnowledgeSource(id="src-plain", kind=SourceKind.TEXT, title="Plain")
    fallback_repo = SeekDBRepository(db_path, native_chunk_index=None, allow_sqlite_vector_fallback=True)
    await fallback_repo.save_source(embedded_source)
    await fallback_repo.save_chunks(
        embedded_source.id,
        [
            KnowledgeChunk(
                id="chunk-embedded",
                source_id=embedded_source.id,
                content="embedded legacy content",
                chunk_index=0,
                embedding=[0.1, 0.2, 0.3],
                metadata={"source_id": embedded_source.id},
            )
        ],
    )
    await fallback_repo.save_source(plain_source)
    await fallback_repo.save_chunks(
        plain_source.id,
        [
            KnowledgeChunk(
                id="chunk-plain",
                source_id=plain_source.id,
                content="plain legacy content",
                chunk_index=0,
                metadata={"source_id": plain_source.id},
            )
        ],
    )
    await fallback_repo.close()

    native_index = RecordingNativeIndex()
    repo = SeekDBRepository(db_path, native_chunk_index=native_index, allow_sqlite_vector_fallback=False)

    await repo.backfill_native_chunks()
    await repo.search_chunks("legacy", source_ids=None, top_k=1, query_embedding=[0.1, 0.2, 0.3])

    assert {source_id for source_id, _chunks in native_index.upserts} == {
        embedded_source.id,
        plain_source.id,
    }
    assert native_index.searches == [([0.1, 0.2, 0.3], [embedded_source.id], 1)]


@pytest.mark.asyncio
async def test_repository_backfill_skips_partially_embedded_sources_and_native_search(
    tmp_path: Path,
):
    db_path = tmp_path / "knowledge.db"
    source = KnowledgeSource(id="src-partial", kind=SourceKind.TEXT, title="Partial")
    fallback_repo = SeekDBRepository(db_path, native_chunk_index=None, allow_sqlite_vector_fallback=True)
    await fallback_repo.save_source(source)
    await fallback_repo.save_chunks(
        source.id,
        [
            KnowledgeChunk(
                id="chunk-embedded",
                source_id=source.id,
                content="embedded partial content",
                chunk_index=0,
                embedding=[0.1, 0.2, 0.3],
                metadata={"source_id": source.id},
            ),
            KnowledgeChunk(
                id="chunk-plain",
                source_id=source.id,
                content="plain partial content",
                chunk_index=1,
                metadata={"source_id": source.id},
            ),
        ],
    )
    await fallback_repo.close()

    native_index = StaleAwareNativeIndex()
    repo = SeekDBRepository(db_path, native_chunk_index=native_index, allow_sqlite_vector_fallback=False)

    written = await repo.backfill_native_chunks()
    results = await repo.search_chunks(
        "partial",
        source_ids=[source.id],
        top_k=1,
        query_embedding=[0.1, 0.2, 0.3],
    )

    assert written == 0
    assert native_index.upserts == [(source.id, [])]
    assert native_index.searches == []
    assert results[0]["chunk"].source_id == source.id
    assert results[0]["backend"] == "sqlite_legacy_text"


@pytest.mark.asyncio
async def test_repository_native_search_uses_sqlite_fallback_for_partial_writes(tmp_path: Path):
    native_index = RecordingNativeIndex()
    repo = SeekDBRepository(
        tmp_path / "knowledge.db",
        native_chunk_index=native_index,
        allow_sqlite_vector_fallback=True,
    )
    source = KnowledgeSource(id="src-partial-fallback", kind=SourceKind.TEXT, title="Partial Fallback")
    await repo.save_source(source)
    await repo.save_chunks(
        source.id,
        [
            KnowledgeChunk(
                id="chunk-embedded",
                source_id=source.id,
                content="embedded fallback content",
                chunk_index=0,
                embedding=[0.1, 0.2, 0.3],
                metadata={"source_id": source.id},
            ),
            KnowledgeChunk(
                id="chunk-plain",
                source_id=source.id,
                content="plain fallback content",
                chunk_index=1,
                metadata={"source_id": source.id},
            ),
        ],
    )

    results = await repo.search_chunks(
        "fallback",
        source_ids=[source.id],
        top_k=1,
        query_embedding=[0.1, 0.2, 0.3],
    )

    assert native_index.upserts == [(source.id, [])]
    assert native_index.searches == []
    assert results
    assert results[0]["chunk"].source_id == source.id


@pytest.mark.asyncio
async def test_repository_backfill_treats_empty_embedding_as_native_ineligible(tmp_path: Path):
    db_path = tmp_path / "knowledge.db"
    source = KnowledgeSource(id="src-empty-embedding", kind=SourceKind.TEXT, title="Empty Embedding")
    fallback_repo = SeekDBRepository(db_path, native_chunk_index=None, allow_sqlite_vector_fallback=True)
    await fallback_repo.save_source(source)
    await fallback_repo.save_chunks(
        source.id,
        [
            KnowledgeChunk(
                id="chunk-empty-embedding",
                source_id=source.id,
                content="empty embedding content",
                chunk_index=0,
                embedding=[],
                metadata={"source_id": source.id},
            )
        ],
    )
    await fallback_repo.close()

    native_index = StaleAwareNativeIndex()
    repo = SeekDBRepository(db_path, native_chunk_index=native_index, allow_sqlite_vector_fallback=False)

    written = await repo.backfill_native_chunks()
    results = await repo.search_chunks(
        "empty embedding",
        source_ids=[source.id],
        top_k=1,
        query_embedding=[0.1, 0.2, 0.3],
    )

    assert written == 0
    assert native_index.upserts == [(source.id, [])]
    assert native_index.searches == []
    assert results[0]["chunk"].id == "chunk-empty-embedding"
    assert results[0]["backend"] == "sqlite_legacy_text"


@pytest.mark.asyncio
async def test_repository_native_search_rejects_dimension_mismatched_sources(
    tmp_path: Path,
):
    db_path = tmp_path / "knowledge.db"
    source_3d = KnowledgeSource(id="src-3d", kind=SourceKind.TEXT, title="3D")
    source_2d = KnowledgeSource(id="src-2d", kind=SourceKind.TEXT, title="2D")
    fallback_repo = SeekDBRepository(db_path, native_chunk_index=None, allow_sqlite_vector_fallback=True)
    await fallback_repo.save_source(source_3d)
    await fallback_repo.save_chunks(
        source_3d.id,
        [
            KnowledgeChunk(
                id="chunk-3d",
                source_id=source_3d.id,
                content="three dimension content",
                chunk_index=0,
                embedding=[0.1, 0.2, 0.3],
                metadata={"source_id": source_3d.id},
            )
        ],
    )
    await fallback_repo.save_source(source_2d)
    await fallback_repo.save_chunks(
        source_2d.id,
        [
            KnowledgeChunk(
                id="chunk-2d",
                source_id=source_2d.id,
                content="two dimension content",
                chunk_index=0,
                embedding=[0.1, 0.2],
                metadata={"source_id": source_2d.id},
            )
        ],
    )
    await fallback_repo.close()

    native_index = DimensionCheckingNativeIndex()
    repo = SeekDBRepository(db_path, native_chunk_index=native_index, allow_sqlite_vector_fallback=False)
    await repo.backfill_native_chunks()

    with pytest.raises(RuntimeError, match="embedding dimension"):
        await repo.search_chunks(
            "dimension",
            source_ids=None,
            top_k=1,
            query_embedding=[0.1, 0.2, 0.3],
        )

    assert native_index.searches == []


@pytest.mark.asyncio
async def test_repository_native_search_rejects_changed_embedding_profile(tmp_path: Path):
    native_index = RecordingNativeIndex()
    db_path = tmp_path / "knowledge.db"
    source = KnowledgeSource(id="src-profile", kind=SourceKind.TEXT, title="Profile")
    writer = SeekDBRepository(
        db_path,
        native_chunk_index=native_index,
        allow_sqlite_vector_fallback=False,
        embedding_profile_id="profile-a",
    )
    await writer.save_source(source)
    await writer.save_chunks(
        source.id,
        [
            KnowledgeChunk(
                id="chunk-profile",
                source_id=source.id,
                content="embedding profile content",
                chunk_index=0,
                embedding=[0.1, 0.2, 0.3],
                metadata={"source_id": source.id},
            )
        ],
    )
    await writer.close()

    reader = SeekDBRepository(
        db_path,
        native_chunk_index=native_index,
        allow_sqlite_vector_fallback=False,
        embedding_profile_id="profile-b",
    )

    with pytest.raises(RuntimeError, match="embedding profile"):
        await reader.search_chunks(
            "profile",
            source_ids=[source.id],
            top_k=1,
            query_embedding=[0.1, 0.2, 0.3],
        )


@pytest.mark.asyncio
async def test_sqlite_fallback_does_not_compare_vectors_from_an_old_embedding_profile(
    tmp_path: Path,
):
    native_index = RecordingNativeIndex()
    db_path = tmp_path / "fallback-profile.db"
    source = KnowledgeSource(id="src-fallback-profile", kind=SourceKind.TEXT, title="Fallback")
    writer = SeekDBRepository(
        db_path,
        native_chunk_index=native_index,
        allow_sqlite_vector_fallback=True,
        embedding_profile_id="profile-a",
    )
    await writer.save_source(source)
    await writer.save_chunks(
        source.id,
        [
            KnowledgeChunk(
                id="chunk-fallback-profile",
                source_id=source.id,
                content="unrelated content",
                chunk_index=0,
                embedding=[1.0, 0.0],
                metadata={"source_id": source.id},
            )
        ],
    )
    await writer.close()

    reader = SeekDBRepository(
        db_path,
        native_chunk_index=native_index,
        allow_sqlite_vector_fallback=True,
        embedding_profile_id="profile-b",
    )
    results = await reader.search_chunks(
        "needle",
        source_ids=[source.id],
        top_k=1,
        query_embedding=[1.0, 0.0],
    )

    assert results == []


@pytest.mark.asyncio
async def test_repository_sqlite_fallback_handles_dimension_mismatched_sources(
    tmp_path: Path,
):
    native_index = DimensionCheckingNativeIndex()
    repo = SeekDBRepository(
        tmp_path / "knowledge.db",
        native_chunk_index=native_index,
        allow_sqlite_vector_fallback=True,
    )
    source_3d = KnowledgeSource(id="src-3d-fallback", kind=SourceKind.TEXT, title="3D Fallback")
    source_2d = KnowledgeSource(id="src-2d-fallback", kind=SourceKind.TEXT, title="2D Fallback")
    await repo.save_source(source_3d)
    await repo.save_chunks(
        source_3d.id,
        [
            KnowledgeChunk(
                id="chunk-3d-fallback",
                source_id=source_3d.id,
                content="three dimension fallback",
                chunk_index=0,
                embedding=[0.1, 0.2, 0.3],
                metadata={"source_id": source_3d.id},
            )
        ],
    )
    await repo.save_source(source_2d)
    await repo.save_chunks(
        source_2d.id,
        [
            KnowledgeChunk(
                id="chunk-2d-fallback",
                source_id=source_2d.id,
                content="two dimension fallback",
                chunk_index=0,
                embedding=[0.1, 0.2],
                metadata={"source_id": source_2d.id},
            )
        ],
    )

    results = await repo.search_chunks(
        "two dimension",
        source_ids=[source_2d.id],
        top_k=1,
        query_embedding=[0.1, 0.2, 0.3],
    )

    assert native_index.searches == []
    assert results
    assert results[0]["chunk"].id == "chunk-2d-fallback"


@pytest.mark.asyncio
async def test_repository_sqlite_fallback_handles_missing_native_collection_for_eligible_chunks(
    tmp_path: Path,
):
    db_path = tmp_path / "knowledge.db"
    source = KnowledgeSource(id="src-legacy-eligible", kind=SourceKind.TEXT, title="Legacy Eligible")
    seed_repo = SeekDBRepository(db_path, native_chunk_index=None, allow_sqlite_vector_fallback=True)
    await seed_repo.save_source(source)
    await seed_repo.save_chunks(
        source.id,
        [
            KnowledgeChunk(
                id="chunk-legacy-eligible",
                source_id=source.id,
                content="legacy eligible fallback content",
                chunk_index=0,
                embedding=[0.1, 0.2, 0.3],
                metadata={"source_id": source.id},
            )
        ],
    )
    await seed_repo.close()

    native_index = QueryFailingNativeIndex()
    repo = SeekDBRepository(db_path, native_chunk_index=native_index, allow_sqlite_vector_fallback=True)

    results = await repo.search_chunks(
        "legacy eligible",
        source_ids=[source.id],
        top_k=1,
        query_embedding=[0.1, 0.2, 0.3],
    )

    assert native_index.searches == []
    assert results
    assert results[0]["chunk"].id == "chunk-legacy-eligible"


@pytest.mark.asyncio
async def test_repository_sqlite_fallback_keeps_vector_only_zero_cosine_results(
    tmp_path: Path,
):
    source = KnowledgeSource(id="src-zero-cosine", kind=SourceKind.TEXT, title="Zero Cosine")
    repo = SeekDBRepository(
        tmp_path / "knowledge.db",
        native_chunk_index=QueryFailingNativeIndex(),
        allow_sqlite_vector_fallback=True,
    )
    await repo.save_source(source)
    await repo.save_chunks(
        source.id,
        [
            KnowledgeChunk(
                id="chunk-zero-cosine",
                source_id=source.id,
                content="orthogonal vector content without lexical query overlap",
                chunk_index=0,
                embedding=[0.0, 1.0],
                metadata={"source_id": source.id},
            )
        ],
    )

    results = await repo.search_chunks(
        "unrelated",
        source_ids=[source.id],
        top_k=1,
        query_embedding=[1.0, 0.0],
    )

    assert results
    assert results[0]["chunk"].id == "chunk-zero-cosine"
    assert results[0]["score"] == 0.0


@pytest.mark.asyncio
async def test_strict_native_search_rejects_empty_query_embedding(tmp_path: Path):
    native_index = RecordingNativeIndex()
    repo = SeekDBRepository(
        tmp_path / "knowledge.db",
        native_chunk_index=native_index,
        allow_sqlite_vector_fallback=False,
    )
    source = KnowledgeSource(id="src-empty-query", kind=SourceKind.TEXT, title="Empty Query")
    await repo.save_source(source)
    await repo.save_chunks(
        source.id,
        [
            KnowledgeChunk(
                id="chunk-empty-query",
                source_id=source.id,
                content="empty query content",
                chunk_index=0,
                embedding=[0.1, 0.2, 0.3],
                metadata={"source_id": source.id},
            )
        ],
    )

    with pytest.raises(RuntimeError, match="non-empty query embedding"):
        await repo.search_chunks(
            "empty query",
            source_ids=[source.id],
            top_k=1,
            query_embedding=[],
        )

    assert native_index.searches == []


@pytest.mark.asyncio
async def test_sqlite_fallback_handles_empty_query_embedding(tmp_path: Path):
    native_index = RecordingNativeIndex()
    repo = SeekDBRepository(
        tmp_path / "knowledge.db",
        native_chunk_index=native_index,
        allow_sqlite_vector_fallback=True,
    )
    source = KnowledgeSource(id="src-empty-query-fallback", kind=SourceKind.TEXT, title="Empty Query Fallback")
    await repo.save_source(source)
    await repo.save_chunks(
        source.id,
        [
            KnowledgeChunk(
                id="chunk-empty-query-fallback",
                source_id=source.id,
                content="empty query fallback content",
                chunk_index=0,
                embedding=[0.1, 0.2, 0.3],
                metadata={"source_id": source.id},
            )
        ],
    )

    results = await repo.search_chunks(
        "empty query fallback",
        source_ids=[source.id],
        top_k=1,
        query_embedding=[],
    )

    assert native_index.searches == []
    assert results
    assert results[0]["chunk"].id == "chunk-empty-query-fallback"


@pytest.mark.asyncio
async def test_sqlite_fallback_respects_empty_source_selection(tmp_path: Path):
    repo = SeekDBRepository(
        tmp_path / "knowledge.db",
        native_chunk_index=RecordingNativeIndex(),
        allow_sqlite_vector_fallback=True,
    )
    source = KnowledgeSource(id="src-empty-selection", kind=SourceKind.TEXT, title="Empty Selection")
    await repo.save_source(source)
    await repo.save_chunks(
        source.id,
        [
            KnowledgeChunk(
                id="chunk-empty-selection",
                source_id=source.id,
                content="empty selection fallback content",
                chunk_index=0,
                metadata={"source_id": source.id},
            )
        ],
    )

    no_embedding_results = await repo.search_chunks(
        "empty selection",
        source_ids=[],
        top_k=1,
        query_embedding=None,
    )
    empty_embedding_results = await repo.search_chunks(
        "empty selection",
        source_ids=[],
        top_k=1,
        query_embedding=[],
    )

    assert no_embedding_results == []
    assert empty_embedding_results == []


@pytest.mark.asyncio
async def test_strict_native_search_respects_empty_source_selection_without_embedding(tmp_path: Path):
    native_index = RecordingNativeIndex()
    repo = SeekDBRepository(
        tmp_path / "knowledge.db",
        native_chunk_index=native_index,
        allow_sqlite_vector_fallback=False,
    )

    results = await repo.search_chunks(
        "empty selection",
        source_ids=[],
        top_k=1,
        query_embedding=None,
    )

    assert results == []
    assert native_index.searches == []


@pytest.mark.asyncio
async def test_source_service_ingestion_and_vector_store_search_use_native_seekdb(tmp_path: Path):
    native_index = RecordingNativeIndex()
    embedding_provider = DeterministicEmbeddingProvider()
    repo = SeekDBRepository(
        tmp_path / "knowledge.db",
        native_chunk_index=native_index,
        allow_sqlite_vector_fallback=False,
    )
    service = SourceService(
        repository=repo,
        parser=DoclingParser(),
        embedding_provider=embedding_provider,
        chunk_size=128,
        chunk_overlap=0,
    )

    source = await service.create_text_source("Native E2E", "Alpha native retrieval content.")
    from backend.infrastructure.vector_stores.seekdb_vector_store import SeekDBVectorStore

    store = SeekDBVectorStore(repo, embedding_provider=embedding_provider)
    results = await store.search("Alpha native", top_k=1, doc_ids=[source.id])

    assert source.status == "ready"
    assert native_index.upserts[0][0] == source.id
    assert all(chunk.embedding == [0.1, 0.2, 0.3] for chunk in native_index.upserts[0][1])
    assert native_index.searches == [([0.1, 0.2, 0.3], [source.id], 1)]
    assert results[0]["id"] == "native_chunk"


@pytest.mark.asyncio
async def test_source_service_marks_ready_only_after_chunk_commit(tmp_path: Path, monkeypatch):
    native_index = RecordingNativeIndex()
    repo = SeekDBRepository(
        tmp_path / "ingestion-order.db",
        native_chunk_index=native_index,
        allow_sqlite_vector_fallback=False,
    )
    events: list[str] = []
    original_save_source = repo.save_source
    original_save_chunks = repo.save_chunks

    async def record_source(source):
        events.append(f"source:{source.status.value}")
        return await original_save_source(source)

    async def record_chunks(source_id, chunks):
        events.append("chunks")
        return await original_save_chunks(source_id, chunks)

    monkeypatch.setattr(repo, "save_source", record_source)
    monkeypatch.setattr(repo, "save_chunks", record_chunks)
    service = SourceService(
        repository=repo,
        parser=DoclingParser(),
        embedding_provider=DeterministicEmbeddingProvider(),
        chunk_size=128,
        chunk_overlap=0,
    )

    source = await service.create_text_source("Ordered", "Commit chunks before ready.")

    assert source.status.value == "ready"
    assert events == ["source:processing", "source:processing", "chunks", "source:ready"]


@pytest.mark.asyncio
async def test_repository_recovers_processing_source_after_committed_chunks(tmp_path: Path):
    db_path = tmp_path / "processing-recovery.db"
    native_index = RecordingNativeIndex()
    source = KnowledgeSource(
        id="src-processing-recovery",
        kind=SourceKind.TEXT,
        title="Recovery",
        text="Parsed content survived the interruption.",
        chunk_count=1,
    )
    chunk = KnowledgeChunk(
        id="chunk-processing-recovery",
        source_id=source.id,
        content=source.text,
        chunk_index=0,
        embedding=[0.1, 0.2, 0.3],
        metadata={"source_id": source.id},
    )
    writer = SeekDBRepository(
        db_path,
        native_chunk_index=native_index,
        allow_sqlite_vector_fallback=False,
    )
    await writer.save_source(source)
    await writer.save_chunks(source.id, [chunk])
    await writer.close()

    recovered = SeekDBRepository(
        db_path,
        native_chunk_index=native_index,
        allow_sqlite_vector_fallback=False,
    )
    await recovered.initialize_storage()

    loaded = await recovered.get_source(source.id)
    assert loaded is not None
    assert loaded.status.value == "ready"


@pytest.mark.asyncio
async def test_text_source_is_chunked_with_citation_metadata(tmp_path: Path):
    repo = SeekDBRepository(tmp_path / "knowledge.db", native_chunk_index=None, allow_sqlite_vector_fallback=True)
    service = SourceService(
        repository=repo,
        parser=DoclingParser(),
        chunk_size=24,
        chunk_overlap=6,
    )

    source = await service.create_text_source(
        title="Research notes",
        text="Alpha beta gamma.\n\nDelta epsilon zeta connects to alpha.",
    )

    chunks = await repo.get_chunks(source.id)

    assert source.title == "Research notes"
    assert source.status == "ready"
    assert len(chunks) >= 2
    assert chunks[0].source_id == source.id
    assert chunks[0].metadata["source_title"] == "Research notes"
    assert chunks[0].metadata["chunk_index"] == 0
    assert chunks[0].start_offset == 0
    assert chunks[0].end_offset > chunks[0].start_offset


@pytest.mark.asyncio
async def test_upload_parse_failure_is_recorded(tmp_path: Path):
    class BrokenParser:
        async def parse_file(self, file_path: str | Path, filename: str | None = None):
            raise ValueError("parse exploded")

        async def parse_text(self, text: str, title: str = "Pasted text"):
            raise AssertionError("not used")

    repo = SeekDBRepository(tmp_path / "knowledge.db", native_chunk_index=None, allow_sqlite_vector_fallback=True)
    service = SourceService(repository=repo, parser=BrokenParser())
    file_path = tmp_path / "broken.pdf"
    file_path.write_bytes(b"%PDF-1.4 broken")

    source = await service.create_file_source(file_path=file_path, filename="broken.pdf")

    assert source.status == "error"
    assert "parse exploded" in (source.error or "")
    assert await repo.get_chunks(source.id) == []


@pytest.mark.asyncio
async def test_seekdb_repository_persists_sources_after_restart(tmp_path: Path):
    db_path = tmp_path / "knowledge.db"
    repo = SeekDBRepository(db_path, native_chunk_index=None, allow_sqlite_vector_fallback=True)
    service = SourceService(repository=repo, parser=DoclingParser(), chunk_size=40, chunk_overlap=0)

    created = await service.create_text_source("Durable", "Persistent source text for restart.")
    await repo.close()

    reopened = SeekDBRepository(db_path, native_chunk_index=None, allow_sqlite_vector_fallback=True)
    loaded = await reopened.get_source(created.id)
    chunks = await reopened.get_chunks(created.id)

    assert loaded is not None
    assert loaded.id == created.id
    assert loaded.title == "Durable"
    assert chunks[0].content.startswith("Persistent source")


@pytest.mark.asyncio
async def test_delete_source_removes_chunks_from_retrieval(tmp_path: Path):
    repo = SeekDBRepository(tmp_path / "knowledge.db", native_chunk_index=None, allow_sqlite_vector_fallback=True)
    service = SourceService(repository=repo, parser=DoclingParser(), chunk_size=64, chunk_overlap=0)

    source = await service.create_text_source("Delete me", "Needle phrase should disappear.")
    before = await repo.search_chunks("Needle", source_ids=[source.id], top_k=3)
    deleted = await service.delete_source(source.id)
    after = await repo.search_chunks("Needle", source_ids=[source.id], top_k=3)

    assert before
    assert deleted is True
    assert after == []


def test_sources_api_text_upload_list_get_delete(tmp_path: Path):
    repo = SeekDBRepository(tmp_path / "api.db", native_chunk_index=None, allow_sqlite_vector_fallback=True)
    service = SourceService(repository=repo, parser=DoclingParser(), chunk_size=64, chunk_overlap=0)
    app = FastAPI()
    app.include_router(sources_router, prefix="/api")
    app.dependency_overrides[get_source_service] = lambda: service

    client = TestClient(app)

    created = client.post(
        "/api/sources/text",
        json={"title": "API source", "text": "API source content with citation material."},
    )
    assert created.status_code == 200
    source_id = created.json()["id"]

    listed = client.get("/api/sources")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    detail = client.get(f"/api/sources/{source_id}")
    assert detail.status_code == 200
    assert detail.json()["text"].startswith("API source content")

    deleted = client.delete(f"/api/sources/{source_id}")
    assert deleted.status_code == 200
    assert deleted.json()["success"] is True

    missing = client.get(f"/api/sources/{source_id}")
    assert missing.status_code == 404


def test_sources_api_rejects_strict_seekdb_ingestion_without_embeddings(tmp_path: Path):
    repo = SeekDBRepository(
        tmp_path / "strict-api.db",
        native_chunk_index=RecordingNativeIndex(),
        allow_sqlite_vector_fallback=False,
    )
    service = SourceService(repository=repo, parser=DoclingParser(), chunk_size=64, chunk_overlap=0)
    app = FastAPI()
    app.include_router(sources_router, prefix="/api")
    app.dependency_overrides[get_source_service] = lambda: service

    response = TestClient(app).post(
        "/api/sources/text",
        json={"title": "Missing embeddings", "text": "This source requires vectors."},
    )

    assert response.status_code == 422
    assert "require embeddings" in response.json()["detail"]


def test_sources_api_file_upload_text_fallback(tmp_path: Path):
    repo = SeekDBRepository(tmp_path / "upload.db", native_chunk_index=None, allow_sqlite_vector_fallback=True)
    service = SourceService(repository=repo, parser=DoclingParser(), chunk_size=64, chunk_overlap=0)
    app = FastAPI()
    app.include_router(sources_router, prefix="/api")
    app.dependency_overrides[get_source_service] = lambda: service
    app.dependency_overrides[get_settings] = lambda: Settings(upload_dir=str(tmp_path / "uploads"))

    client = TestClient(app)
    response = client.post(
        "/api/sources/upload",
        files={"file": ("notes.txt", b"Uploaded plain text source.", "text/plain")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["filename"] == "notes.txt"
    assert payload["status"] == "ready"
    assert payload["chunk_count"] == 1


@pytest.mark.asyncio
async def test_docling_parser_offloads_blocking_conversion(monkeypatch, tmp_path: Path):
    main_thread = threading.get_ident()
    called: dict[str, int] = {}

    accelerator_module = ModuleType("docling.datamodel.accelerator_options")
    accelerator_module.AcceleratorOptions = lambda device: SimpleNamespace(device=device)
    base_models_module = ModuleType("docling.datamodel.base_models")
    base_models_module.InputFormat = SimpleNamespace(PDF="pdf")
    pipeline_module = ModuleType("docling.datamodel.pipeline_options")
    pipeline_module.PdfPipelineOptions = lambda accelerator_options: SimpleNamespace(
        accelerator_options=accelerator_options
    )
    converter_module = ModuleType("docling.document_converter")

    class PdfFormatOption:
        def __init__(self, pipeline_options):
            self.pipeline_options = pipeline_options

    class DocumentConverter:
        def __init__(self, format_options):
            self.format_options = format_options

        def convert(self, path: str):
            called["thread"] = threading.get_ident()

            class Document:
                def export_to_markdown(self):
                    return "# Parsed PDF"

            return SimpleNamespace(document=Document())

    converter_module.DocumentConverter = DocumentConverter
    converter_module.PdfFormatOption = PdfFormatOption

    monkeypatch.setitem(sys.modules, "docling.datamodel.accelerator_options", accelerator_module)
    monkeypatch.setitem(sys.modules, "docling.datamodel.base_models", base_models_module)
    monkeypatch.setitem(sys.modules, "docling.datamodel.pipeline_options", pipeline_module)
    monkeypatch.setitem(sys.modules, "docling.document_converter", converter_module)

    file_path = tmp_path / "paper.pdf"
    file_path.write_bytes(b"%PDF-1.4")

    parsed = await DoclingParser().parse_file(file_path, filename="paper.pdf")

    assert parsed["content"] == "# Parsed PDF"
    assert called["thread"] != main_thread
