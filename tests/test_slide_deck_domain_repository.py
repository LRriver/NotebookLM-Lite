from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from backend.domain.slide_deck import (
    SlideDeckFileKind,
    SlideAsset,
    SlideAssetStage,
    SlideDeckExport,
    SlideDeckJob,
    SlideDeckJobStage,
    SlideDeckOutline,
    SlideDeckProject,
    SlideDeckStage,
    SlideDeckStatus,
    SlideExportFormat,
    SlideExportStatus,
    SlideOutline,
    SlidePromptPlan,
    SlidePromptPlanSet,
    SlideRecord,
    SlideStatus,
)
from backend.domain.source import JobStatus, KnowledgeChunk
from backend.infrastructure.slide_deck_files import SlideDeckFileStore
from backend.infrastructure.repositories.memory_repository import InMemoryKnowledgeRepository
from backend.infrastructure.repositories.seekdb_repository import SeekDBRepository


def test_slide_deck_project_defaults_and_source_lineage():
    outline = SlideDeckOutline(
        title="HTTP Security Overview",
        design_style="technical briefing",
        audience="engineers",
        slides=[
            SlideOutline(
                page=1,
                title="Why TLS matters",
                narrative_goal="Explain the risk of cleartext HTTP.",
                key_points=["Confidentiality", "Integrity"],
                visual_direction="Layered network diagram",
            )
        ],
    )
    prompt_plan = SlidePromptPlanSet(
        slide_prompts=[
            SlidePromptPlan(
                page=1,
                title="Why TLS matters",
                content_summary="TLS protects HTTP traffic.",
                display_content="TLS protects HTTP traffic.",
                prompt="Create a technical slide about TLS protection.",
            )
        ]
    )
    deck = SlideDeckProject(
        title="HTTP Security Overview",
        source_ids=["src_https"],
        source_snapshot=[
            {
                "source_id": "src_https",
                "title": "HTTPS.pdf",
                "chunk_ids": ["chunk_1"],
                "excerpt": "TLS protects HTTP traffic.",
            }
        ],
        config_snapshot={"page_count": 2, "aspect_ratio": "16:9"},
        outline=outline,
        prompt_plan=prompt_plan,
    )

    assert deck.id.startswith("deck_")
    assert deck.status == SlideDeckStatus.DRAFT
    assert deck.stage == SlideDeckStage.CREATED
    assert deck.source_ids == ["src_https"]
    assert deck.source_snapshot[0]["title"] == "HTTPS.pdf"
    assert deck.config_snapshot["aspect_ratio"] == "16:9"
    assert deck.outline.slides[0].page == 1
    assert deck.prompt_plan.slide_prompts[0].prompt.startswith("Create")


def test_slide_deck_project_rejects_invalid_outline_payload():
    with pytest.raises(ValueError):
        SlideDeckProject(
            title="Invalid",
            outline={
                "title": "",
                "design_style": "",
                "audience": "",
                "slides": [{"page": 0, "title": "", "narrative_goal": "", "visual_direction": ""}],
            },
        )


@pytest.mark.asyncio
async def test_memory_repository_persists_deck_asset_export_and_job(tmp_path: Path):
    repo = InMemoryKnowledgeRepository()
    deck = SlideDeckProject(title="Deck", source_ids=["src_1"])
    asset = SlideAsset(
        deck_id=deck.id,
        slide_id="slide_1",
        file_path=str(tmp_path / "slide_1.png"),
        mime_type="image/png",
        byte_size=12,
        checksum="abc123",
        download_ref="slide_decks/deck/slide_image/slide_1.png",
        stage=SlideAssetStage.GENERATED,
    )
    deck.slides.append(
        SlideRecord(
            id="slide_1",
            deck_id=deck.id,
            page_number=1,
            title="Intro",
            prompt="Create an intro slide",
            display_content="Intro content",
            asset_id=asset.id,
            status=SlideStatus.SUCCEEDED,
        )
    )
    export = SlideDeckExport(
        deck_id=deck.id,
        format=SlideExportFormat.PPTX,
        file_path=str(tmp_path / "deck.pptx"),
        filename="deck.pptx",
        byte_size=16,
        checksum="pptx123",
        download_ref="slide_decks/deck/export/deck.pptx",
        slide_count=1,
        status=SlideExportStatus.SUCCEEDED,
    )
    job = SlideDeckJob(
        deck_id=deck.id,
        stage=SlideDeckJobStage.EXPORT,
        status=JobStatus.PENDING,
        progress=0.0,
    )

    await repo.save_slide_deck(deck)
    await repo.save_slide_asset(asset)
    await repo.save_slide_export(export)
    await repo.save_slide_deck_job(job)
    job.status = JobStatus.RUNNING
    job.progress = 0.5
    await repo.save_slide_deck_job(job)
    job.status = JobStatus.SUCCEEDED
    job.progress = 1.0
    job.result_ref = export.id
    await repo.save_slide_deck_job(job)

    loaded = await repo.get_slide_deck(deck.id)
    assert loaded is not None
    assert loaded.slides[0].asset_id == asset.id
    assert (await repo.get_slide_asset(asset.id)).checksum == "abc123"
    assert (await repo.get_slide_asset(asset.id)).download_ref.endswith("slide_1.png")
    assert (await repo.list_slide_decks())[0].id == deck.id
    loaded_export = (await repo.list_slide_exports(deck.id))[0]
    assert loaded_export.id == export.id
    assert loaded_export.byte_size == 16
    assert loaded_export.checksum == "pptx123"
    assert loaded_export.download_ref.endswith("deck.pptx")
    loaded_job = await repo.get_slide_deck_job(job.id)
    assert loaded_job.result_ref == export.id
    assert loaded_job.progress == 1.0
    assert loaded_job.stage == SlideDeckJobStage.EXPORT


@pytest.mark.asyncio
async def test_seekdb_repository_persists_slide_deck_state_after_restart(tmp_path: Path):
    db_path = tmp_path / "knowledge.db"
    repo = SeekDBRepository(db_path)
    deck = SlideDeckProject(
        title="Durable deck",
        source_ids=["src_doc"],
        source_snapshot=[{"source_id": "src_doc", "title": "Document"}],
        status=SlideDeckStatus.GENERATING,
        stage=SlideDeckStage.SLIDES_GENERATING,
    )
    asset = SlideAsset(
        deck_id=deck.id,
        slide_id="slide_1",
        file_path=str(tmp_path / "slide_1.png"),
        mime_type="image/png",
        byte_size=4,
        checksum="sha256-demo",
        download_ref="slide_decks/deck/slide_image/slide_1.png",
        width=1600,
        height=900,
    )
    export = SlideDeckExport(
        deck_id=deck.id,
        format=SlideExportFormat.PPTX,
        file_path=str(tmp_path / "durable.pptx"),
        filename="durable.pptx",
        byte_size=9,
        checksum="sha256-pptx",
        download_ref="slide_decks/deck/export/durable.pptx",
        slide_count=1,
        status=SlideExportStatus.SUCCEEDED,
    )

    await repo.save_slide_deck(deck)
    await repo.save_slide_asset(asset)
    await repo.save_slide_export(export)
    job = SlideDeckJob(
        deck_id=deck.id,
        stage=SlideDeckJobStage.SLIDE_GENERATION,
        status=JobStatus.RUNNING,
        progress=0.25,
        retry_count=1,
    )
    await repo.save_slide_deck_job(job)
    await repo.close()

    reopened = SeekDBRepository(db_path)
    loaded = await reopened.get_slide_deck(deck.id)
    loaded_asset = await reopened.get_slide_asset(asset.id)
    loaded_exports = await reopened.list_slide_exports(deck.id)
    loaded_job = await reopened.get_slide_deck_job(job.id)

    loaded.title = "Updated after restart"
    loaded_asset.byte_size = 8
    loaded_exports[0].status = SlideExportStatus.FAILED
    loaded_job.status = JobStatus.FAILED
    await reopened.save_slide_deck(loaded)
    await reopened.save_slide_asset(loaded_asset)
    await reopened.save_slide_export(loaded_exports[0])
    await reopened.save_slide_deck_job(loaded_job)

    assert loaded is not None
    assert (await reopened.get_slide_deck(deck.id)).title == "Updated after restart"
    assert loaded.stage == SlideDeckStage.SLIDES_GENERATING
    assert loaded.source_snapshot[0]["title"] == "Document"
    assert loaded_asset is not None
    assert (await reopened.get_slide_asset(asset.id)).byte_size == 8
    assert (await reopened.get_slide_asset(asset.id)).download_ref.endswith("slide_1.png")
    assert (await reopened.get_slide_export(export.id)).status == SlideExportStatus.FAILED
    assert (await reopened.get_slide_export(export.id)).checksum == "sha256-pptx"
    assert (await reopened.get_slide_export(export.id)).download_ref.endswith("durable.pptx")
    assert (await reopened.get_slide_deck_job(job.id)).status == JobStatus.FAILED


def test_seekdb_repository_uses_separate_embedded_path_for_native_seekdb(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    calls: list[str] = []

    class FakeClient:
        def __init__(self, path: str) -> None:
            calls.append(path)
            Path(path).mkdir(parents=True, exist_ok=True)

        def list_collections(self):
            return []

    monkeypatch.setitem(sys.modules, "pyseekdb", types.SimpleNamespace(Client=FakeClient))

    db_path = tmp_path / "knowledge.db"
    repo = SeekDBRepository(db_path)

    assert calls == [str(tmp_path / "knowledge.seekdb")]
    assert db_path.is_file()
    assert repo.native_chunk_index is not None
    assert repo.storage_status()["seekdb_path"] == str(tmp_path / "knowledge.seekdb")
    assert repo.storage_status()["native_available"] is True


@pytest.mark.asyncio
async def test_seekdb_repository_uses_sqlite_chunk_search_only_when_fallback_is_enabled(tmp_path: Path):
    repo = SeekDBRepository(
        tmp_path / "knowledge.db",
        native_chunk_index=None,
        allow_sqlite_vector_fallback=True,
    )
    chunk = KnowledgeChunk(
        id="chunk_1",
        source_id="src_1",
        content="Hybrid retrieval should still use the durable SQLite store.",
        chunk_index=0,
        metadata={"title": "demo"},
    )

    await repo.save_chunks("src_1", [chunk])

    loaded = await repo.get_chunks("src_1")
    results = await repo.search_chunks("hybrid retrieval", top_k=1)
    assert [item.id for item in loaded] == ["chunk_1"]
    assert results[0]["chunk"].id == "chunk_1"
    assert repo.storage_status()["vector_backend"] == "sqlite_fallback"


def test_slide_deck_file_store_writes_ignored_files_and_returns_metadata(tmp_path: Path):
    store = SlideDeckFileStore(tmp_path / "output")

    image = store.save_file(
        deck_id="deck_1",
        kind=SlideDeckFileKind.SLIDE_IMAGE,
        filename="slide.png",
        content=b"image-bytes",
    )
    export = store.save_file(
        deck_id="deck_1",
        kind=SlideDeckFileKind.EXPORT,
        filename="deck.pptx",
        content=b"pptx-bytes",
    )

    assert image.path.exists()
    assert export.path.exists()
    assert image.path.is_relative_to(tmp_path / "output")
    assert export.path.is_relative_to(tmp_path / "output")
    assert image.checksum != export.checksum
    assert image.byte_size == len(b"image-bytes")
    assert export.download_ref.endswith("/deck.pptx")


def test_slide_deck_file_store_rejects_unsafe_deck_id(tmp_path: Path):
    store = SlideDeckFileStore(tmp_path / "output")

    with pytest.raises(ValueError):
        store.save_file(
            deck_id="../outside",
            kind=SlideDeckFileKind.SLIDE_IMAGE,
            filename="slide.png",
            content=b"image-bytes",
        )
