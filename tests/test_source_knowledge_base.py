from __future__ import annotations

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
from backend.dependencies import get_source_service
from backend.infrastructure.parsers.docling_parser import DoclingParser
from backend.infrastructure.repositories.seekdb_repository import SeekDBRepository


@pytest.mark.asyncio
async def test_text_source_is_chunked_with_citation_metadata(tmp_path: Path):
    repo = SeekDBRepository(tmp_path / "knowledge.db")
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

    repo = SeekDBRepository(tmp_path / "knowledge.db")
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
    repo = SeekDBRepository(db_path)
    service = SourceService(repository=repo, parser=DoclingParser(), chunk_size=40, chunk_overlap=0)

    created = await service.create_text_source("Durable", "Persistent source text for restart.")
    await repo.close()

    reopened = SeekDBRepository(db_path)
    loaded = await reopened.get_source(created.id)
    chunks = await reopened.get_chunks(created.id)

    assert loaded is not None
    assert loaded.id == created.id
    assert loaded.title == "Durable"
    assert chunks[0].content.startswith("Persistent source")


@pytest.mark.asyncio
async def test_delete_source_removes_chunks_from_retrieval(tmp_path: Path):
    repo = SeekDBRepository(tmp_path / "knowledge.db")
    service = SourceService(repository=repo, parser=DoclingParser(), chunk_size=64, chunk_overlap=0)

    source = await service.create_text_source("Delete me", "Needle phrase should disappear.")
    before = await repo.search_chunks("Needle", source_ids=[source.id], top_k=3)
    deleted = await service.delete_source(source.id)
    after = await repo.search_chunks("Needle", source_ids=[source.id], top_k=3)

    assert before
    assert deleted is True
    assert after == []


def test_sources_api_text_upload_list_get_delete(tmp_path: Path):
    repo = SeekDBRepository(tmp_path / "api.db")
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
    repo = SeekDBRepository(tmp_path / "upload.db")
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
