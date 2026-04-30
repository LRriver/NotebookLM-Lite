from __future__ import annotations

import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes.notes import router as notes_router
from backend.core.services.source_service import SourceService
from backend.dependencies import get_knowledge_repository, get_source_service
from backend.infrastructure.parsers.docling_parser import DoclingParser
from backend.infrastructure.repositories.seekdb_repository import SeekDBRepository


def test_notes_api_crud_and_convert_note_to_rag_source(tmp_path):
    repo = SeekDBRepository(tmp_path / "notes.db")
    source_service = SourceService(repo, parser=DoclingParser(), chunk_size=64, chunk_overlap=0)
    source = asyncio.run(source_service.create_text_source("HTTPS.pdf", "HTTPS uses TLS certificates."))

    app = FastAPI()
    app.include_router(notes_router, prefix="/api")
    app.dependency_overrides[get_knowledge_repository] = lambda: repo
    app.dependency_overrides[get_source_service] = lambda: source_service
    client = TestClient(app)

    created = client.post(
        "/api/notes",
        json={
            "title": "TLS 摘要",
            "body": "证书把服务器身份和公钥绑定起来。",
            "source_ids": [source.id],
            "tags": ["security", "tls"],
        },
    )
    assert created.status_code == 200
    note = created.json()
    assert note["title"] == "TLS 摘要"
    assert note["source_ids"] == [source.id]

    listed = client.get("/api/notes?query=证书")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["notes"][0]["tags"] == ["security", "tls"]

    updated = client.patch(
        f"/api/notes/{note['id']}",
        json={"body": "TLS 证书用于身份验证，也支持后续问答引用。"},
    )
    assert updated.status_code == 200
    assert "身份验证" in updated.json()["body"]

    converted = client.post(f"/api/notes/{note['id']}/source")
    assert converted.status_code == 200
    source_payload = converted.json()
    assert source_payload["kind"] == "text"
    assert source_payload["chunk_count"] >= 1
    assert source_payload["metadata"]["origin"] == "note"
    assert source_payload["metadata"]["note_id"] == note["id"]

    deleted = client.delete(f"/api/notes/{note['id']}")
    assert deleted.status_code == 200
    assert deleted.json()["success"] is True

    missing = client.get(f"/api/notes/{note['id']}")
    assert missing.status_code == 404
