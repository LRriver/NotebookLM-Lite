"""SeekDB repository wrapper.

SQLite stores source and chunk payload metadata. Native SeekDB owns chunk vector
indexing whenever embeddings are present; SQLite vector scoring is retained only
as an explicit fallback path.
"""

from __future__ import annotations

import json
import logging
import math
import re
import sqlite3
from pathlib import Path
from typing import Any

from ...core.interfaces.knowledge_repository import KnowledgeRepositoryInterface
from ...domain.slide_deck import SlideAsset, SlideDeckExport, SlideDeckJob, SlideDeckProject
from ...domain.source import Artifact, Job, KnowledgeChunk, KnowledgeSource, Note, SourceStatus, utc_now
from ..vector_stores.seekdb_chunk_index import SeekDBChunkIndex

logger = logging.getLogger(__name__)

_AUTO_NATIVE_CHUNK_INDEX: Any = object()
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
        native_chunk_index: object | None = _AUTO_NATIVE_CHUNK_INDEX,
        allow_sqlite_vector_fallback: bool = False,
    ) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.seekdb_path = self.db_path.parent / f"{self.db_path.stem}.seekdb"
        self.allow_sqlite_vector_fallback = allow_sqlite_vector_fallback
        self.native_chunk_index = (
            self._try_native_chunk_index(self.seekdb_path)
            if native_chunk_index is _AUTO_NATIVE_CHUNK_INDEX
            else native_chunk_index
        )
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

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
                payload TEXT NOT NULL,
                FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_chunks_source_id ON chunks(source_id);
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
        self._conn.commit()

    async def close(self) -> None:
        self._conn.close()

    def storage_status(self) -> dict[str, Any]:
        if self.native_chunk_index is not None:
            status = dict(self.native_chunk_index.status())
            status.setdefault("seekdb_path", str(self.seekdb_path))
            status.setdefault("native_available", True)
            return status
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
        chunk_rows = self._conn.execute("SELECT id FROM chunks WHERE source_id = ?", (source_id,)).fetchall()
        chunk_ids = [row["id"] for row in chunk_rows]
        if self.native_chunk_index is not None:
            self.native_chunk_index.delete_source_chunks(source_id, chunk_ids)
        self._conn.execute("DELETE FROM chunks WHERE source_id = ?", (source_id,))
        self._conn.execute("DELETE FROM sources WHERE id = ?", (source_id,))
        self._conn.commit()
        return True

    async def save_chunks(self, source_id: str, chunks: list[KnowledgeChunk]) -> None:
        self._conn.execute("DELETE FROM chunks WHERE source_id = ?", (source_id,))
        self._conn.executemany(
            """
            INSERT INTO chunks(id, source_id, content, chunk_index, embedding, payload)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    chunk.id,
                    chunk.source_id,
                    chunk.content,
                    chunk.chunk_index,
                    json.dumps(chunk.embedding) if chunk.embedding is not None else None,
                    _dump_model(chunk),
                )
                for chunk in chunks
            ],
        )
        self._conn.commit()

        has_vector_chunks = any(chunk.embedding is not None for chunk in chunks)
        if self.native_chunk_index is not None:
            if chunks and has_vector_chunks:
                self.native_chunk_index.upsert_source_chunks(source_id, chunks)
            elif not chunks:
                self.native_chunk_index.upsert_source_chunks(source_id, chunks)
            return

        if has_vector_chunks and not self.allow_sqlite_vector_fallback:
            raise RuntimeError(_NATIVE_UNAVAILABLE_MESSAGE)

    async def get_chunks(self, source_id: str) -> list[KnowledgeChunk]:
        rows = self._conn.execute(
            "SELECT payload FROM chunks WHERE source_id = ? ORDER BY chunk_index ASC",
            (source_id,),
        ).fetchall()
        return [KnowledgeChunk.model_validate_json(row["payload"]) for row in rows]

    async def search_chunks(
        self,
        query: str,
        source_ids: list[str] | None = None,
        top_k: int = 5,
        query_embedding: list[float] | None = None,
        rerank_provider: object | None = None,
    ) -> list[dict]:
        if self.native_chunk_index is not None and query_embedding is not None:
            selected_source_ids = source_ids or self._current_source_ids()
            results = self.native_chunk_index.search(query_embedding, selected_source_ids, top_k)
            return await self._maybe_rerank(query, results, top_k, rerank_provider)

        rows = self._chunk_rows(source_ids)
        has_sqlite_vectors = any(row["embedding"] for row in rows)
        if self.native_chunk_index is not None and has_sqlite_vectors and not self.allow_sqlite_vector_fallback:
            raise RuntimeError("native SeekDB vector search requires query embeddings")
        if (
            self.native_chunk_index is None
            and (query_embedding is not None or has_sqlite_vectors)
            and not self.allow_sqlite_vector_fallback
        ):
            raise RuntimeError(_NATIVE_UNAVAILABLE_MESSAGE)

        return await self._search_sqlite_chunk_rows(query, rows, top_k, query_embedding, rerank_provider)

    def _current_source_ids(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT id FROM sources WHERE status != ? ORDER BY created_at DESC",
            (SourceStatus.DELETED.value,),
        ).fetchall()
        return [row["id"] for row in rows]

    def _chunk_rows(self, source_ids: list[str] | None = None) -> list[sqlite3.Row]:
        params: list[Any] = []
        sql = "SELECT payload, content, embedding FROM chunks"
        if source_ids:
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
            if query_embedding and row["embedding"]:
                vector_score = _cosine(query_embedding, json.loads(row["embedding"]))
            score = bm25_score + max(vector_score, 0.0)
            if bm25_score > 0 or query_embedding:
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
