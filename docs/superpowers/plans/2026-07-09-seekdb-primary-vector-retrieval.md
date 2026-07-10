# SeekDB Primary Vector Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make SeekDB the real primary vector and hybrid retrieval backend for NotebookLM-Lite RAG chunks, with SQLite kept only for entity metadata and explicit fallback.

**Architecture:** Keep the current repository interface and SQLite-backed CRUD tables for sources, artifacts, notes, jobs, and slide-deck state. Move chunk embedding writes and retrieval into a dedicated SeekDB native chunk index using `pyseekdb` collections with explicit HNSW dimensions and `embedding_function=None`; SQLite chunk rows remain a metadata/fallback copy, not the default vector search engine.

**Tech Stack:** FastAPI, Python 3.12, `pyseekdb>=1.3.0`, SQLite metadata tables, LiteLLM embeddings, pytest, Playwright smoke validation.

---

## Current Problem

Current code sets `vector_store_type: seekdb`, but `backend/infrastructure/repositories/seekdb_repository.py` writes embeddings into SQLite as JSON and searches by reading SQLite rows and calculating BM25/cosine in Python. The optional `pyseekdb` mirror is attempted after SQLite commit and fails in real uploads with:

```text
Skipping optional pyseekdb chunk mirror after save failure: execute sql failed OB_INVALID_ARGUMENT(1210): Incorrect arguments to %s
```

Local SDK inspection shows the failure is caused by creating a `pyseekdb` collection without matching explicit embedding settings and then searching before refreshing the native index. A working explicit-embedding path, verified against the installed `pyseekdb`, is:

```python
import pyseekdb

client = pyseekdb.Client(path="/tmp/seekdb")
collection = client.create_collection(
    name="chunks_source_abc",
    configuration=pyseekdb.HNSWConfiguration(dimension=3),
    embedding_function=None,
)
collection.upsert(
    ids=["chunk_1"],
    documents=["content"],
    metadatas=[{"source_id": "source_1", "payload": "{}"}],
    embeddings=[[0.1, 0.2, 0.3]],
)
collection.refresh_index()
collection.query(
    query_embeddings=[0.1, 0.2, 0.3],
    n_results=1,
    include=["documents", "metadatas", "distances"],
)
```

This plan makes that working path the default RAG chunk path.

## File Structure

- Create `backend/infrastructure/vector_stores/seekdb_chunk_index.py`
  - Owns all native `pyseekdb` collection creation, chunk upsert/delete/query, index refresh, collection naming, score normalization, and backend status.
- Modify `backend/infrastructure/repositories/seekdb_repository.py`
  - Delegates chunk vector writes/searches to `SeekDBChunkIndex`.
  - Keeps SQLite rows for source/chunk payload metadata and explicit fallback.
  - Removes the optional mirror warning path.
- Modify `backend/config.py`
  - Adds explicit fallback configuration and default primary semantics.
- Modify `config_example.yaml`
  - Documents that SeekDB native vector retrieval is default and fallback is opt-in.
- Modify `backend/infrastructure/vector_stores/seekdb_vector_store.py`
  - Reports the actual backend status from the repository.
- Modify `backend/api/routes/config.py` and `backend/api/schemas/config.py`
  - Exposes actual storage status to the frontend config modal.
- Modify `backend/main.py`
  - Extends `/health` with actual vector backend status.
- Modify tests:
  - `tests/test_seekdb_chunk_index.py`
  - `tests/test_chunking_and_rerank.py`
  - `tests/test_source_knowledge_base.py`
  - `tests/test_runtime_config_api.py`
  - `tests/test_config_settings.py`

## Decisions

- The scope is RAG chunk vector storage and retrieval. SQLite may remain the metadata store for non-vector entities in this iteration.
- SeekDB native mode is the default for `vector_store_type: seekdb`.
- SQLite vector search is available only when `seekdb_allow_sqlite_fallback: true` or in tests that explicitly construct the repository with fallback enabled.
- The repository must never silently label SQLite vector search as SeekDB.
- Multi-source filtering will use one SeekDB collection per source. This avoids relying on metadata `where` filtering, which did not work reliably in local SDK checks.

## Collection Model

For source `source_id`, native chunks are stored in:

```text
chunks_<sha1(source_id)[:16]>
```

Each collection uses the embedding dimension of the first chunk with an embedding:

```python
pyseekdb.HNSWConfiguration(dimension=len(first_embedding))
embedding_function=None
```

Each metadata row contains enough data to reconstruct `KnowledgeChunk`:

```python
{
    "source_id": chunk.source_id,
    "chunk_index": chunk.chunk_index,
    "payload": chunk.model_dump_json(),
}
```

Searching selected sources queries each selected source collection, merges results by normalized score, applies optional rerank, and returns the existing `list[dict]` shape:

```python
{"chunk": KnowledgeChunk(...), "score": 0.82}
```

---

### Task 1: Add a Native SeekDB Chunk Index

**Files:**
- Create: `backend/infrastructure/vector_stores/seekdb_chunk_index.py`
- Test: `tests/test_seekdb_chunk_index.py`

- [ ] **Step 1: Write failing tests for native collection creation and query**

Create `tests/test_seekdb_chunk_index.py`:

```python
import sys
import types
from pathlib import Path

import pytest

from backend.domain.source import KnowledgeChunk
from backend.infrastructure.vector_stores.seekdb_chunk_index import (
    SeekDBChunkIndex,
    SeekDBUnavailableError,
)


class FakeHNSWConfiguration:
    def __init__(self, dimension: int, distance: str = "cosine") -> None:
        self.dimension = dimension
        self.distance = distance


class FakeCollection:
    def __init__(self, name: str, dimension: int) -> None:
        self.name = name
        self.dimension = dimension
        self.upsert_calls = []
        self.delete_calls = []
        self.query_calls = []
        self.refresh_calls = 0
        self.rows = {}

    def upsert(self, ids, documents, metadatas, embeddings):
        self.upsert_calls.append(
            {
                "ids": ids,
                "documents": documents,
                "metadatas": metadatas,
                "embeddings": embeddings,
            }
        )
        for index, chunk_id in enumerate(ids):
            self.rows[chunk_id] = {
                "document": documents[index],
                "metadata": metadatas[index],
                "embedding": embeddings[index],
            }

    def delete(self, ids=None, **kwargs):
        self.delete_calls.append({"ids": ids, **kwargs})
        if ids:
            for chunk_id in ids:
                self.rows.pop(chunk_id, None)

    def query(self, query_embeddings, n_results, include):
        self.query_calls.append(
            {
                "query_embeddings": query_embeddings,
                "n_results": n_results,
                "include": include,
            }
        )
        ids = list(self.rows)[:n_results]
        return {
            "ids": [ids],
            "distances": [[0.0 + index for index, _ in enumerate(ids)]],
            "documents": [[self.rows[chunk_id]["document"] for chunk_id in ids]],
            "metadatas": [[self.rows[chunk_id]["metadata"] for chunk_id in ids]],
        }

    def count(self):
        return len(self.rows)

    def refresh_index(self):
        self.refresh_calls += 1


class FakeClient:
    instances = []

    def __init__(self, path: str) -> None:
        self.path = path
        self.collections = {}
        self.created = []
        FakeClient.instances.append(self)

    def get_or_create_collection(self, name, configuration=None, embedding_function=None):
        if embedding_function is not None:
            raise AssertionError("explicit LiteLLM embeddings require embedding_function=None")
        if configuration is None:
            raise AssertionError("native SeekDB collection must declare vector dimension")
        if name not in self.collections:
            self.created.append((name, configuration.dimension))
            self.collections[name] = FakeCollection(name, configuration.dimension)
        return self.collections[name]

    def get_collection(self, name, embedding_function=None):
        if name not in self.collections:
            raise KeyError(name)
        return self.collections[name]


@pytest.fixture(autouse=True)
def fake_pyseekdb(monkeypatch, request):
    if request.node.name == "test_real_pyseekdb_upsert_refresh_and_query_round_trip":
        yield
        return
    FakeClient.instances.clear()
    module = types.SimpleNamespace(Client=FakeClient, HNSWConfiguration=FakeHNSWConfiguration)
    monkeypatch.setitem(sys.modules, "pyseekdb", module)
    yield


def chunk(chunk_id: str, source_id: str, embedding: list[float]) -> KnowledgeChunk:
    return KnowledgeChunk(
        id=chunk_id,
        source_id=source_id,
        content=f"{chunk_id} content",
        chunk_index=0,
        embedding=embedding,
        metadata={"source_id": source_id},
    )


def test_upsert_creates_dimensioned_source_collection(tmp_path: Path):
    index = SeekDBChunkIndex(tmp_path / "native.seekdb")

    index.upsert_source_chunks("source-a", [chunk("chunk-a", "source-a", [0.1, 0.2, 0.3])])

    client = FakeClient.instances[0]
    assert client.created == [(index.collection_name("source-a"), 3)]
    collection = client.collections[index.collection_name("source-a")]
    assert collection.upsert_calls[0]["ids"] == ["chunk-a"]
    assert collection.upsert_calls[0]["embeddings"] == [[0.1, 0.2, 0.3]]
    assert collection.upsert_calls[0]["metadatas"][0]["source_id"] == "source-a"
    assert "payload" in collection.upsert_calls[0]["metadatas"][0]
    assert collection.refresh_calls == 1


def test_search_queries_seekdb_collections_and_reconstructs_chunks(tmp_path: Path):
    index = SeekDBChunkIndex(tmp_path / "native.seekdb")
    index.upsert_source_chunks("source-a", [chunk("chunk-a", "source-a", [0.1, 0.2, 0.3])])
    index.upsert_source_chunks("source-b", [chunk("chunk-b", "source-b", [0.9, 0.1, 0.1])])

    results = index.search(
        query_embedding=[0.1, 0.2, 0.3],
        source_ids=["source-a", "source-b"],
        top_k=2,
    )

    assert [item["chunk"].id for item in results] == ["chunk-a", "chunk-b"]
    assert all(item["backend"] == "seekdb" for item in results)
    client = FakeClient.instances[0]
    assert client.collections[index.collection_name("source-a")].query_calls
    assert client.collections[index.collection_name("source-b")].query_calls


def test_missing_pyseekdb_raises_without_silent_sqlite_vector_fallback(tmp_path: Path, monkeypatch):
    monkeypatch.setitem(sys.modules, "pyseekdb", None)

    with pytest.raises(SeekDBUnavailableError):
        SeekDBChunkIndex(tmp_path / "native.seekdb")


def test_real_pyseekdb_upsert_refresh_and_query_round_trip(tmp_path: Path, monkeypatch):
    pyseekdb = pytest.importorskip("pyseekdb")
    monkeypatch.setitem(sys.modules, "pyseekdb", pyseekdb)
    index = SeekDBChunkIndex(tmp_path / "real.seekdb")

    index.upsert_source_chunks("real-source", [chunk("real-chunk", "real-source", [0.1, 0.2, 0.3])])
    results = index.search(
        query_embedding=[0.1, 0.2, 0.3],
        source_ids=["real-source"],
        top_k=1,
    )

    assert results[0]["chunk"].id == "real-chunk"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
/Users/lzj/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest tests/test_seekdb_chunk_index.py -q
```

Expected: FAIL with `ModuleNotFoundError` or import error for `seekdb_chunk_index`.

- [ ] **Step 3: Implement the native chunk index**

Create `backend/infrastructure/vector_stores/seekdb_chunk_index.py`:

```python
"""Native SeekDB chunk vector index.

This module owns pyseekdb usage. The repository may keep SQLite metadata rows,
but RAG vector search should go through this index when vector_store_type=seekdb.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

from ...domain.source import KnowledgeChunk

logger = logging.getLogger(__name__)


class SeekDBUnavailableError(RuntimeError):
    """Raised when native SeekDB is required but the SDK cannot be initialized."""


class SeekDBChunkIndex:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        try:
            import pyseekdb  # type: ignore
        except Exception as exc:
            raise SeekDBUnavailableError("pyseekdb is required for native SeekDB vector retrieval") from exc

        self._pyseekdb = pyseekdb
        try:
            self.client = pyseekdb.Client(path=str(self.path))
        except Exception as exc:
            raise SeekDBUnavailableError(f"failed to initialize pyseekdb at {self.path}") from exc

    @staticmethod
    def collection_name(source_id: str) -> str:
        digest = hashlib.sha1(source_id.encode("utf-8")).hexdigest()[:16]
        return f"chunks_{digest}"

    @staticmethod
    def _first_embedding_dimension(chunks: list[KnowledgeChunk]) -> int:
        for chunk in chunks:
            if chunk.embedding:
                return len(chunk.embedding)
        raise ValueError("SeekDB native indexing requires chunk embeddings")

    def _collection(self, source_id: str, dimension: int | None = None) -> Any:
        name = self.collection_name(source_id)
        if dimension is None:
            return self.client.get_collection(name=name, embedding_function=None)
        return self.client.get_or_create_collection(
            name=name,
            configuration=self._pyseekdb.HNSWConfiguration(dimension=dimension),
            embedding_function=None,
        )

    def upsert_source_chunks(self, source_id: str, chunks: list[KnowledgeChunk]) -> None:
        if not chunks:
            return
        dimension = self._first_embedding_dimension(chunks)
        missing = [chunk.id for chunk in chunks if not chunk.embedding or len(chunk.embedding) != dimension]
        if missing:
            raise ValueError(f"all chunks require {dimension}-dimensional embeddings: {missing}")

        collection = self._collection(source_id, dimension=dimension)
        collection.upsert(
            ids=[chunk.id for chunk in chunks],
            documents=[chunk.content for chunk in chunks],
            metadatas=[
                {
                    "source_id": chunk.source_id,
                    "chunk_index": chunk.chunk_index,
                    "payload": chunk.model_dump_json(),
                }
                for chunk in chunks
            ],
            embeddings=[chunk.embedding for chunk in chunks],
        )
        collection.refresh_index()

    def delete_source_chunks(self, source_id: str, chunk_ids: list[str]) -> None:
        if not chunk_ids:
            return
        try:
            collection = self._collection(source_id)
            collection.delete(ids=chunk_ids)
        except Exception as exc:
            logger.warning("SeekDB native chunk delete skipped for %s: %s", source_id, exc)

    def search(
        self,
        query_embedding: list[float],
        source_ids: list[str],
        top_k: int,
    ) -> list[dict[str, Any]]:
        if not query_embedding:
            raise ValueError("SeekDB native search requires a query embedding")

        merged: list[dict[str, Any]] = []
        per_source_k = max(top_k, 1)
        for source_id in source_ids:
            try:
                collection = self._collection(source_id)
                response = collection.query(
                    query_embeddings=query_embedding,
                    n_results=per_source_k,
                    include=["documents", "metadatas", "distances"],
                )
            except Exception as exc:
                logger.warning("SeekDB native search skipped source %s: %s", source_id, exc)
                continue

            ids = (response.get("ids") or [[]])[0]
            distances = (response.get("distances") or [[]])[0]
            metadatas = (response.get("metadatas") or [[]])[0]
            for index, chunk_id in enumerate(ids):
                metadata = metadatas[index] if index < len(metadatas) else {}
                payload = metadata.get("payload")
                if not payload:
                    continue
                distance = distances[index] if index < len(distances) else 1.0
                merged.append(
                    {
                        "chunk": KnowledgeChunk.model_validate_json(payload),
                        "score": 1.0 / (1.0 + max(float(distance), 0.0)),
                        "backend": "seekdb",
                        "id": chunk_id,
                    }
                )

        return sorted(merged, key=lambda item: item["score"], reverse=True)[:top_k]

    def status(self) -> dict[str, Any]:
        return {
            "vector_backend": "seekdb",
            "seekdb_path": str(self.path),
            "native_available": True,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
/Users/lzj/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest tests/test_seekdb_chunk_index.py -q
```

Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/infrastructure/vector_stores/seekdb_chunk_index.py tests/test_seekdb_chunk_index.py
git commit -m "feat(seekdb): add native chunk vector index"
```

---

### Task 2: Wire Repository Chunk Writes to Native SeekDB Primary

**Files:**
- Modify: `backend/config.py`
- Modify: `config_example.yaml`
- Modify: `backend/infrastructure/repositories/seekdb_repository.py`
- Test: `tests/test_source_knowledge_base.py`
- Test: `tests/test_config_settings.py`

- [ ] **Step 1: Write failing repository tests**

Append to `tests/test_source_knowledge_base.py`:

```python
import logging


class RecordingNativeIndex:
    def __init__(self) -> None:
        self.upserts = []
        self.deletes = []
        self.searches = []

    def upsert_source_chunks(self, source_id, chunks):
        self.upserts.append((source_id, chunks))

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

    def status(self):
        return {"vector_backend": "seekdb", "native_available": True}


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
async def test_repository_requires_native_seekdb_for_vector_search_unless_fallback_enabled(tmp_path: Path):
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
```

Modify `tests/test_config_settings.py` to assert fallback is disabled by default:

```python
def test_seekdb_native_vector_search_is_default(sample_config_file):
    settings = get_settings()

    assert settings.vector_store_type == "seekdb"
    assert settings.seekdb_allow_sqlite_fallback is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
/Users/lzj/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest tests/test_source_knowledge_base.py::test_repository_uses_seekdb_native_index_for_chunk_save_and_search tests/test_source_knowledge_base.py::test_repository_requires_native_seekdb_for_vector_search_unless_fallback_enabled tests/test_config_settings.py::test_seekdb_native_vector_search_is_default -q
```

Expected: FAIL because `SeekDBRepository` does not accept `native_chunk_index` or `allow_sqlite_vector_fallback`, and `Settings` lacks `seekdb_allow_sqlite_fallback`.

- [ ] **Step 3: Add explicit config**

Modify `backend/config.py` in `Settings`:

```python
    # SeekDB settings
    seekdb_path: str = "./data/seekdb.db"
    seekdb_allow_sqlite_fallback: bool = False
```

Modify the public dict construction in `Settings.model_config` related code if the project currently enumerates storage keys. Include:

```python
        for key in (
            "vector_store_type",
            "chroma_persist_dir",
            "seekdb_path",
            "seekdb_allow_sqlite_fallback",
        ):
```

Modify `config_example.yaml`:

```yaml
vector_store:
  vector_store_type: "seekdb"
  seekdb_path: "./data/seekdb.db"
  # SeekDB is the primary vector/hybrid retrieval backend.
  # Set this true only for local debugging when pyseekdb is unavailable.
  seekdb_allow_sqlite_fallback: false
```

If the file uses a flat `vector_store_type` block instead of `vector_store:`, preserve the existing shape and add:

```yaml
  seekdb_allow_sqlite_fallback: false
```

- [ ] **Step 4: Wire native chunk index into repository**

Modify `backend/infrastructure/repositories/seekdb_repository.py`:

```python
from ...infrastructure.vector_stores.seekdb_chunk_index import SeekDBChunkIndex, SeekDBUnavailableError
```

Change `__init__`:

```python
    def __init__(
        self,
        db_path: str | Path,
        native_chunk_index: object | None = None,
        allow_sqlite_vector_fallback: bool = False,
    ) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.allow_sqlite_vector_fallback = allow_sqlite_vector_fallback
        self.native_chunk_index = native_chunk_index
        if self.native_chunk_index is None:
            try:
                self.native_chunk_index = SeekDBChunkIndex(self.db_path.parent / f"{self.db_path.stem}.seekdb")
            except SeekDBUnavailableError as exc:
                if not allow_sqlite_vector_fallback:
                    logger.warning("Native SeekDB vector index unavailable: %s", exc)
                self.native_chunk_index = None
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()
```

Remove `_try_pyseekdb` and `self.seekdb_client`.

Replace the end of `save_chunks` after SQLite commit:

```python
        if self.native_chunk_index is not None:
            self.native_chunk_index.upsert_source_chunks(source_id, chunks)
            return
        if not self.allow_sqlite_vector_fallback:
            raise RuntimeError("native SeekDB vector index is unavailable; enable seekdb_allow_sqlite_fallback for SQLite fallback")
```

Replace the top of `search_chunks`:

```python
        if self.native_chunk_index is not None and query_embedding:
            selected_source_ids = source_ids or [source.id for source in await self.list_sources()]
            results = self.native_chunk_index.search(
                query_embedding=query_embedding,
                source_ids=selected_source_ids,
                top_k=top_k,
            )
            if rerank_provider and results:
                try:
                    return await rerank_provider.rerank(query, results, top_k=top_k)
                except Exception:
                    return results
            return results
        if self.native_chunk_index is not None and not query_embedding:
            logger.warning("SeekDB native vector search skipped because query embedding is missing")
        if not self.allow_sqlite_vector_fallback:
            raise RuntimeError("native SeekDB vector search requires query embeddings")
```

Keep the existing SQLite BM25/cosine code below as fallback only.

Modify `delete_source` before SQLite deletion:

```python
        chunks = await self.get_chunks(source_id)
        if self.native_chunk_index is not None:
            self.native_chunk_index.delete_source_chunks(source_id, [chunk.id for chunk in chunks])
```

Add:

```python
    def storage_status(self) -> dict[str, Any]:
        if self.native_chunk_index is not None:
            return self.native_chunk_index.status()
        return {
            "vector_backend": "sqlite_fallback" if self.allow_sqlite_vector_fallback else "unavailable",
            "seekdb_path": str(self.db_path.parent / f"{self.db_path.stem}.seekdb"),
            "native_available": False,
        }
```

- [ ] **Step 5: Update dependency injection**

Modify `backend/dependencies.py`:

```python
            cls._knowledge_repository = SeekDBRepository(
                settings.seekdb_path,
                allow_sqlite_vector_fallback=settings.seekdb_allow_sqlite_fallback,
            )
```

- [ ] **Step 6: Run tests to verify they pass**

Run:

```bash
/Users/lzj/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest tests/test_source_knowledge_base.py::test_repository_uses_seekdb_native_index_for_chunk_save_and_search tests/test_source_knowledge_base.py::test_repository_requires_native_seekdb_for_vector_search_unless_fallback_enabled tests/test_config_settings.py::test_seekdb_native_vector_search_is_default -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/config.py config_example.yaml backend/dependencies.py backend/infrastructure/repositories/seekdb_repository.py tests/test_source_knowledge_base.py tests/test_config_settings.py
git commit -m "feat(seekdb): make native vector index primary"
```

---

### Task 3: Preserve Lexical Recall Without Making SQLite Primary

**Files:**
- Modify: `backend/infrastructure/vector_stores/seekdb_chunk_index.py`
- Modify: `backend/infrastructure/repositories/seekdb_repository.py`
- Test: `tests/test_chunking_and_rerank.py`

- [ ] **Step 1: Write failing test for native hybrid call**

Append to `tests/test_chunking_and_rerank.py`:

```python
class HybridRecordingIndex:
    def __init__(self) -> None:
        self.calls = []

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

    results = await repo.search_chunks(
        "TLS handshake",
        source_ids=[source.id],
        top_k=1,
        query_embedding=[0.1, 0.2, 0.3],
    )

    assert native_index.calls == [("TLS handshake", [0.1, 0.2, 0.3], [source.id], 1)]
    assert results[0]["chunk"].id == "hybrid_chunk"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
/Users/lzj/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest tests/test_chunking_and_rerank.py::test_seekdb_repository_prefers_native_hybrid_search -q
```

Expected: FAIL because `hybrid_search` is not called.

- [ ] **Step 3: Implement `hybrid_search` in `SeekDBChunkIndex`**

Add to `backend/infrastructure/vector_stores/seekdb_chunk_index.py`:

```python
    def hybrid_search(
        self,
        query_text: str,
        query_embedding: list[float],
        source_ids: list[str],
        top_k: int,
    ) -> list[dict[str, Any]]:
        if not query_text.strip():
            return self.search(query_embedding=query_embedding, source_ids=source_ids, top_k=top_k)

        merged: list[dict[str, Any]] = []
        for source_id in source_ids:
            try:
                collection = self._collection(source_id)
                response = collection.hybrid_search(
                    query={"match": {"document": query_text}},
                    knn={"query_embeddings": query_embedding, "k": max(top_k, 1)},
                    n_results=max(top_k, 1),
                    include=["documents", "metadatas", "distances"],
                )
            except AttributeError:
                return self.search(query_embedding=query_embedding, source_ids=source_ids, top_k=top_k)
            except Exception as exc:
                logger.warning("SeekDB hybrid search skipped source %s: %s", source_id, exc)
                continue

            ids = (response.get("ids") or [[]])[0]
            distances = (response.get("distances") or [[]])[0]
            metadatas = (response.get("metadatas") or [[]])[0]
            for index, chunk_id in enumerate(ids):
                metadata = metadatas[index] if index < len(metadatas) else {}
                payload = metadata.get("payload")
                if not payload:
                    continue
                distance = distances[index] if index < len(distances) else 1.0
                merged.append(
                    {
                        "chunk": KnowledgeChunk.model_validate_json(payload),
                        "score": 1.0 / (1.0 + max(float(distance), 0.0)),
                        "backend": "seekdb",
                        "id": chunk_id,
                    }
                )

        return sorted(merged, key=lambda item: item["score"], reverse=True)[:top_k]
```

Modify `search_chunks` in `backend/infrastructure/repositories/seekdb_repository.py`:

```python
        if self.native_chunk_index is not None and query_embedding:
            selected_source_ids = source_ids or [source.id for source in await self.list_sources()]
            if hasattr(self.native_chunk_index, "hybrid_search"):
                results = self.native_chunk_index.hybrid_search(
                    query_text=query,
                    query_embedding=query_embedding,
                    source_ids=selected_source_ids,
                    top_k=top_k,
                )
            else:
                results = self.native_chunk_index.search(
                    query_embedding=query_embedding,
                    source_ids=selected_source_ids,
                    top_k=top_k,
                )
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
/Users/lzj/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest tests/test_chunking_and_rerank.py::test_seekdb_repository_prefers_native_hybrid_search -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/infrastructure/vector_stores/seekdb_chunk_index.py backend/infrastructure/repositories/seekdb_repository.py tests/test_chunking_and_rerank.py
git commit -m "feat(seekdb): use native hybrid retrieval"
```

---

### Task 4: Expose Actual Backend Status

**Files:**
- Modify: `backend/infrastructure/vector_stores/seekdb_vector_store.py`
- Modify: `backend/api/schemas/config.py`
- Modify: `backend/api/routes/config.py`
- Modify: `backend/main.py`
- Test: `tests/test_runtime_config_api.py`

- [ ] **Step 1: Write failing API status tests**

Append to `tests/test_runtime_config_api.py`:

```python
def test_runtime_config_exposes_actual_vector_backend(client):
    response = client.get("/api/config")

    assert response.status_code == 200
    storage = response.json()["storage"]
    assert "actual_vector_backend" in storage
    assert storage["configured_vector_store_type"] == "seekdb"


def test_health_exposes_actual_vector_backend(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert "storage" in response.json()
    assert "actual_vector_backend" in response.json()["storage"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
/Users/lzj/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest tests/test_runtime_config_api.py::test_runtime_config_exposes_actual_vector_backend tests/test_runtime_config_api.py::test_health_exposes_actual_vector_backend -q
```

Expected: FAIL because the response does not include actual backend status.

- [ ] **Step 3: Add status helpers**

Modify `backend/infrastructure/vector_stores/seekdb_vector_store.py`:

```python
    def storage_status(self) -> dict[str, Any]:
        if hasattr(self.repository, "storage_status"):
            return self.repository.storage_status()
        return {"vector_backend": "unknown", "native_available": False}

    async def get_stats(self) -> dict[str, Any]:
        sources = await self.repository.list_sources()
        chunk_count = sum(source.chunk_count for source in sources)
        status = self.storage_status()
        return {
            "total_documents": len(sources),
            "total_chunks": chunk_count,
            "backend": status["vector_backend"],
            "storage": status,
        }
```

- [ ] **Step 4: Add config schema/status fields**

Modify `backend/api/schemas/config.py` so `RuntimeConfigResponse.storage` allows untyped status values:

```python
class RuntimeConfigResponse(BaseModel):
    models: dict[str, PublicModelProfile]
    chunking: dict[str, Any]
    storage: dict[str, Any]
    message: str = ""
```

Modify `_response` in `backend/api/routes/config.py`:

```python
    vector_store = DependencyContainer.get_vector_store(settings=settings)
    stats = await vector_store.get_stats() if hasattr(vector_store, "get_stats") else {}
```

Because `_response` is currently synchronous, change it to:

```python
async def _response(message: str = "") -> RuntimeConfigResponse:
    settings = get_settings()
    models = settings.api.models
    vector_store = DependencyContainer.get_vector_store(settings=settings)
    stats = await vector_store.get_stats()
    storage_status = stats.get("storage", {})
    return RuntimeConfigResponse(
        models={name: _public_profile(getattr(models, name)) for name in ModelProfiles.model_fields},
        chunking={
            "provider": settings.chunking.provider,
            "tokenizer": settings.chunking.tokenizer,
            "chunk_size": settings.chunk_size,
            "chunk_overlap": settings.chunk_overlap,
        },
        storage={
            "configured_vector_store_type": settings.vector_store_type,
            "seekdb_path": settings.seekdb_path,
            "seekdb_allow_sqlite_fallback": settings.seekdb_allow_sqlite_fallback,
            "actual_vector_backend": storage_status.get("vector_backend", "unknown"),
            "native_available": storage_status.get("native_available", False),
        },
        message=message,
    )
```

Then update route returns:

```python
@router.get("", response_model=RuntimeConfigResponse)
async def get_runtime_config() -> RuntimeConfigResponse:
    return await _response()


@router.post("", response_model=RuntimeConfigResponse)
async def update_runtime_config(request: RuntimeConfigUpdate) -> RuntimeConfigResponse:
    profile_data = {
        name: profile.model_dump(exclude_none=True)
        for name, profile in request.models.items()
    }
    update_runtime_model_profiles(profile_data)
    DependencyContainer.reset_runtime_caches()
    return await _response("Runtime model configuration updated.")
```

Modify `backend/main.py`:

```python
@app.get("/health")
async def health_check():
    from .dependencies import get_vector_store

    vector_store = get_vector_store()
    stats = await vector_store.get_stats()
    return {
        "status": "healthy",
        "version": settings.app_version,
        "storage": {
            "actual_vector_backend": stats.get("storage", {}).get("vector_backend", stats.get("backend")),
            "native_available": stats.get("storage", {}).get("native_available", False),
        },
    }
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
/Users/lzj/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest tests/test_runtime_config_api.py::test_runtime_config_exposes_actual_vector_backend tests/test_runtime_config_api.py::test_health_exposes_actual_vector_backend -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/infrastructure/vector_stores/seekdb_vector_store.py backend/api/schemas/config.py backend/api/routes/config.py backend/main.py tests/test_runtime_config_api.py
git commit -m "feat(config): expose actual vector backend status"
```

---

### Task 5: Backfill Existing SQLite Chunk Embeddings Into SeekDB

**Files:**
- Modify: `backend/infrastructure/repositories/seekdb_repository.py`
- Test: `tests/test_source_knowledge_base.py`

- [ ] **Step 1: Write failing test for lazy backfill**

Append to `tests/test_source_knowledge_base.py`:

```python
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

    await repo.backfill_native_chunks()

    assert native_index.upserts[0][0] == source.id
    assert native_index.upserts[0][1][0].id == "chunk-backfill"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
/Users/lzj/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest tests/test_source_knowledge_base.py::test_repository_backfills_existing_sqlite_chunks_to_native_index -q
```

Expected: FAIL because `backfill_native_chunks` does not exist.

- [ ] **Step 3: Implement backfill**

Add to `backend/infrastructure/repositories/seekdb_repository.py`:

```python
    async def backfill_native_chunks(self) -> int:
        if self.native_chunk_index is None:
            if self.allow_sqlite_vector_fallback:
                return 0
            raise RuntimeError("native SeekDB vector index is unavailable; cannot backfill chunks")

        sources = await self.list_sources()
        written = 0
        for source in sources:
            chunks = await self.get_chunks(source.id)
            chunks_with_embeddings = [chunk for chunk in chunks if chunk.embedding]
            if chunks_with_embeddings:
                self.native_chunk_index.upsert_source_chunks(source.id, chunks_with_embeddings)
                written += len(chunks_with_embeddings)
        return written
```

Call it in `DependencyContainer.get_knowledge_repository` is not safe because it is async. Instead call it opportunistically from `SourceService` only after new writes and expose a manual helper for migration. Add a script in Task 6 for explicit migration.

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
/Users/lzj/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest tests/test_source_knowledge_base.py::test_repository_backfills_existing_sqlite_chunks_to_native_index -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/infrastructure/repositories/seekdb_repository.py tests/test_source_knowledge_base.py
git commit -m "feat(seekdb): backfill existing chunks into native index"
```

---

### Task 6: Add a Local Verification Script for the Warning Regression

**Files:**
- Create: `scripts/verify_seekdb_native.py`
- Test: manual command in this task

- [ ] **Step 1: Create verification script**

Create `scripts/verify_seekdb_native.py`:

```python
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from backend.domain.source import KnowledgeChunk, KnowledgeSource, SourceKind
from backend.infrastructure.repositories.seekdb_repository import SeekDBRepository


async def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = SeekDBRepository(Path(tmp) / "knowledge.db", allow_sqlite_vector_fallback=False)
        source = KnowledgeSource(id="verify-source", kind=SourceKind.TEXT, title="Verify")
        await repo.save_source(source)
        await repo.save_chunks(
            source.id,
            [
                KnowledgeChunk(
                    id="verify-chunk",
                    source_id=source.id,
                    content="SeekDB native vector retrieval verification",
                    chunk_index=0,
                    embedding=[0.1, 0.2, 0.3],
                    metadata={"source_id": source.id},
                )
            ],
        )
        results = await repo.search_chunks(
            "SeekDB native retrieval",
            source_ids=[source.id],
            top_k=1,
            query_embedding=[0.1, 0.2, 0.3],
        )
        assert results, "expected at least one native SeekDB result"
        assert results[0]["chunk"].id == "verify-chunk"
        assert repo.storage_status()["vector_backend"] == "seekdb"
        await repo.close()
    print("SeekDB native vector verification passed")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Run script**

Run:

```bash
/Users/lzj/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/verify_seekdb_native.py
```

Expected:

```text
SeekDB native vector verification passed
```

There must be no log line containing:

```text
Skipping optional pyseekdb chunk mirror
```

- [ ] **Step 3: Commit**

```bash
git add scripts/verify_seekdb_native.py
git commit -m "test(seekdb): add native vector verification script"
```

---

### Task 7: Full Regression and Real App Smoke

**Files:**
- No required source edits if all prior tasks pass.
- Use existing local `config.yaml`; do not commit it.

- [ ] **Step 1: Run backend unit tests**

Run:

```bash
/Users/lzj/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Run backend compile check**

Run:

```bash
/Users/lzj/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m compileall -q backend
```

Expected: exit code `0`.

- [ ] **Step 3: Run frontend build and tests**

Run:

```bash
cd frontend
npm test -- --reporter=dot
npm run build
npm run lint
npm run test:e2e -- --project=chromium
```

Expected:
- Vitest passes.
- Build passes.
- Lint has no errors.
- Playwright passes.

- [ ] **Step 4: Start services**

Run backend:

```bash
/Users/lzj/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Run frontend in another shell:

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Expected:
- Backend logs show startup without SeekDB mirror warning.
- Frontend is available at `http://127.0.0.1:5173`.

- [ ] **Step 5: Verify health and config report native SeekDB**

Run:

```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/api/config
```

Expected JSON contains:

```json
{
  "actual_vector_backend": "seekdb",
  "native_available": true
}
```

- [ ] **Step 6: Browser smoke upload and RAG**

Use Playwright or the browser manually:

1. Open `http://127.0.0.1:5173`.
2. Upload `/Users/lzj/proj/notebook/NotebookLM-Lite/doc/L9.md`.
3. Ask: `理想 L9 的智能座舱有哪些核心能力？`
4. Confirm the answer references uploaded content and sources.
5. Check backend logs for absence of:

```text
Skipping optional pyseekdb chunk mirror
```

- [ ] **Step 7: Commit if a smoke-only doc update is added**

If this task adds a small note to README or docs, commit:

```bash
git add README.md README_zn.md
git commit -m "docs: clarify SeekDB native vector retrieval"
```

If no doc edit is needed, skip this commit.

---

## Self-Review

**Spec coverage:** The plan makes SeekDB native chunk vector storage and retrieval primary, keeps SQLite as explicit fallback only, exposes actual backend status, and directly targets the observed `Skipping optional pyseekdb chunk mirror` warning by deleting the optional mirror path.

**Placeholder scan:** No implementation step relies on TBD, TODO, or undefined behavior. Each code-changing task includes concrete test code, implementation code, commands, and expected results.

**Type consistency:** The new `SeekDBChunkIndex` methods are used consistently:
- `upsert_source_chunks(source_id, chunks)`
- `delete_source_chunks(source_id, chunk_ids)`
- `search(query_embedding, source_ids, top_k)`
- `hybrid_search(query_text, query_embedding, source_ids, top_k)`
- `status()`

**Risk boundary:** This plan does not migrate artifacts, notes, jobs, or slide decks from SQLite into SeekDB. That is a separate broader database migration. This plan fixes the vector/RAG path that currently claims SeekDB while using SQLite.
