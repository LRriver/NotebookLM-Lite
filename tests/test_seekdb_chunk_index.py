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
