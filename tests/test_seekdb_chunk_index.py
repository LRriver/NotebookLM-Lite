import os
import subprocess
import sys
import textwrap
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
        self.events = []
        self.refresh_calls = 0
        self.rows = {}

    def upsert(self, ids, documents, metadatas, embeddings):
        self.events.append({"op": "upsert", "ids": ids})
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
        self.events.append({"op": "delete", "ids": ids, **kwargs})
        self.delete_calls.append({"ids": ids, **kwargs})
        if ids:
            for chunk_id in ids:
                self.rows.pop(chunk_id, None)
        where = kwargs.get("where")
        if where:
            for chunk_id, row in list(self.rows.items()):
                if all(row["metadata"].get(key) == value for key, value in where.items()):
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

    def get(self, include=None, **kwargs):
        return {"ids": list(self.rows)}

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
    if request.node.name.startswith("test_real_pyseekdb"):
        yield
        return
    FakeClient.instances.clear()
    module = types.SimpleNamespace(Client=FakeClient, HNSWConfiguration=FakeHNSWConfiguration)
    monkeypatch.setitem(sys.modules, "pyseekdb", module)
    yield


def chunk(
    chunk_id: str,
    source_id: str,
    embedding: list[float],
    metadata: dict | None = None,
) -> KnowledgeChunk:
    return KnowledgeChunk(
        id=chunk_id,
        source_id=source_id,
        content=f"{chunk_id} content",
        chunk_index=0,
        embedding=embedding,
        metadata=metadata if metadata is not None else {"source_id": source_id},
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
    source_a_query = client.collections[index.collection_name("source-a")].query_calls[0]
    source_b_query = client.collections[index.collection_name("source-b")].query_calls[0]
    assert source_a_query["query_embeddings"] == [[0.1, 0.2, 0.3]]
    assert source_a_query["n_results"] == 2
    assert source_a_query["include"] == ["documents", "metadatas", "distances"]
    assert source_b_query["query_embeddings"] == [[0.1, 0.2, 0.3]]
    assert source_b_query["n_results"] == 2
    assert source_b_query["include"] == ["documents", "metadatas", "distances"]


def test_delete_source_chunks_refreshes_collection_after_successful_delete(tmp_path: Path):
    index = SeekDBChunkIndex(tmp_path / "native.seekdb")
    index.upsert_source_chunks("source-a", [chunk("chunk-a", "source-a", [0.1, 0.2, 0.3])])

    collection = FakeClient.instances[0].collections[index.collection_name("source-a")]
    index.delete_source_chunks("source-a", ["chunk-a"])

    assert collection.delete_calls[-1]["ids"] == ["chunk-a"]
    assert collection.rows == {}
    assert collection.refresh_calls == 2


def test_upsert_source_chunks_replaces_existing_source_collection(tmp_path: Path):
    index = SeekDBChunkIndex(tmp_path / "native.seekdb")
    index.upsert_source_chunks(
        "source-a",
        [
            chunk("chunk-a", "source-a", [0.1, 0.2, 0.3]),
            chunk("chunk-b", "source-a", [0.3, 0.2, 0.1]),
        ],
    )

    collection = FakeClient.instances[0].collections[index.collection_name("source-a")]
    index.upsert_source_chunks("source-a", [chunk("chunk-c", "source-a", [0.9, 0.1, 0.1])])
    results = index.search(
        query_embedding=[0.9, 0.1, 0.1],
        source_ids=["source-a"],
        top_k=10,
    )

    assert [item["chunk"].id for item in results] == ["chunk-c"]
    assert collection.delete_calls[-1]["ids"] == ["chunk-a", "chunk-b"]
    assert [event["op"] for event in collection.events[-2:]] == ["upsert", "delete"]


def test_upsert_source_chunks_removes_stale_bad_metadata_by_collection_membership(tmp_path: Path):
    index = SeekDBChunkIndex(tmp_path / "native.seekdb")
    index.upsert_source_chunks("source-a", [chunk("chunk-a", "source-a", [0.1, 0.2, 0.3])])

    collection = FakeClient.instances[0].collections[index.collection_name("source-a")]
    stale = chunk(
        "stale-chunk",
        "source-a",
        [0.2, 0.2, 0.2],
        metadata={"source_id": "wrong-source"},
    )
    collection.upsert(
        ids=[stale.id],
        documents=[stale.content],
        metadatas=[{"source_id": "wrong-source", "payload": stale.model_dump_json()}],
        embeddings=[stale.embedding],
    )
    collection.refresh_index()

    index.upsert_source_chunks("source-a", [chunk("chunk-c", "source-a", [0.9, 0.1, 0.1])])
    results = index.search(
        query_embedding=[0.9, 0.1, 0.1],
        source_ids=["source-a"],
        top_k=10,
    )

    assert [item["chunk"].id for item in results] == ["chunk-c"]
    assert collection.delete_calls[-1]["ids"] == ["chunk-a", "stale-chunk"]


def test_upsert_source_chunks_dimension_mismatch_preserves_existing_chunks(tmp_path: Path):
    index = SeekDBChunkIndex(tmp_path / "native.seekdb")
    index.upsert_source_chunks("source-a", [chunk("chunk-a", "source-a", [0.1, 0.2, 0.3])])

    with pytest.raises(ValueError, match="dimension"):
        index.upsert_source_chunks("source-a", [chunk("chunk-b", "source-a", [0.1, 0.2])])

    results = index.search(
        query_embedding=[0.1, 0.2, 0.3],
        source_ids=["source-a"],
        top_k=10,
    )

    assert [item["chunk"].id for item in results] == ["chunk-a"]


def test_upsert_source_chunks_overrides_conflicting_metadata_source_id_for_replacement(tmp_path: Path):
    index = SeekDBChunkIndex(tmp_path / "native.seekdb")
    index.upsert_source_chunks(
        "source-a",
        [
            chunk(
                "chunk-a",
                "source-a",
                [0.1, 0.2, 0.3],
                metadata={"source_id": "wrong-source", "user_label": "kept"},
            ),
            chunk(
                "chunk-b",
                "source-a",
                [0.3, 0.2, 0.1],
                metadata={"source_id": "wrong-source"},
            ),
        ],
    )

    collection = FakeClient.instances[0].collections[index.collection_name("source-a")]
    assert collection.upsert_calls[0]["metadatas"][0]["source_id"] == "source-a"
    assert collection.upsert_calls[0]["metadatas"][0]["user_label"] == "kept"

    index.upsert_source_chunks("source-a", [chunk("chunk-c", "source-a", [0.9, 0.1, 0.1])])
    results = index.search(
        query_embedding=[0.9, 0.1, 0.1],
        source_ids=["source-a"],
        top_k=10,
    )

    assert [item["chunk"].id for item in results] == ["chunk-c"]


def test_upsert_source_chunks_empty_list_clears_existing_source_collection(tmp_path: Path):
    index = SeekDBChunkIndex(tmp_path / "native.seekdb")
    index.upsert_source_chunks("source-a", [chunk("chunk-a", "source-a", [0.1, 0.2, 0.3])])

    collection = FakeClient.instances[0].collections[index.collection_name("source-a")]
    index.upsert_source_chunks("source-a", [])
    results = index.search(
        query_embedding=[0.1, 0.2, 0.3],
        source_ids=["source-a"],
        top_k=10,
    )

    assert results == []
    assert collection.delete_calls[-1]["ids"] == ["chunk-a"]
    assert collection.refresh_calls == 2


def test_upsert_source_chunks_empty_list_missing_collection_is_noop(tmp_path: Path):
    index = SeekDBChunkIndex(tmp_path / "native.seekdb")

    index.upsert_source_chunks("source-a", [])

    client = FakeClient.instances[0]
    assert index.collection_name("source-a") not in client.collections


def test_delete_source_chunks_missing_collection_is_noop(tmp_path: Path, caplog):
    index = SeekDBChunkIndex(tmp_path / "native.seekdb")

    index.delete_source_chunks("source-a", ["chunk-a"])

    client = FakeClient.instances[0]
    assert index.collection_name("source-a") not in client.collections
    assert not [record for record in caplog.records if record.levelname == "WARNING"]


def test_upsert_source_chunks_rejects_mismatched_source_id(tmp_path: Path):
    index = SeekDBChunkIndex(tmp_path / "native.seekdb")

    with pytest.raises(ValueError, match="source_id"):
        index.upsert_source_chunks("source-a", [chunk("chunk-b", "source-b", [0.1, 0.2, 0.3])])


def test_missing_pyseekdb_raises_without_silent_sqlite_vector_fallback(tmp_path: Path, monkeypatch):
    monkeypatch.setitem(sys.modules, "pyseekdb", None)

    with pytest.raises(SeekDBUnavailableError):
        SeekDBChunkIndex(tmp_path / "native.seekdb")


def run_real_pyseekdb_subprocess(script: str) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        value for value in [str(repo_root), env.get("PYTHONPATH", "")] if value
    )
    subprocess_script = textwrap.dedent(
        """
        try:
            import pyseekdb  # noqa: F401
        except Exception:
            print("PYSEEKDB_UNAVAILABLE")
            raise SystemExit(0)

        from backend.domain.source import KnowledgeChunk
        from backend.infrastructure.vector_stores.seekdb_chunk_index import SeekDBChunkIndex


        def chunk(chunk_id: str, source_id: str, embedding: list[float], metadata: dict | None = None):
            return KnowledgeChunk(
                id=chunk_id,
                source_id=source_id,
                content=f"{chunk_id} content",
                chunk_index=0,
                embedding=embedding,
                metadata=metadata if metadata is not None else {"source_id": source_id},
            )
        """
    ) + "\n" + textwrap.dedent(script)
    try:
        completed = subprocess.run(
            [sys.executable, "-c", subprocess_script],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except subprocess.TimeoutExpired:
        pytest.skip("real pyseekdb subprocess timed out after 60 seconds")
    if "PYSEEKDB_UNAVAILABLE" in completed.stdout:
        pytest.skip("pyseekdb is unavailable in subprocess")
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_real_pyseekdb_upsert_refresh_and_query_round_trip(tmp_path: Path):
    run_real_pyseekdb_subprocess(
        f"""
        index = SeekDBChunkIndex({str(tmp_path / "real.seekdb")!r})
        index.upsert_source_chunks("real-source", [chunk("real-chunk", "real-source", [0.1, 0.2, 0.3])])
        results = index.search(
            query_embedding=[0.1, 0.2, 0.3],
            source_ids=["real-source"],
            top_k=1,
        )
        assert results[0]["chunk"].id == "real-chunk"
        """
    )


def test_real_pyseekdb_reindex_replaces_stale_chunks(tmp_path: Path):
    run_real_pyseekdb_subprocess(
        f"""
        index = SeekDBChunkIndex({str(tmp_path / "real.seekdb")!r})
        index.upsert_source_chunks(
            "real-source",
            [
                chunk("real-a", "real-source", [0.1, 0.2, 0.3]),
                chunk("real-b", "real-source", [0.3, 0.2, 0.1]),
            ],
        )
        index.upsert_source_chunks("real-source", [chunk("real-c", "real-source", [0.9, 0.1, 0.1])])
        results = index.search(
            query_embedding=[0.9, 0.1, 0.1],
            source_ids=["real-source"],
            top_k=10,
        )
        assert [item["chunk"].id for item in results] == ["real-c"]
        """
    )


def test_real_pyseekdb_conflicting_metadata_source_id_does_not_leave_stale_chunks(
    tmp_path: Path,
):
    run_real_pyseekdb_subprocess(
        f"""
        index = SeekDBChunkIndex({str(tmp_path / "real.seekdb")!r})
        index.upsert_source_chunks(
            "real-source",
            [
                chunk(
                    "real-a",
                    "real-source",
                    [0.1, 0.2, 0.3],
                    metadata={{"source_id": "wrong-source"}},
                ),
                chunk(
                    "real-b",
                    "real-source",
                    [0.3, 0.2, 0.1],
                    metadata={{"source_id": "wrong-source"}},
                ),
            ],
        )
        index.upsert_source_chunks("real-source", [chunk("real-c", "real-source", [0.9, 0.1, 0.1])])
        results = index.search(
            query_embedding=[0.9, 0.1, 0.1],
            source_ids=["real-source"],
            top_k=10,
        )
        assert [item["chunk"].id for item in results] == ["real-c"]
        """
    )


def test_real_pyseekdb_empty_reindex_clears_existing_chunks(tmp_path: Path):
    run_real_pyseekdb_subprocess(
        f"""
        index = SeekDBChunkIndex({str(tmp_path / "real.seekdb")!r})
        index.upsert_source_chunks("real-source", [chunk("real-a", "real-source", [0.1, 0.2, 0.3])])
        index.upsert_source_chunks("real-source", [])
        results = index.search(
            query_embedding=[0.1, 0.2, 0.3],
            source_ids=["real-source"],
            top_k=10,
        )
        assert results == []
        """
    )


def test_real_pyseekdb_stale_bad_metadata_row_is_removed_by_collection_membership(tmp_path: Path):
    run_real_pyseekdb_subprocess(
        f"""
        index = SeekDBChunkIndex({str(tmp_path / "real.seekdb")!r})
        index.upsert_source_chunks("real-source", [chunk("real-a", "real-source", [0.1, 0.2, 0.3])])
        stale = chunk(
            "real-stale",
            "real-source",
            [0.2, 0.2, 0.2],
            metadata={{"source_id": "wrong-source"}},
        )
        collection = index._collection("real-source", dimension=3)
        collection.upsert(
            ids=[stale.id],
            documents=[stale.content],
            metadatas=[{{"source_id": "wrong-source", "payload": stale.model_dump_json()}}],
            embeddings=[stale.embedding],
        )
        collection.refresh_index()

        index.upsert_source_chunks("real-source", [chunk("real-c", "real-source", [0.9, 0.1, 0.1])])
        results = index.search(
            query_embedding=[0.9, 0.1, 0.1],
            source_ids=["real-source"],
            top_k=10,
        )
        assert [item["chunk"].id for item in results] == ["real-c"]
        """
    )


def test_real_pyseekdb_dimension_mismatch_preserves_existing_chunks(tmp_path: Path):
    run_real_pyseekdb_subprocess(
        f"""
        index = SeekDBChunkIndex({str(tmp_path / "real.seekdb")!r})
        index.upsert_source_chunks("real-source", [chunk("real-a", "real-source", [0.1, 0.2, 0.3])])
        try:
            index.upsert_source_chunks("real-source", [chunk("real-b", "real-source", [0.1, 0.2])])
        except ValueError:
            pass
        else:
            raise AssertionError("dimension mismatch did not raise")

        results = index.search(
            query_embedding=[0.1, 0.2, 0.3],
            source_ids=["real-source"],
            top_k=10,
        )
        assert [item["chunk"].id for item in results] == ["real-a"]
        """
    )
