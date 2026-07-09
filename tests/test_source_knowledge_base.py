from __future__ import annotations

import logging
from pathlib import Path
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
async def test_repository_requires_query_embedding_when_native_seekdb_is_primary(tmp_path: Path):
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

    with pytest.raises(RuntimeError, match="native SeekDB vector search requires query embeddings"):
        await repo.search_chunks("native query", source_ids=[source.id], top_k=1)


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
