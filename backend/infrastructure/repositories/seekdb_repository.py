"""SQLite entity repository with a native SeekDB knowledge-chunk index.

In strict mode, SeekDB owns chunk vectors and retrieval. SQLite keeps source and
chunk metadata without embeddings. SQLite vector scoring is retained only for
the explicitly enabled compatibility fallback.
"""

from __future__ import annotations

import json
import logging
import math
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from ...core.interfaces.knowledge_repository import KnowledgeRepositoryInterface
from ...domain.slide_deck import SlideAsset, SlideDeckExport, SlideDeckJob, SlideDeckProject
from ...domain.source import Artifact, Job, KnowledgeChunk, KnowledgeSource, Note, SourceStatus, utc_now
from ..vector_stores.seekdb_chunk_index import SeekDBChunkIndex

logger = logging.getLogger(__name__)

_AUTO_NATIVE_INDEX: Any = object()
_NATIVE_UNAVAILABLE_MESSAGE = (
    "native SeekDB vector index is unavailable; enable seekdb_allow_sqlite_fallback for SQLite fallback"
)


def _dump_model(model: Any) -> str:
    return model.model_dump_json()


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)


def _tokens(text: str) -> list[str]:
    return re.findall(r"[\u4e00-\u9fff]|[a-z0-9]+", text.lower())


def _bm25_scores(query: str, documents: list[str]) -> list[float]:
    query_terms = _tokens(query)
    if not query_terms or not documents:
        return [0.0 for _ in documents]

    tokenized_docs = [_tokens(document) for document in documents]
    doc_count = len(tokenized_docs)
    avg_len = sum(len(tokens) for tokens in tokenized_docs) / doc_count if doc_count else 0.0
    if avg_len == 0:
        return [0.0 for _ in documents]

    doc_freq: dict[str, int] = {}
    for tokens in tokenized_docs:
        for term in set(tokens):
            doc_freq[term] = doc_freq.get(term, 0) + 1

    k1 = 1.5
    b = 0.75
    scores: list[float] = []
    for tokens in tokenized_docs:
        length = len(tokens)
        term_freq: dict[str, int] = {}
        for token in tokens:
            term_freq[token] = term_freq.get(token, 0) + 1

        score = 0.0
        for term in query_terms:
            freq = term_freq.get(term, 0)
            if not freq:
                continue
            idf = math.log(1 + (doc_count - doc_freq.get(term, 0) + 0.5) / (doc_freq.get(term, 0) + 0.5))
            denominator = freq + k1 * (1 - b + b * length / avg_len)
            score += idf * (freq * (k1 + 1)) / denominator
        scores.append(score)
    return scores


class SeekDBRepository(KnowledgeRepositoryInterface):
    def __init__(
        self,
        db_path: str | Path,
        native_chunk_index: object = _AUTO_NATIVE_INDEX,
        allow_sqlite_vector_fallback: bool = False,
        embedding_profile_id: str | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.seekdb_path = self.db_path.parent / f"{self.db_path.stem}.seekdb"
        self.allow_sqlite_vector_fallback = allow_sqlite_vector_fallback
        self.embedding_profile_id = embedding_profile_id
        self.native_chunk_index = (
            self._try_native_chunk_index(self.seekdb_path)
            if native_chunk_index is _AUTO_NATIVE_INDEX
            else native_chunk_index
        )
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()
        self._storage_initialized = False
        self._migration_has_unresolved_sources = False
        self._closed = False

    def _try_native_chunk_index(self, path: Path) -> Any | None:
        try:
            return SeekDBChunkIndex(path)
        except Exception as exc:
            if not self.allow_sqlite_vector_fallback:
                logger.warning("Native SeekDB vector index is unavailable: %s", exc)
            return None

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sources (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                content TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                embedding TEXT,
                vector_state TEXT NOT NULL DEFAULT 'legacy',
                payload TEXT NOT NULL,
                FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_chunks_source_id ON chunks(source_id);
            CREATE TABLE IF NOT EXISTS chunk_index_state (
                source_id TEXT PRIMARY KEY,
                revision TEXT NOT NULL,
                chunk_count INTEGER NOT NULL,
                embedding_dimension INTEGER,
                embedding_profile TEXT,
                storage_mode TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS chunk_sync_operations (
                source_id TEXT PRIMARY KEY,
                revision TEXT NOT NULL,
                operation TEXT NOT NULL,
                payload TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS repository_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS artifacts (
                id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS notes (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS slide_decks (
                id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS slide_assets (
                id TEXT PRIMARY KEY,
                deck_id TEXT NOT NULL,
                slide_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_slide_assets_deck_id ON slide_assets(deck_id);
            CREATE TABLE IF NOT EXISTS slide_exports (
                id TEXT PRIMARY KEY,
                deck_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_slide_exports_deck_id ON slide_exports(deck_id);
            CREATE TABLE IF NOT EXISTS slide_deck_jobs (
                id TEXT PRIMARY KEY,
                deck_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_slide_deck_jobs_deck_id ON slide_deck_jobs(deck_id);
            """
        )
        chunk_columns = {
            row["name"] for row in self._conn.execute("PRAGMA table_info(chunks)").fetchall()
        }
        if "vector_state" not in chunk_columns:
            self._conn.execute(
                "ALTER TABLE chunks ADD COLUMN vector_state TEXT NOT NULL DEFAULT 'legacy'"
            )
        state_columns = {
            row["name"] for row in self._conn.execute("PRAGMA table_info(chunk_index_state)").fetchall()
        }
        if "embedding_profile" not in state_columns:
            self._conn.execute("ALTER TABLE chunk_index_state ADD COLUMN embedding_profile TEXT")
            if self.embedding_profile_id:
                self._conn.execute(
                    """
                    UPDATE chunk_index_state
                    SET embedding_profile = ?
                    WHERE embedding_profile IS NULL AND storage_mode = 'seekdb'
                    """,
                    (self.embedding_profile_id,),
                )
        self._conn.commit()

    async def close(self) -> None:
        self.close_sync()

    def close_sync(self) -> None:
        if self._closed:
            return
        try:
            close_native = getattr(self.native_chunk_index, "close", None)
            if callable(close_native):
                close_native()
        finally:
            self._conn.close()
        self._closed = True

    def storage_status(self) -> dict[str, Any]:
        if self.native_chunk_index is not None:
            try:
                probe_native = getattr(self.native_chunk_index, "probe", None)
                if callable(probe_native):
                    probe_native()
                status = dict(self.native_chunk_index.status())
                status.setdefault("seekdb_path", str(self.seekdb_path))
                status.setdefault("native_available", True)
                return status
            except Exception as exc:
                return {
                    "vector_backend": (
                        "sqlite_fallback" if self.allow_sqlite_vector_fallback else "unavailable"
                    ),
                    "seekdb_path": str(self.seekdb_path),
                    "native_available": False,
                    "error": str(exc),
                }
        return {
            "vector_backend": "sqlite_fallback" if self.allow_sqlite_vector_fallback else "unavailable",
            "seekdb_path": str(self.seekdb_path),
            "native_available": False,
        }

    async def save_source(self, source: KnowledgeSource) -> KnowledgeSource:
        self._conn.execute(
            """
            INSERT INTO sources(id, status, payload, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status=excluded.status,
                payload=excluded.payload,
                updated_at=excluded.updated_at
            """,
            (
                source.id,
                source.status.value,
                _dump_model(source),
                source.created_at.isoformat(),
                source.updated_at.isoformat(),
            ),
        )
        self._conn.commit()
        return source

    async def get_source(self, source_id: str) -> KnowledgeSource | None:
        row = self._conn.execute("SELECT payload FROM sources WHERE id = ?", (source_id,)).fetchone()
        return KnowledgeSource.model_validate_json(row["payload"]) if row else None

    async def list_sources(self) -> list[KnowledgeSource]:
        rows = self._conn.execute(
            "SELECT payload FROM sources WHERE status != ? ORDER BY created_at DESC",
            (SourceStatus.DELETED.value,),
        ).fetchall()
        return [KnowledgeSource.model_validate_json(row["payload"]) for row in rows]

    async def delete_source(self, source_id: str) -> bool:
        if self.native_chunk_index is None and not self.allow_sqlite_vector_fallback:
            raise RuntimeError(_NATIVE_UNAVAILABLE_MESSAGE)

        await self._ensure_storage_initialized()

        if self.native_chunk_index is None:
            with self._conn:
                self._conn.execute("DELETE FROM chunks WHERE source_id = ?", (source_id,))
                self._conn.execute("DELETE FROM chunk_index_state WHERE source_id = ?", (source_id,))
                self._conn.execute("DELETE FROM sources WHERE id = ?", (source_id,))
            return True

        previous_native_chunks: list[KnowledgeChunk] | None = None
        get_native_chunks = getattr(self.native_chunk_index, "get_source_chunks", None)
        if callable(get_native_chunks):
            previous_native_chunks = get_native_chunks(source_id)
        revision = uuid4().hex
        self._record_sync_operation(source_id, revision, "delete", None)
        try:
            self.native_chunk_index.upsert_source_chunks(source_id, [])
            self._finalize_source_delete(source_id, revision)
        except Exception:
            self._compensate_native_failure(source_id, revision, previous_native_chunks)
            raise
        return True

    async def delete_source_metadata_only(self, source_id: str) -> None:
        """Rollback local metadata without touching native SeekDB."""
        with self._conn:
            self._conn.execute("DELETE FROM chunks WHERE source_id = ?", (source_id,))
            self._conn.execute("DELETE FROM chunk_index_state WHERE source_id = ?", (source_id,))
            self._conn.execute("DELETE FROM chunk_sync_operations WHERE source_id = ?", (source_id,))
            self._conn.execute("DELETE FROM sources WHERE id = ?", (source_id,))

    async def save_chunks(self, source_id: str, chunks: list[KnowledgeChunk]) -> None:
        if self.native_chunk_index is None and not self.allow_sqlite_vector_fallback:
            raise RuntimeError(_NATIVE_UNAVAILABLE_MESSAGE)

        if self.native_chunk_index is not None and chunks and not self.allow_sqlite_vector_fallback:
            missing_embeddings = [chunk.id for chunk in chunks if not chunk.embedding]
            if missing_embeddings:
                raise RuntimeError(
                    "native SeekDB chunk writes require embeddings for all chunks; "
                    f"missing embeddings for: {', '.join(missing_embeddings)}"
                )
            native_eligible_chunks = self._native_eligible_chunks(chunks)
            if len(native_eligible_chunks) != len(chunks):
                raise RuntimeError("native SeekDB chunk writes require same-dimension embeddings for all chunks")

        await self._ensure_storage_initialized()

        if self.native_chunk_index is None:
            with self._conn:
                self._replace_sqlite_chunks(source_id, chunks, persist_embedding=True)
                self._upsert_chunk_index_state(
                    source_id,
                    uuid4().hex,
                    chunks,
                    storage_mode="sqlite_fallback",
                )
            return

        native_chunks = self._native_eligible_chunks(chunks)
        previous_native_chunks: list[KnowledgeChunk] | None = None
        get_native_chunks = getattr(self.native_chunk_index, "get_source_chunks", None)
        if callable(get_native_chunks):
            previous_native_chunks = get_native_chunks(source_id)
        revision = uuid4().hex
        persist_embedding = self.allow_sqlite_vector_fallback
        self._record_sync_operation(
            source_id,
            revision,
            "replace",
            self._replacement_operation_payload(chunks, persist_embedding),
        )

        try:
            self.native_chunk_index.upsert_source_chunks(source_id, native_chunks)
            self._finalize_chunk_replace(
                source_id,
                revision,
                chunks,
                persist_embedding=persist_embedding,
            )
        except Exception:
            self._compensate_native_failure(source_id, revision, previous_native_chunks)
            raise

    async def get_chunks(self, source_id: str) -> list[KnowledgeChunk]:
        await self._ensure_storage_initialized()
        state = self._chunk_index_states([source_id]).get(source_id)
        if state is not None and state["storage_mode"] == "sqlite_legacy":
            return self._get_sqlite_chunks_sync(source_id)
        if self.native_chunk_index is not None:
            get_native_chunks = getattr(self.native_chunk_index, "get_source_chunks", None)
            if callable(get_native_chunks):
                try:
                    chunks = get_native_chunks(source_id)
                    if chunks or not self.allow_sqlite_vector_fallback:
                        return chunks
                except Exception:
                    if not self.allow_sqlite_vector_fallback:
                        raise
        if not self.allow_sqlite_vector_fallback:
            raise RuntimeError(_NATIVE_UNAVAILABLE_MESSAGE)
        return self._get_sqlite_chunks_sync(source_id)

    async def backfill_native_chunks(self) -> int:
        if self.native_chunk_index is None:
            if self.allow_sqlite_vector_fallback:
                return 0
            raise RuntimeError("native SeekDB vector index is unavailable; cannot backfill chunks")

        probe_native = getattr(self.native_chunk_index, "probe", None)
        if callable(probe_native):
            probe_native()
        self._recover_pending_sync_operations()
        written = self._backfill_native_chunks_sync()
        if not self.allow_sqlite_vector_fallback and not self._migration_has_unresolved_sources:
            self._set_repository_meta("native_chunk_migration_v2", "complete")
        self._reconcile_processing_sources()
        self._storage_initialized = True
        return written

    async def initialize_storage(self) -> int:
        """Recover interrupted writes and migrate legacy SQLite vectors into SeekDB."""
        if self._storage_initialized:
            return 0
        if self.native_chunk_index is None:
            if self.allow_sqlite_vector_fallback:
                self._reconcile_processing_sources()
                self._storage_initialized = True
            return 0
        probe_native = getattr(self.native_chunk_index, "probe", None)
        if callable(probe_native):
            probe_native()
        self._recover_pending_sync_operations()
        written = 0
        if (
            not self.allow_sqlite_vector_fallback
            and self._get_repository_meta("native_chunk_migration_v2") != "complete"
        ):
            written = self._backfill_native_chunks_sync()
            if not self._migration_has_unresolved_sources:
                self._set_repository_meta("native_chunk_migration_v2", "complete")
        self._reconcile_processing_sources()
        self._storage_initialized = True
        return written

    async def _ensure_storage_initialized(self) -> None:
        if not self._storage_initialized:
            await self.initialize_storage()

    def _backfill_native_chunks_sync(self) -> int:
        written = 0
        self._migration_has_unresolved_sources = False
        source_rows = self._conn.execute(
            "SELECT payload FROM sources WHERE status != ? ORDER BY created_at DESC",
            (SourceStatus.DELETED.value,),
        ).fetchall()
        sources = [KnowledgeSource.model_validate_json(row["payload"]) for row in source_rows]
        reconciled_states = {"seekdb"}
        if self.allow_sqlite_vector_fallback:
            reconciled_states.add("sqlite_fallback_reconciled")
        reconciled_placeholders = ",".join("?" for _ in reconciled_states)
        for source in sources:
            state_row = self._conn.execute(
                "SELECT source_id FROM chunk_index_state WHERE source_id = ?",
                (source.id,),
            ).fetchone()
            if state_row:
                unreconciled_row = self._conn.execute(
                    f"""
                    SELECT 1
                    FROM chunks
                    WHERE source_id = ?
                      AND vector_state NOT IN ({reconciled_placeholders})
                    LIMIT 1
                    """,
                    (source.id, *reconciled_states),
                ).fetchone()
                if unreconciled_row is None:
                    continue
            sqlite_rows = self._conn.execute(
                "SELECT payload, vector_state FROM chunks WHERE source_id = ? ORDER BY chunk_index ASC",
                (source.id,),
            ).fetchall()
            chunks = [KnowledgeChunk.model_validate_json(row["payload"]) for row in sqlite_rows]
            if not chunks:
                with self._conn:
                    self._upsert_chunk_index_state(
                        source.id,
                        uuid4().hex,
                        [],
                        storage_mode="seekdb",
                    )
                continue
            if state_row and all(row["vector_state"] in reconciled_states for row in sqlite_rows):
                continue
            if state_row and all(row["vector_state"] == "legacy_needs_embedding" for row in sqlite_rows):
                self._migration_has_unresolved_sources = True
                continue
            chunks_with_embeddings = self._native_eligible_chunks(chunks)
            get_native_chunks = getattr(self.native_chunk_index, "get_source_chunks", None)
            previous_native_chunks = get_native_chunks(source.id) if callable(get_native_chunks) else None
            if len(chunks_with_embeddings) != len(chunks):
                if all(row["vector_state"] in {"legacy", "seekdb"} for row in sqlite_rows) and self._chunks_match_without_vectors(
                    chunks,
                    previous_native_chunks or [],
                ):
                    with self._conn:
                        self._conn.execute(
                            "UPDATE chunks SET vector_state = 'seekdb' WHERE source_id = ?",
                            (source.id,),
                        )
                        self._upsert_chunk_index_state(
                            source.id,
                            uuid4().hex,
                            previous_native_chunks or [],
                            storage_mode="seekdb",
                        )
                    continue
                logger.warning(
                    "Legacy source %s has missing or inconsistent embeddings",
                    source.id,
                )
                revision = uuid4().hex
                if not self.allow_sqlite_vector_fallback:
                    self._migration_has_unresolved_sources = True
                    self._record_sync_operation(source.id, revision, "legacy_clear", None)
                    try:
                        self.native_chunk_index.upsert_source_chunks(source.id, [])
                        self._finalize_legacy_source(source.id, revision, chunks)
                    except Exception:
                        self._compensate_native_failure(source.id, revision, previous_native_chunks)
                        raise
                    continue
                self._record_sync_operation(
                    source.id,
                    revision,
                    "replace",
                    self._replacement_operation_payload(chunks, persist_embedding=True),
                )
                try:
                    self.native_chunk_index.upsert_source_chunks(source.id, [])
                    self._finalize_chunk_replace(
                        source.id,
                        revision,
                        chunks,
                        persist_embedding=True,
                        storage_mode="sqlite_fallback",
                        vector_state="sqlite_fallback_reconciled",
                    )
                except Exception:
                    self._compensate_native_failure(source.id, revision, previous_native_chunks)
                    raise
                continue
            revision = uuid4().hex
            persist_embedding = self.allow_sqlite_vector_fallback
            finalize_mode = "replace" if persist_embedding else "scrub"
            self._record_sync_operation(
                source.id,
                revision,
                "replace",
                self._replacement_operation_payload(
                    chunks,
                    persist_embedding,
                    finalize_mode=finalize_mode,
                ),
            )
            try:
                self.native_chunk_index.upsert_source_chunks(source.id, chunks_with_embeddings)
                if finalize_mode == "scrub":
                    self._finalize_chunk_migration(source.id, revision, chunks)
                else:
                    self._finalize_chunk_replace(
                        source.id,
                        revision,
                        chunks,
                        persist_embedding=persist_embedding,
                    )
            except Exception:
                self._compensate_native_failure(source.id, revision, previous_native_chunks)
                raise
            written += len(chunks_with_embeddings)
        return written

    async def search_chunks(
        self,
        query: str,
        source_ids: list[str] | None = None,
        top_k: int = 5,
        query_embedding: list[float] | None = None,
        rerank_provider: object | None = None,
    ) -> list[dict]:
        if source_ids == []:
            return []
        await self._ensure_storage_initialized()
        if self.native_chunk_index is not None and query_embedding is None:
            query_text = query.strip()
            if not query_text:
                raise RuntimeError("native SeekDB full-text search requires query text")
            requested_source_ids = source_ids if source_ids is not None else self._current_source_ids()
            selected_source_ids = self._native_source_ids_with_chunks(requested_source_ids)
            text_search = getattr(self.native_chunk_index, "text_search", None)
            results: list[dict] = []
            if not callable(text_search):
                if not self.allow_sqlite_vector_fallback:
                    raise RuntimeError("native SeekDB full-text search is unavailable")
                selected_source_ids = []
            elif selected_source_ids:
                try:
                    results.extend(text_search(query_text, selected_source_ids, top_k))
                except Exception:
                    if not self.allow_sqlite_vector_fallback:
                        raise
                    selected_source_ids = []
            if self.allow_sqlite_vector_fallback:
                native_source_id_set = set(selected_source_ids)
                fallback_source_ids = [
                    source_id for source_id in requested_source_ids if source_id not in native_source_id_set
                ]
                if fallback_source_ids:
                    results.extend(
                        await self._search_sqlite_chunk_rows(
                            query,
                            self._chunk_rows(fallback_source_ids),
                            top_k,
                            None,
                            None,
                        )
                    )
            else:
                legacy_source_ids = self._legacy_source_ids(requested_source_ids)
                if legacy_source_ids:
                    legacy_results = await self._search_sqlite_chunk_rows(
                        query,
                        self._chunk_rows(legacy_source_ids),
                        top_k,
                        None,
                        None,
                    )
                    for result in legacy_results:
                        result["backend"] = "sqlite_legacy_text"
                    results.extend(legacy_results)
            results = sorted(results, key=lambda item: item["score"], reverse=True)[:top_k]
            return await self._maybe_rerank(query_text, results, top_k, rerank_provider)
        if self.native_chunk_index is not None and query_embedding is not None:
            if not query_embedding:
                if self.allow_sqlite_vector_fallback:
                    rows = self._chunk_rows(source_ids)
                    return await self._search_sqlite_chunk_rows(query, rows, top_k, None, rerank_provider)
                raise RuntimeError("native SeekDB vector search requires a non-empty query embedding")
            requested_source_ids = source_ids if source_ids is not None else self._current_source_ids()
            selected_source_ids = self._native_search_source_ids(requested_source_ids, query_embedding)
            results: list[dict] = []
            hybrid_search = getattr(self.native_chunk_index, "hybrid_search", None)
            if selected_source_ids:
                try:
                    if callable(hybrid_search):
                        results.extend(
                            hybrid_search(
                                query_text=query,
                                query_embedding=query_embedding,
                                source_ids=selected_source_ids,
                                top_k=top_k,
                            )
                        )
                    else:
                        results.extend(self.native_chunk_index.search(query_embedding, selected_source_ids, top_k))
                except Exception:
                    if not self.allow_sqlite_vector_fallback:
                        raise
                    selected_source_ids = []
            if self.allow_sqlite_vector_fallback:
                native_source_id_set = set(selected_source_ids)
                fallback_source_ids = [
                    source_id for source_id in requested_source_ids if source_id not in native_source_id_set
                ]
                if fallback_source_ids:
                    fallback_query_embedding = (
                        None
                        if self._has_embedding_profile_mismatch(fallback_source_ids)
                        else query_embedding
                    )
                    fallback_results = await self._search_sqlite_chunk_rows(
                        query,
                        self._chunk_rows(fallback_source_ids),
                        top_k,
                        fallback_query_embedding,
                        None,
                    )
                    results.extend(fallback_results)
            else:
                legacy_source_ids = self._legacy_source_ids(requested_source_ids)
                if legacy_source_ids:
                    legacy_results = await self._search_sqlite_chunk_rows(
                        query,
                        self._chunk_rows(legacy_source_ids),
                        top_k,
                        None,
                        None,
                    )
                    for result in legacy_results:
                        result["backend"] = "sqlite_legacy_text"
                    results.extend(legacy_results)
            results = sorted(results, key=lambda item: item["score"], reverse=True)[:top_k]
            return await self._maybe_rerank(query, results, top_k, rerank_provider)

        if self.native_chunk_index is None and not self.allow_sqlite_vector_fallback:
            raise RuntimeError(_NATIVE_UNAVAILABLE_MESSAGE)

        rows = self._chunk_rows(source_ids)
        return await self._search_sqlite_chunk_rows(query, rows, top_k, query_embedding, rerank_provider)

    def _current_source_ids(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT id FROM sources WHERE status != ? ORDER BY created_at DESC",
            (SourceStatus.DELETED.value,),
        ).fetchall()
        return [row["id"] for row in rows]

    @staticmethod
    def _native_eligible_chunks(chunks: list[KnowledgeChunk]) -> list[KnowledgeChunk]:
        if not chunks:
            return []
        dimension: int | None = None
        for chunk in chunks:
            if not chunk.embedding:
                return []
            if dimension is None:
                dimension = len(chunk.embedding)
            elif len(chunk.embedding) != dimension:
                return []
        return chunks

    def _native_search_source_ids(self, source_ids: list[str], query_embedding: list[float]) -> list[str]:
        if not source_ids:
            return []
        query_dimension = len(query_embedding)
        states = self._chunk_index_states(source_ids)
        seekdb_states = {
            source_id: states[source_id]
            for source_id in source_ids
            if source_id in states
            and states[source_id]["storage_mode"] == "seekdb"
            and states[source_id]["chunk_count"] > 0
        }
        if not self.allow_sqlite_vector_fallback:
            profile_mismatches = [
                source_id
                for source_id, state in seekdb_states.items()
                if self.embedding_profile_id
                and state["embedding_profile"]
                and state["embedding_profile"] != self.embedding_profile_id
            ]
            if profile_mismatches:
                raise RuntimeError(
                    "Selected sources were indexed with a different embedding profile; "
                    "re-index the sources before vector retrieval: "
                    + ", ".join(profile_mismatches)
                )
            dimension_mismatches = [
                source_id
                for source_id, state in seekdb_states.items()
                if state["embedding_dimension"] != query_dimension
            ]
            if dimension_mismatches:
                raise RuntimeError(
                    "Selected sources use an incompatible embedding dimension; "
                    "re-index the sources before vector retrieval: "
                    + ", ".join(dimension_mismatches)
                )
        return [
            source_id
            for source_id, state in seekdb_states.items()
            if state["embedding_dimension"] == query_dimension
            and (
                not self.embedding_profile_id
                or not state["embedding_profile"]
                or state["embedding_profile"] == self.embedding_profile_id
            )
        ]

    def _native_source_ids_with_chunks(self, source_ids: list[str]) -> list[str]:
        states = self._chunk_index_states(source_ids)
        return [
            source_id
            for source_id in source_ids
            if source_id in states
            and states[source_id]["storage_mode"] == "seekdb"
            and states[source_id]["chunk_count"] > 0
        ]

    def _legacy_source_ids(self, source_ids: list[str]) -> list[str]:
        states = self._chunk_index_states(source_ids)
        return [
            source_id
            for source_id in source_ids
            if source_id in states
            and states[source_id]["storage_mode"] == "sqlite_legacy"
            and states[source_id]["chunk_count"] > 0
        ]

    def _has_embedding_profile_mismatch(self, source_ids: list[str]) -> bool:
        if not self.embedding_profile_id:
            return False
        states = self._chunk_index_states(source_ids)
        return any(
            state["embedding_profile"]
            and state["embedding_profile"] != self.embedding_profile_id
            for state in states.values()
        )

    def indexed_vector_chunk_count(self) -> int:
        row = self._conn.execute(
            """
            SELECT COALESCE(SUM(chunk_count), 0) AS total
            FROM chunk_index_state
            WHERE storage_mode = 'seekdb'
            """
        ).fetchone()
        return int(row["total"])

    def _reconcile_processing_sources(self) -> int:
        rows = self._conn.execute(
            """
            SELECT sources.payload, chunk_index_state.chunk_count AS indexed_chunk_count
            FROM sources
            JOIN chunk_index_state ON chunk_index_state.source_id = sources.id
            WHERE sources.status = ?
            """,
            (SourceStatus.PROCESSING.value,),
        ).fetchall()
        recovered = 0
        with self._conn:
            for row in rows:
                source = KnowledgeSource.model_validate_json(row["payload"])
                if not source.text or source.chunk_count != row["indexed_chunk_count"]:
                    continue
                source.status = SourceStatus.READY
                source.error = None
                source.updated_at = utc_now()
                self._conn.execute(
                    """
                    UPDATE sources
                    SET status = ?, payload = ?, updated_at = ?
                    WHERE id = ? AND status = ?
                    """,
                    (
                        source.status.value,
                        _dump_model(source),
                        source.updated_at.isoformat(),
                        source.id,
                        SourceStatus.PROCESSING.value,
                    ),
                )
                recovered += 1
        return recovered

    def _record_sync_operation(
        self,
        source_id: str,
        revision: str,
        operation: str,
        payload: str | None,
    ) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO chunk_sync_operations(source_id, revision, operation, payload, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    revision=excluded.revision,
                    operation=excluded.operation,
                    payload=excluded.payload,
                    created_at=excluded.created_at
                """,
                (source_id, revision, operation, payload, datetime.now(timezone.utc).isoformat()),
            )

    def _discard_sync_operation(self, source_id: str, revision: str) -> None:
        try:
            with self._conn:
                self._conn.execute(
                    "DELETE FROM chunk_sync_operations WHERE source_id = ? AND revision = ?",
                    (source_id, revision),
                )
        except Exception:
            logger.exception("Failed to discard completed chunk sync operation for %s", source_id)

    def _compensate_native_failure(
        self,
        source_id: str,
        revision: str,
        previous_native_chunks: list[KnowledgeChunk] | None,
    ) -> None:
        if previous_native_chunks is None:
            logger.error(
                "Cannot restore SeekDB source %s because its previous state is unavailable; "
                "the original sync operation remains pending",
                source_id,
            )
            return
        try:
            self._record_sync_operation(
                source_id,
                revision,
                "native_restore",
                json.dumps([chunk.model_dump_json() for chunk in previous_native_chunks]),
            )
        except Exception:
            logger.exception(
                "Failed to persist native restore operation for %s; original operation remains pending",
                source_id,
            )
            return
        try:
            self.native_chunk_index.upsert_source_chunks(source_id, previous_native_chunks)
        except Exception:
            logger.exception("Failed to restore SeekDB chunks for %s; restore remains pending", source_id)
            return
        self._discard_sync_operation(source_id, revision)

    @staticmethod
    def _replacement_operation_payload(
        chunks: list[KnowledgeChunk],
        persist_embedding: bool,
        *,
        finalize_mode: str = "replace",
    ) -> str:
        return json.dumps(
            {
                "chunks": [chunk.model_dump_json() for chunk in chunks],
                "persist_embedding": persist_embedding,
                "finalize_mode": finalize_mode,
            }
        )

    @staticmethod
    def _load_replacement_operation(payload: str | None) -> tuple[list[KnowledgeChunk], bool, str]:
        if payload is None:
            raise ValueError("replace operation is missing its payload")
        value = json.loads(payload)
        chunks = [KnowledgeChunk.model_validate_json(item) for item in value.get("chunks", [])]
        return chunks, bool(value.get("persist_embedding", False)), value.get("finalize_mode", "replace")

    def _recover_pending_sync_operations(self) -> None:
        if self.native_chunk_index is None:
            return
        rows = self._conn.execute(
            """
            SELECT source_id, revision, operation, payload
            FROM chunk_sync_operations
            ORDER BY created_at ASC
            """
        ).fetchall()
        for row in rows:
            source_id = row["source_id"]
            revision = row["revision"]
            if row["operation"] == "replace":
                chunks, persist_embedding, finalize_mode = self._load_replacement_operation(row["payload"])
                self.native_chunk_index.upsert_source_chunks(
                    source_id,
                    self._native_eligible_chunks(chunks),
                )
                if finalize_mode == "scrub":
                    self._finalize_chunk_migration(source_id, revision, chunks)
                else:
                    self._finalize_chunk_replace(
                        source_id,
                        revision,
                        chunks,
                        persist_embedding=persist_embedding,
                    )
            elif row["operation"] == "delete":
                self.native_chunk_index.upsert_source_chunks(source_id, [])
                self._finalize_source_delete(source_id, revision)
            elif row["operation"] == "native_restore":
                payload = json.loads(row["payload"] or "[]")
                chunks = [KnowledgeChunk.model_validate_json(item) for item in payload]
                self.native_chunk_index.upsert_source_chunks(source_id, chunks)
                self._discard_sync_operation(source_id, revision)
            elif row["operation"] == "legacy_clear":
                chunks = self._get_sqlite_chunks_sync(source_id)
                self.native_chunk_index.upsert_source_chunks(source_id, [])
                self._finalize_legacy_source(source_id, revision, chunks)
            else:
                raise ValueError(f"Unknown chunk sync operation: {row['operation']}")

    def _finalize_chunk_replace(
        self,
        source_id: str,
        revision: str,
        chunks: list[KnowledgeChunk],
        *,
        persist_embedding: bool,
        storage_mode: str | None = None,
        vector_state: str | None = None,
    ) -> None:
        eligible_chunks = self._native_eligible_chunks(chunks)
        resolved_storage_mode = storage_mode or (
            "seekdb" if not chunks or len(eligible_chunks) == len(chunks) else "sqlite_fallback"
        )
        with self._conn:
            self._replace_sqlite_chunks(
                source_id,
                chunks,
                persist_embedding=persist_embedding,
                vector_state=vector_state,
            )
            self._upsert_chunk_index_state(
                source_id,
                revision,
                eligible_chunks if resolved_storage_mode == "seekdb" else chunks,
                storage_mode=resolved_storage_mode,
            )
            self._conn.execute(
                "DELETE FROM chunk_sync_operations WHERE source_id = ? AND revision = ?",
                (source_id, revision),
            )

    def _finalize_source_delete(self, source_id: str, revision: str) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM chunks WHERE source_id = ?", (source_id,))
            self._conn.execute("DELETE FROM chunk_index_state WHERE source_id = ?", (source_id,))
            self._conn.execute("DELETE FROM sources WHERE id = ?", (source_id,))
            self._conn.execute(
                "DELETE FROM chunk_sync_operations WHERE source_id = ? AND revision = ?",
                (source_id, revision),
            )

    def _finalize_chunk_migration(
        self,
        source_id: str,
        revision: str,
        chunks: list[KnowledgeChunk],
    ) -> None:
        with self._conn:
            for chunk in chunks:
                self._conn.execute(
                    """
                    UPDATE chunks
                    SET embedding = NULL, payload = ?, vector_state = 'seekdb'
                    WHERE id = ? AND source_id = ?
                    """,
                    (self._chunk_payload_without_embedding(chunk), chunk.id, source_id),
                )
            self._upsert_chunk_index_state(
                source_id,
                revision,
                chunks,
                storage_mode="seekdb",
            )
            self._conn.execute(
                "DELETE FROM chunk_sync_operations WHERE source_id = ? AND revision = ?",
                (source_id, revision),
            )

    def _finalize_legacy_source(
        self,
        source_id: str,
        revision: str,
        chunks: list[KnowledgeChunk],
    ) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE chunks SET vector_state = 'legacy_needs_embedding' WHERE source_id = ?",
                (source_id,),
            )
            self._upsert_chunk_index_state(
                source_id,
                revision,
                chunks,
                storage_mode="sqlite_legacy",
            )
            self._conn.execute(
                "DELETE FROM chunk_sync_operations WHERE source_id = ? AND revision = ?",
                (source_id, revision),
            )

    def _replace_sqlite_chunks(
        self,
        source_id: str,
        chunks: list[KnowledgeChunk],
        *,
        persist_embedding: bool,
        vector_state: str | None = None,
    ) -> None:
        self._conn.execute("DELETE FROM chunks WHERE source_id = ?", (source_id,))
        self._conn.executemany(
            """
            INSERT INTO chunks(id, source_id, content, chunk_index, embedding, vector_state, payload)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                self._sqlite_chunk_row(
                    chunk,
                    persist_embedding=persist_embedding,
                    vector_state=vector_state,
                )
                for chunk in chunks
            ],
        )

    def _upsert_chunk_index_state(
        self,
        source_id: str,
        revision: str,
        chunks: list[KnowledgeChunk],
        *,
        storage_mode: str,
    ) -> None:
        dimension = len(chunks[0].embedding or []) if chunks and chunks[0].embedding else None
        self._conn.execute(
            """
            INSERT INTO chunk_index_state(
                source_id, revision, chunk_count, embedding_dimension,
                embedding_profile, storage_mode, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_id) DO UPDATE SET
                revision=excluded.revision,
                chunk_count=excluded.chunk_count,
                embedding_dimension=excluded.embedding_dimension,
                embedding_profile=excluded.embedding_profile,
                storage_mode=excluded.storage_mode,
                updated_at=excluded.updated_at
            """,
            (
                source_id,
                revision,
                len(chunks),
                dimension,
                self.embedding_profile_id,
                storage_mode,
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    def _chunk_index_states(self, source_ids: list[str]) -> dict[str, sqlite3.Row]:
        if not source_ids:
            return {}
        placeholders = ",".join("?" for _ in source_ids)
        rows = self._conn.execute(
            f"""
            SELECT source_id, chunk_count, embedding_dimension, embedding_profile, storage_mode
            FROM chunk_index_state
            WHERE source_id IN ({placeholders})
            """,
            source_ids,
        ).fetchall()
        return {row["source_id"]: row for row in rows}

    def _get_repository_meta(self, key: str) -> str | None:
        row = self._conn.execute("SELECT value FROM repository_meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def _set_repository_meta(self, key: str, value: str) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO repository_meta(key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (key, value),
            )

    def _get_sqlite_chunks_sync(self, source_id: str) -> list[KnowledgeChunk]:
        rows = self._conn.execute(
            "SELECT payload FROM chunks WHERE source_id = ? ORDER BY chunk_index ASC",
            (source_id,),
        ).fetchall()
        return [KnowledgeChunk.model_validate_json(row["payload"]) for row in rows]

    @staticmethod
    def _chunk_payload_without_embedding(chunk: KnowledgeChunk) -> str:
        return chunk.model_copy(update={"embedding": None}).model_dump_json()

    @staticmethod
    def _chunks_match_without_vectors(
        sqlite_chunks: list[KnowledgeChunk],
        native_chunks: list[KnowledgeChunk],
    ) -> bool:
        if len(sqlite_chunks) != len(native_chunks):
            return False

        def signature(chunk: KnowledgeChunk) -> dict[str, Any]:
            return chunk.model_dump(exclude={"embedding", "created_at"})

        sqlite_signatures = {chunk.id: signature(chunk) for chunk in sqlite_chunks}
        native_signatures = {chunk.id: signature(chunk) for chunk in native_chunks}
        return sqlite_signatures == native_signatures

    def _sqlite_chunk_row(
        self,
        chunk: KnowledgeChunk,
        *,
        persist_embedding: bool | None = None,
        vector_state: str | None = None,
    ) -> tuple[Any, ...]:
        if persist_embedding is None:
            persist_embedding = self.allow_sqlite_vector_fallback
        return (
            chunk.id,
            chunk.source_id,
            chunk.content,
            chunk.chunk_index,
            json.dumps(chunk.embedding) if persist_embedding and chunk.embedding is not None else None,
            vector_state or ("sqlite_fallback" if persist_embedding else "seekdb"),
            _dump_model(chunk) if persist_embedding else self._chunk_payload_without_embedding(chunk),
        )

    def _chunk_rows(self, source_ids: list[str] | None = None) -> list[sqlite3.Row]:
        if source_ids == []:
            return []
        params: list[Any] = []
        sql = "SELECT payload, content, embedding FROM chunks"
        if source_ids is not None:
            placeholders = ",".join("?" for _ in source_ids)
            sql += f" WHERE source_id IN ({placeholders})"
            params.extend(source_ids)
        return self._conn.execute(sql, params).fetchall()

    async def _search_sqlite_chunk_rows(
        self,
        query: str,
        rows: list[sqlite3.Row],
        top_k: int,
        query_embedding: list[float] | None,
        rerank_provider: object | None,
    ) -> list[dict]:
        bm25_scores = _bm25_scores(query, [row["content"] for row in rows])
        results = []
        for row, bm25_score in zip(rows, bm25_scores):
            chunk = KnowledgeChunk.model_validate_json(row["payload"])
            vector_score = 0.0
            has_comparable_embedding = False
            if query_embedding and row["embedding"]:
                row_embedding = json.loads(row["embedding"])
                has_comparable_embedding = len(row_embedding) == len(query_embedding)
                if has_comparable_embedding:
                    vector_score = _cosine(query_embedding, row_embedding)
            score = bm25_score + max(vector_score, 0.0)
            if bm25_score > 0 or has_comparable_embedding:
                results.append({"chunk": chunk, "score": score})

        results = sorted(results, key=lambda item: item["score"], reverse=True)[:top_k]
        return await self._maybe_rerank(query, results, top_k, rerank_provider)

    async def _maybe_rerank(
        self,
        query: str,
        results: list[dict],
        top_k: int,
        rerank_provider: object | None,
    ) -> list[dict]:
        if rerank_provider and results:
            try:
                return await rerank_provider.rerank(query, results, top_k=top_k)
            except Exception:
                return results
        return results

    async def save_artifact(self, artifact: Artifact) -> Artifact:
        self._conn.execute(
            """
            INSERT INTO artifacts(id, payload, created_at) VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET payload=excluded.payload
            """,
            (artifact.id, _dump_model(artifact), artifact.created_at.isoformat()),
        )
        self._conn.commit()
        return artifact

    async def get_artifact(self, artifact_id: str) -> Artifact | None:
        row = self._conn.execute("SELECT payload FROM artifacts WHERE id = ?", (artifact_id,)).fetchone()
        return Artifact.model_validate_json(row["payload"]) if row else None

    async def list_artifacts(self) -> list[Artifact]:
        rows = self._conn.execute("SELECT payload FROM artifacts ORDER BY created_at DESC").fetchall()
        return [Artifact.model_validate_json(row["payload"]) for row in rows]

    async def save_note(self, note: Note) -> Note:
        note.updated_at = utc_now()
        self._conn.execute(
            """
            INSERT INTO notes(id, title, body, payload, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title,
                body=excluded.body,
                payload=excluded.payload,
                updated_at=excluded.updated_at
            """,
            (
                note.id,
                note.title,
                note.body,
                _dump_model(note),
                note.created_at.isoformat(),
                note.updated_at.isoformat(),
            ),
        )
        self._conn.commit()
        return note

    async def get_note(self, note_id: str) -> Note | None:
        row = self._conn.execute("SELECT payload FROM notes WHERE id = ?", (note_id,)).fetchone()
        return Note.model_validate_json(row["payload"]) if row else None

    async def list_notes(self, query: str | None = None) -> list[Note]:
        if query:
            like = f"%{query.lower()}%"
            rows = self._conn.execute(
                """
                SELECT payload FROM notes
                WHERE lower(title) LIKE ? OR lower(body) LIKE ?
                ORDER BY updated_at DESC
                """,
                (like, like),
            ).fetchall()
        else:
            rows = self._conn.execute("SELECT payload FROM notes ORDER BY updated_at DESC").fetchall()
        return [Note.model_validate_json(row["payload"]) for row in rows]

    async def delete_note(self, note_id: str) -> bool:
        self._conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        self._conn.commit()
        return True

    async def save_job(self, job: Job) -> Job:
        self._conn.execute(
            """
            INSERT INTO jobs(id, payload, created_at) VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET payload=excluded.payload
            """,
            (job.id, _dump_model(job), job.created_at.isoformat()),
        )
        self._conn.commit()
        return job

    async def get_job(self, job_id: str) -> Job | None:
        row = self._conn.execute("SELECT payload FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return Job.model_validate_json(row["payload"]) if row else None

    async def save_slide_deck(self, deck: SlideDeckProject) -> SlideDeckProject:
        deck.updated_at = utc_now()
        self._conn.execute(
            """
            INSERT INTO slide_decks(id, payload, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                payload=excluded.payload,
                updated_at=excluded.updated_at
            """,
            (deck.id, _dump_model(deck), deck.created_at.isoformat(), deck.updated_at.isoformat()),
        )
        self._conn.commit()
        return deck

    async def get_slide_deck(self, deck_id: str) -> SlideDeckProject | None:
        row = self._conn.execute("SELECT payload FROM slide_decks WHERE id = ?", (deck_id,)).fetchone()
        return SlideDeckProject.model_validate_json(row["payload"]) if row else None

    async def list_slide_decks(self) -> list[SlideDeckProject]:
        rows = self._conn.execute("SELECT payload FROM slide_decks ORDER BY updated_at DESC").fetchall()
        return [SlideDeckProject.model_validate_json(row["payload"]) for row in rows]

    async def save_slide_asset(self, asset: SlideAsset) -> SlideAsset:
        self._conn.execute(
            """
            INSERT INTO slide_assets(id, deck_id, slide_id, payload, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET payload=excluded.payload
            """,
            (asset.id, asset.deck_id, asset.slide_id, _dump_model(asset), asset.created_at.isoformat()),
        )
        self._conn.commit()
        return asset

    async def get_slide_asset(self, asset_id: str) -> SlideAsset | None:
        row = self._conn.execute("SELECT payload FROM slide_assets WHERE id = ?", (asset_id,)).fetchone()
        return SlideAsset.model_validate_json(row["payload"]) if row else None

    async def save_slide_export(self, export: SlideDeckExport) -> SlideDeckExport:
        export.updated_at = utc_now()
        self._conn.execute(
            """
            INSERT INTO slide_exports(id, deck_id, payload, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                payload=excluded.payload,
                updated_at=excluded.updated_at
            """,
            (
                export.id,
                export.deck_id,
                _dump_model(export),
                export.created_at.isoformat(),
                export.updated_at.isoformat(),
            ),
        )
        self._conn.commit()
        return export

    async def get_slide_export(self, export_id: str) -> SlideDeckExport | None:
        row = self._conn.execute("SELECT payload FROM slide_exports WHERE id = ?", (export_id,)).fetchone()
        return SlideDeckExport.model_validate_json(row["payload"]) if row else None

    async def list_slide_exports(self, deck_id: str) -> list[SlideDeckExport]:
        rows = self._conn.execute(
            "SELECT payload FROM slide_exports WHERE deck_id = ? ORDER BY created_at DESC",
            (deck_id,),
        ).fetchall()
        return [SlideDeckExport.model_validate_json(row["payload"]) for row in rows]

    async def save_slide_deck_job(self, job: SlideDeckJob) -> SlideDeckJob:
        job.updated_at = utc_now()
        self._conn.execute(
            """
            INSERT INTO slide_deck_jobs(id, deck_id, payload, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                payload=excluded.payload,
                updated_at=excluded.updated_at
            """,
            (
                job.id,
                job.deck_id,
                _dump_model(job),
                job.created_at.isoformat(),
                job.updated_at.isoformat(),
            ),
        )
        self._conn.commit()
        return job

    async def get_slide_deck_job(self, job_id: str) -> SlideDeckJob | None:
        row = self._conn.execute("SELECT payload FROM slide_deck_jobs WHERE id = ?", (job_id,)).fetchone()
        return SlideDeckJob.model_validate_json(row["payload"]) if row else None

    async def list_slide_deck_jobs(self, deck_id: str) -> list[SlideDeckJob]:
        rows = self._conn.execute(
            "SELECT payload FROM slide_deck_jobs WHERE deck_id = ? ORDER BY created_at DESC",
            (deck_id,),
        ).fetchall()
        return [SlideDeckJob.model_validate_json(row["payload"]) for row in rows]
