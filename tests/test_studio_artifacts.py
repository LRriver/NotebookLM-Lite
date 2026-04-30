from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes.artifacts import get_artifact_llm_factory, router as artifacts_router
from backend.core.services.artifact_service import ArtifactService
from backend.core.services.source_service import SourceService
from backend.dependencies import get_knowledge_repository
from backend.infrastructure.parsers.docling_parser import DoclingParser
from backend.infrastructure.repositories.seekdb_repository import SeekDBRepository


class ArtifactLLM:
    async def generate_structured(self, prompt, response_model, system_prompt=None, temperature=0.7, **kwargs):
        name = response_model.__name__
        if name == "MindMapArtifactPayload":
            return response_model.model_validate(
                {"title": "Map", "root": {"id": "root", "label": "Topic", "children": []}}
            )
        if name == "FAQArtifactPayload":
            return response_model.model_validate(
                {"title": "FAQ", "items": [{"question": "Q?", "answer": "A"}]}
            )
        if name == "FlashcardsArtifactPayload":
            return response_model.model_validate(
                {
                    "title": "Cards",
                    "cards": [{"front": "F", "back": "B"}],
                    "quiz": [
                        {
                            "question": "Q?",
                            "options": ["A", "B"],
                            "answer": "A",
                            "explanation": "Because source says A.",
                        }
                    ],
                }
            )
        if name == "DataTableArtifactPayload":
            return response_model.model_validate(
                {"title": "Table", "columns": ["Name"], "rows": [{"Name": "Alpha"}]}
            )
        if name == "InfographicArtifactPayload":
            return response_model.model_validate(
                {
                    "title": "Source Infographic",
                    "subtitle": "A visual summary grounded in the selected source.",
                    "sections": [
                        {
                            "heading": "Core idea",
                            "body": "Alpha studio material is the central evidence.",
                            "stat": "1 source",
                        }
                    ],
                    "footer": "Generated from selected sources.",
                }
            )
        if name == "PPTOutlineArtifactPayload":
            return response_model.model_validate(
                {"title": "Deck", "slides": [{"title": "Intro"}], "adapter_status": "placeholder"}
            )
        return response_model.model_validate(
            {
                "title": "Report",
                "summary": "Summary",
                "sections": [{"heading": "H", "body": "B"}],
                "key_takeaways": ["K"],
            }
        )


class BrokenArtifactLLM:
    async def generate_structured(self, *args, **kwargs):
        raise ValueError("bad structured output")


@pytest.mark.asyncio
async def test_generates_each_text_artifact_type(tmp_path):
    repo = SeekDBRepository(tmp_path / "studio.db")
    source_service = SourceService(repo, parser=DoclingParser(), chunk_size=128, chunk_overlap=0)
    source = await source_service.create_text_source("Studio", "Alpha studio material.")
    service = ArtifactService(repo, ArtifactLLM())

    for artifact_type in ["mind_map", "faq", "flashcards", "report", "study_guide", "data_table", "infographic", "ppt_outline"]:
        artifact = await service.generate_artifact(artifact_type, [source.id])
        assert artifact.artifact_type.value == artifact_type
        assert artifact.payload["title"]
        assert artifact.markdown.startswith("# ")
        if artifact_type == "flashcards":
            assert artifact.payload["quiz"][0]["options"] == ["A", "B"]
            assert "## Quiz" in artifact.markdown
        if artifact_type == "ppt_outline":
            assert artifact.payload["adapter_status"] == "placeholder"
        if artifact_type == "infographic":
            assert artifact.payload["svg"].startswith("<svg")
            assert "Core idea" in artifact.markdown
            assert artifact.file_refs[0]["format"] == "svg"


@pytest.mark.asyncio
async def test_missing_media_artifacts_are_explicit_placeholders(tmp_path):
    repo = SeekDBRepository(tmp_path / "studio-placeholders.db")
    source_service = SourceService(repo, parser=DoclingParser(), chunk_size=128, chunk_overlap=0)
    source = await source_service.create_text_source("Studio", "Alpha studio material.")
    service = ArtifactService(repo, ArtifactLLM())

    artifact = await service.generate_artifact("video_overview", [source.id])
    assert artifact.artifact_type.value == "video_overview"
    assert artifact.payload["adapter_status"] == "placeholder"
    assert "not implemented" in artifact.payload["message"].lower()


def test_artifact_api_list_detail_download_and_research_placeholder(tmp_path):
    repo = SeekDBRepository(tmp_path / "studio-api.db")
    source_service = SourceService(repo, parser=DoclingParser(), chunk_size=128, chunk_overlap=0)
    source = asyncio.run(source_service.create_text_source("Studio", "Alpha studio material."))

    app = FastAPI()
    app.include_router(artifacts_router, prefix="/api")
    app.dependency_overrides[get_knowledge_repository] = lambda: repo
    app.dependency_overrides[get_artifact_llm_factory] = lambda: (lambda **kwargs: ArtifactLLM())
    client = TestClient(app)

    generated = client.post(
        "/api/artifacts/generate",
        json={"artifact_type": "mind_map", "source_ids": [source.id]},
    )
    assert generated.status_code == 200
    artifact_id = generated.json()["id"]

    listed = client.get("/api/artifacts")
    detail = client.get(f"/api/artifacts/{artifact_id}")
    markdown = client.get(f"/api/artifacts/{artifact_id}/download?format=markdown")
    as_json = client.get(f"/api/artifacts/{artifact_id}/download?format=json")
    as_svg = client.get(f"/api/artifacts/{artifact_id}/download?format=svg")
    research = client.post("/api/research/jobs", json={"query": "research this", "source_ids": [source.id]})

    assert listed.json()["total"] == 1
    assert detail.json()["payload"]["title"] == "Map"
    assert markdown.text.startswith("# Map")
    assert as_json.headers["content-type"].startswith("application/json")
    assert as_svg.status_code == 400
    assert research.json()["job_type"] == "deep_research"


def test_artifact_api_downloads_infographic_svg(tmp_path):
    repo = SeekDBRepository(tmp_path / "studio-api-infographic.db")
    source_service = SourceService(repo, parser=DoclingParser(), chunk_size=128, chunk_overlap=0)
    source = asyncio.run(source_service.create_text_source("Studio", "Alpha studio material."))

    app = FastAPI()
    app.include_router(artifacts_router, prefix="/api")
    app.dependency_overrides[get_knowledge_repository] = lambda: repo
    app.dependency_overrides[get_artifact_llm_factory] = lambda: (lambda **kwargs: ArtifactLLM())
    client = TestClient(app)

    generated = client.post(
        "/api/artifacts/generate",
        json={"artifact_type": "infographic", "source_ids": [source.id]},
    )
    assert generated.status_code == 200
    artifact_id = generated.json()["id"]

    as_svg = client.get(f"/api/artifacts/{artifact_id}/download?format=svg")

    assert as_svg.status_code == 200
    assert as_svg.headers["content-type"].startswith("image/svg+xml")
    assert "<svg" in as_svg.text


@pytest.mark.asyncio
async def test_artifact_generation_records_failed_job(tmp_path):
    repo = SeekDBRepository(tmp_path / "studio-fail.db")
    source_service = SourceService(repo, parser=DoclingParser(), chunk_size=128, chunk_overlap=0)
    source = await source_service.create_text_source("Studio", "Alpha studio material.")
    service = ArtifactService(repo, BrokenArtifactLLM())

    with pytest.raises(ValueError):
        await service.generate_artifact("faq", [source.id])

    row = repo._conn.execute("SELECT id FROM jobs").fetchone()
    job = await repo.get_job(row["id"])
    assert job.status.value == "failed"
