from __future__ import annotations

import base64
import asyncio
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes.artifacts import router as artifacts_router
from backend.api.routes.slide_decks import get_slide_deck_service, router as slide_decks_router
from backend.core.services.slide_deck_service import SlideDeckService
from backend.config import ModelProfile, Settings
from backend.dependencies import DependencyContainer
from backend.dependencies import get_knowledge_repository
from backend.domain.slide_deck import (
    SlideDeckJob,
    SlideDeckJobStage,
    SlideDeckOutline,
    SlideDeckProject,
    SlideDeckStage,
    SlideDeckStatus,
    SlideOutline,
    SlidePromptPlan,
    SlidePromptPlanSet,
    SlideStatus,
)
from backend.domain.source import JobStatus, KnowledgeSource, SourceKind, SourceStatus
from backend.infrastructure.repositories.memory_repository import InMemoryKnowledgeRepository
from backend.infrastructure.slide_deck_files import SlideDeckFileStore

PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAFgwJ/lrW3MgAAAABJRU5ErkJggg=="
)
EDITED_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


class FakePlanningService:
    def __init__(self, page_count: int = 1):
        self.page_count = page_count

    async def generate_outline(self, source_context, config, instruction=""):
        slides = [
            SlideOutline(
                page=page,
                title=f"Page {page}",
                narrative_goal="Introduce the source",
                key_points=["Alpha"],
                visual_direction="Clean diagram",
            )
            for page in range(1, self.page_count + 1)
        ]
        return SlideDeckOutline(
            title="Generated Deck",
            design_style="technical",
            audience="engineers",
            slides=slides,
        )

    async def generate_prompt_plan(self, source_context, outline, config, instruction=""):
        return SlidePromptPlanSet(
            slide_prompts=[
                SlidePromptPlan(
                    page=slide.page,
                    title=slide.title,
                    content_summary="Alpha summary",
                    display_content=f"Alpha display {slide.page}",
                    prompt=f"Create alpha slide {slide.page}",
                )
                for slide in outline.slides
            ]
        )


class FakeImageProvider:
    def __init__(self):
        self.generated = 0
        self.edited = 0
        self.last_edit_image_base64 = None
        self.profile = ModelProfile(
            model="fake-image-model",
            base_url="https://image.example/v1",
            api_key="fake-key",
            adapter="raw_chat_multimodal",
        )

    async def generate_image(self, prompt, aspect_ratio="16:9", quality="2K"):
        self.generated += 1
        return type(
            "ImageResult",
            (),
            {"base64_data": base64.b64encode(PNG_BYTES).decode(), "mime_type": "image/png"},
        )()

    async def edit_image(self, image_base64, instruction, aspect_ratio="16:9", quality="2K"):
        self.edited += 1
        self.last_edit_image_base64 = image_base64
        return type(
            "ImageResult",
            (),
            {"base64_data": base64.b64encode(EDITED_PNG_BYTES).decode(), "mime_type": "image/png"},
        )()


class FailingSecondImageProvider(FakeImageProvider):
    async def generate_image(self, prompt, aspect_ratio="16:9", quality="2K"):
        self.generated += 1
        if self.generated == 2:
            raise RuntimeError("image model failed on page 2")
        return type(
            "ImageResult",
            (),
            {"base64_data": base64.b64encode(PNG_BYTES).decode(), "mime_type": "image/png"},
        )()


class SlowImageProvider(FakeImageProvider):
    async def generate_image(self, prompt, aspect_ratio="16:9", quality="2K"):
        await asyncio.sleep(0.1)
        return await super().generate_image(prompt, aspect_ratio=aspect_ratio, quality=quality)


def build_client(tmp_path: Path, *, page_count: int = 1, image_provider=None):
    repo = InMemoryKnowledgeRepository()
    source = KnowledgeSource(
        id="src_alpha",
        kind=SourceKind.TEXT,
        title="Alpha Source",
        text="Alpha material for a slide deck.",
        status=SourceStatus.READY,
    )

    async def seed():
        await repo.save_source(source)

    asyncio.run(seed())

    edit_provider = FakeImageProvider()
    service = SlideDeckService(
        repository=repo,
        planning_service=FakePlanningService(page_count=page_count),
        image_provider=image_provider or FakeImageProvider(),
        edit_provider=edit_provider,
        file_store=SlideDeckFileStore(tmp_path / "output"),
    )

    app = FastAPI()
    app.include_router(slide_decks_router, prefix="/api")
    app.include_router(artifacts_router, prefix="/api")
    app.dependency_overrides[get_slide_deck_service] = lambda: service
    app.dependency_overrides[get_knowledge_repository] = lambda: repo
    return TestClient(app), repo


def test_slide_deck_api_full_mocked_workflow_and_recovery(tmp_path: Path):
    client, repo = build_client(tmp_path)

    created = client.post(
        "/api/slide-decks",
        json={
            "title": "Deck",
            "source_ids": ["src_alpha"],
            "config": {
                "page_count": 1,
                "api_key": "should-not-persist",
                "token": "should-not-persist",
                "bearer_token": "should-not-persist",
                "headers": {"authorization": "Bearer should-not-persist"},
                "nested": {"token": "should-not-persist"},
            },
        },
    )
    assert created.status_code == 200
    deck_id = created.json()["id"]
    assert created.json()["source_snapshot"][0]["title"] == "Alpha Source"
    assert len(created.json()["source_snapshot"][0]["content_sha256"]) == 64
    assert created.json()["source_snapshot"][0]["char_count"] == len("Alpha material for a slide deck.")
    assert created.json()["config_snapshot"]["model_lineage"]["image_model"]["model"] == "fake-image-model"
    assert created.json()["config_snapshot"]["model_lineage"]["image_model"]["api_key_set"] is True
    assert "api_key" not in created.json()["config_snapshot"]["model_lineage"]["image_model"]
    assert "api_key" not in created.json()["config_snapshot"]
    assert "token" not in created.json()["config_snapshot"]
    assert "bearer_token" not in created.json()["config_snapshot"]
    assert "headers" not in created.json()["config_snapshot"]
    assert "token" not in created.json()["config_snapshot"]["nested"]
    persisted_deck = repo.slide_decks[deck_id]
    assert "api_key" not in persisted_deck.config_snapshot
    assert "token" not in persisted_deck.config_snapshot
    assert "bearer_token" not in persisted_deck.config_snapshot
    assert "headers" not in persisted_deck.config_snapshot
    assert "token" not in persisted_deck.config_snapshot["nested"]

    outline_job = client.post(f"/api/slide-decks/{deck_id}/outline/jobs")
    assert outline_job.status_code == 200
    assert outline_job.json()["status"] == "succeeded"
    job_detail = client.get(f"/api/slide-decks/jobs/{outline_job.json()['id']}")
    assert job_detail.status_code == 200
    assert job_detail.json()["stage"] == "outline"
    assert client.get(f"/api/slide-decks/{deck_id}/jobs").json()["jobs"][0]["id"] == outline_job.json()["id"]

    detail = client.get(f"/api/slide-decks/{deck_id}")
    assert detail.json()["outline"]["title"] == "Generated Deck"

    confirmed_outline = client.patch(
        f"/api/slide-decks/{deck_id}/outline",
        json={"outline": detail.json()["outline"], "confirmed": True},
    )
    assert confirmed_outline.json()["stage"] == "outline_confirmed"

    prompt_job = client.post(f"/api/slide-decks/{deck_id}/prompt-plan/jobs")
    assert prompt_job.json()["status"] == "succeeded"
    prompt_detail = client.get(f"/api/slide-decks/{deck_id}").json()
    assert prompt_detail["prompt_plan"]["slide_prompts"][0]["prompt"] == "Create alpha slide 1"

    confirmed_plan = client.patch(
        f"/api/slide-decks/{deck_id}/prompt-plan",
        json={"prompt_plan": prompt_detail["prompt_plan"], "confirmed": True},
    )
    assert confirmed_plan.json()["stage"] == "prompt_plan_confirmed"

    slides_job = client.post(f"/api/slide-decks/{deck_id}/generate/jobs")
    assert slides_job.json()["status"] == "succeeded"
    generated = client.get(f"/api/slide-decks/{deck_id}").json()
    slide_id = generated["slides"][0]["id"]
    assert generated["slides"][0]["status"] == "succeeded"
    stored_asset = repo.slide_assets[generated["slides"][0]["asset_id"]]
    assert stored_asset.mime_type == "image/png"
    assert stored_asset.width == 1
    assert stored_asset.height == 1
    assert stored_asset.model_metadata["role"] == "image_model"
    assert stored_asset.model_metadata["model"] == "fake-image-model"

    regenerated = client.post(f"/api/slide-decks/{deck_id}/slides/{slide_id}/regenerate")
    assert regenerated.json()["slides"][0]["asset_id"] != generated["slides"][0]["asset_id"]

    edited = client.post(
        f"/api/slide-decks/{deck_id}/slides/{slide_id}/edit",
        json={"instruction": "Make the title shorter"},
    )
    assert edited.json()["slides"][0]["edit_history"][0]["instruction"] == "Make the title shorter"

    recovered = client.get(f"/api/slide-decks/{deck_id}")
    assert recovered.status_code == 200
    assert recovered.json()["slides"][0]["edit_history"]

    artifacts = client.get("/api/artifacts")
    assert artifacts.status_code == 200
    assert artifacts.json()["total"] == 1
    assert artifacts.json()["artifacts"][0]["artifact_type"] == "slide_deck"
    assert artifacts.json()["artifacts"][0]["status"] == "succeeded"

    listed = client.get("/api/slide-decks")
    assert listed.json()["total"] == 1
    assert listed.json()["decks"][0]["id"] == deck_id


def test_slide_deck_api_rejects_missing_sources(tmp_path: Path):
    client, _ = build_client(tmp_path)

    response = client.post(
        "/api/slide-decks",
        json={"title": "Deck", "source_ids": [], "config": {"page_count": 1}},
    )

    assert response.status_code == 400
    assert "source_ids" in response.json()["detail"]


def test_slide_deck_service_dependency_is_cached_for_background_job_tracking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo = InMemoryKnowledgeRepository()
    settings = Settings(output_dir=str(tmp_path / "output"), seekdb_path=str(tmp_path / "knowledge.db"))

    DependencyContainer.reset_runtime_caches()
    monkeypatch.setattr("backend.dependencies.get_settings", lambda: settings)
    monkeypatch.setattr(
        DependencyContainer,
        "get_knowledge_repository",
        classmethod(lambda cls, settings=None, force_new=False: repo),
    )

    first = DependencyContainer.get_slide_deck_service()
    second = DependencyContainer.get_slide_deck_service()

    assert first is second
    DependencyContainer.reset_runtime_caches()


def test_slide_deck_api_enforces_confirmation_gates(tmp_path: Path):
    client, _ = build_client(tmp_path)

    created = client.post(
        "/api/slide-decks",
        json={"title": "Deck", "source_ids": ["src_alpha"], "config": {"page_count": 1}},
    )
    deck_id = created.json()["id"]
    client.post(f"/api/slide-decks/{deck_id}/outline/jobs")

    blocked_prompt_plan = client.post(f"/api/slide-decks/{deck_id}/prompt-plan/jobs")
    assert blocked_prompt_plan.status_code == 400
    assert "confirmed outline" in blocked_prompt_plan.json()["detail"]

    outline = client.get(f"/api/slide-decks/{deck_id}").json()["outline"]
    client.patch(f"/api/slide-decks/{deck_id}/outline", json={"outline": outline, "confirmed": True})
    client.post(f"/api/slide-decks/{deck_id}/prompt-plan/jobs")

    blocked_slides = client.post(f"/api/slide-decks/{deck_id}/generate/jobs")
    assert blocked_slides.status_code == 400
    assert "confirmed prompt plan" in blocked_slides.json()["detail"]


def test_slide_deck_api_rejects_invalid_outline_and_prompt_plan_page_sequences(tmp_path: Path):
    client, _ = build_client(tmp_path, page_count=2)

    created = client.post(
        "/api/slide-decks",
        json={"title": "Deck", "source_ids": ["src_alpha"], "config": {"page_count": 2}},
    )
    deck_id = created.json()["id"]
    client.post(f"/api/slide-decks/{deck_id}/outline/jobs")
    detail = client.get(f"/api/slide-decks/{deck_id}").json()

    empty_outline = {**detail["outline"], "slides": []}
    response = client.patch(
        f"/api/slide-decks/{deck_id}/outline",
        json={"outline": empty_outline, "confirmed": True},
    )
    assert response.status_code == 400
    assert "page sequence" in response.json()["detail"]

    duplicate_outline = {
        **detail["outline"],
        "slides": [
            {**detail["outline"]["slides"][0], "page": 1},
            {**detail["outline"]["slides"][0], "page": 1, "title": "Duplicate"},
        ],
    }
    response = client.patch(
        f"/api/slide-decks/{deck_id}/outline",
        json={"outline": duplicate_outline, "confirmed": True},
    )
    assert response.status_code == 400
    assert "page sequence" in response.json()["detail"]

    client.patch(f"/api/slide-decks/{deck_id}/outline", json={"outline": detail["outline"], "confirmed": True})
    client.post(f"/api/slide-decks/{deck_id}/prompt-plan/jobs")
    prompt_plan = client.get(f"/api/slide-decks/{deck_id}").json()["prompt_plan"]
    missing_page_plan = {**prompt_plan, "slide_prompts": prompt_plan["slide_prompts"][:1]}
    response = client.patch(
        f"/api/slide-decks/{deck_id}/prompt-plan",
        json={"prompt_plan": missing_page_plan, "confirmed": True},
    )
    assert response.status_code == 400
    assert "page sequence" in response.json()["detail"]


def test_confirmed_plans_cannot_be_rewritten_after_slide_generation(tmp_path: Path):
    client, _ = build_client(tmp_path)

    created = client.post(
        "/api/slide-decks",
        json={"title": "Deck", "source_ids": ["src_alpha"], "config": {"page_count": 1}},
    )
    deck_id = created.json()["id"]
    client.post(f"/api/slide-decks/{deck_id}/outline/jobs")
    outline = client.get(f"/api/slide-decks/{deck_id}").json()["outline"]
    client.patch(f"/api/slide-decks/{deck_id}/outline", json={"outline": outline, "confirmed": True})
    client.post(f"/api/slide-decks/{deck_id}/prompt-plan/jobs")
    prompt_plan = client.get(f"/api/slide-decks/{deck_id}").json()["prompt_plan"]
    client.patch(f"/api/slide-decks/{deck_id}/prompt-plan", json={"prompt_plan": prompt_plan, "confirmed": True})
    client.post(f"/api/slide-decks/{deck_id}/generate/jobs")

    response = client.patch(
        f"/api/slide-decks/{deck_id}/outline",
        json={"outline": {**outline, "title": "Late rewrite"}, "confirmed": True},
    )
    assert response.status_code == 400
    assert "cannot be changed" in response.json()["detail"]

    response = client.patch(
        f"/api/slide-decks/{deck_id}/prompt-plan",
        json={"prompt_plan": prompt_plan, "confirmed": True},
    )
    assert response.status_code == 400
    assert "cannot be changed" in response.json()["detail"]


def test_edit_slide_requires_existing_generated_image(tmp_path: Path):
    client, _ = build_client(tmp_path, page_count=2, image_provider=FailingSecondImageProvider())

    created = client.post(
        "/api/slide-decks",
        json={"title": "Deck", "source_ids": ["src_alpha"], "config": {"page_count": 2}},
    )
    deck_id = created.json()["id"]
    client.post(f"/api/slide-decks/{deck_id}/outline/jobs")
    outline = client.get(f"/api/slide-decks/{deck_id}").json()["outline"]
    client.patch(f"/api/slide-decks/{deck_id}/outline", json={"outline": outline, "confirmed": True})
    client.post(f"/api/slide-decks/{deck_id}/prompt-plan/jobs")
    prompt_plan = client.get(f"/api/slide-decks/{deck_id}").json()["prompt_plan"]
    client.patch(f"/api/slide-decks/{deck_id}/prompt-plan", json={"prompt_plan": prompt_plan, "confirmed": True})
    client.post(f"/api/slide-decks/{deck_id}/generate/jobs")
    failed_slide = [
        slide
        for slide in client.get(f"/api/slide-decks/{deck_id}").json()["slides"]
        if slide["status"] == "failed"
    ][0]

    response = client.post(
        f"/api/slide-decks/{deck_id}/slides/{failed_slide['id']}/edit",
        json={"instruction": "Make this slide more visual"},
    )

    assert response.status_code == 400
    assert "slide image" in response.json()["detail"]


@pytest.mark.asyncio
async def test_slide_generation_can_start_as_background_job_with_inspectable_progress(tmp_path: Path):
    repo = InMemoryKnowledgeRepository()
    await repo.save_source(
        KnowledgeSource(
            id="src_alpha",
            kind=SourceKind.TEXT,
            title="Alpha Source",
            text="Alpha material for a slide deck.",
            status=SourceStatus.READY,
        )
    )
    service = SlideDeckService(
        repository=repo,
        planning_service=FakePlanningService(page_count=2),
        image_provider=SlowImageProvider(),
        edit_provider=FakeImageProvider(),
        file_store=SlideDeckFileStore(tmp_path / "output"),
    )
    deck = await service.create_deck("Deck", ["src_alpha"], {"page_count": 2})
    await service.generate_outline(deck.id)
    deck = await service.get_deck(deck.id)
    await service.confirm_outline(deck.id, deck.outline, confirmed=True)
    await service.generate_prompt_plan(deck.id)
    deck = await service.get_deck(deck.id)
    await service.confirm_prompt_plan(deck.id, deck.prompt_plan, confirmed=True)

    job = await service.queue_generate_slides(deck.id)
    await asyncio.sleep(0)

    assert job.stage == SlideDeckJobStage.SLIDE_GENERATION
    assert job.status == JobStatus.RUNNING
    started = await service.get_deck(deck.id)
    assert started.stage == SlideDeckStage.SLIDES_GENERATING
    assert started.status == SlideDeckStatus.GENERATING
    assert [slide.status for slide in started.slides] == [SlideStatus.GENERATING, SlideStatus.PENDING]

    detail = await service.get_job(job.id)
    assert detail.stage == SlideDeckJobStage.SLIDE_GENERATION

    for _ in range(20):
        detail = await service.get_job(job.id)
        if detail.status == JobStatus.SUCCEEDED:
            break
        await asyncio.sleep(0.05)
    assert detail.status == JobStatus.SUCCEEDED


def test_restarted_service_marks_orphaned_background_slide_job_failed(tmp_path: Path):
    repo = InMemoryKnowledgeRepository()
    deck = SlideDeckProject(
        title="Interrupted deck",
        source_ids=["src_alpha"],
        stage=SlideDeckStage.SLIDES_GENERATING,
        status=SlideDeckStatus.GENERATING,
        prompt_plan=SlidePromptPlanSet(
            slide_prompts=[
                SlidePromptPlan(
                    page=1,
                    title="Page 1",
                    content_summary="Alpha summary",
                    display_content="Alpha display 1",
                    prompt="Create alpha slide 1",
                )
            ]
        ),
    )
    job = SlideDeckJob(
        deck_id=deck.id,
        stage=SlideDeckJobStage.SLIDE_GENERATION,
        status=JobStatus.RUNNING,
        progress=0.25,
    )

    async def seed():
        await repo.save_slide_deck(deck)
        await repo.save_slide_deck_job(job)

    asyncio.run(seed())
    restarted_service = SlideDeckService(
        repository=repo,
        planning_service=FakePlanningService(page_count=1),
        image_provider=FakeImageProvider(),
        edit_provider=FakeImageProvider(),
        file_store=SlideDeckFileStore(tmp_path / "output"),
    )

    recovered = asyncio.run(restarted_service.get_deck(deck.id))
    recovered_job = asyncio.run(restarted_service.get_job(job.id))

    assert recovered.status == SlideDeckStatus.FAILED
    assert recovered.stage == SlideDeckStage.SLIDES_GENERATING
    assert "interrupted" in recovered.error.lower()
    assert recovered_job.status == JobStatus.FAILED
    assert "interrupted" in recovered_job.error.lower()


def test_outline_generation_cannot_rewind_ready_deck(tmp_path: Path):
    client, _ = build_client(tmp_path)

    created = client.post(
        "/api/slide-decks",
        json={"title": "Deck", "source_ids": ["src_alpha"], "config": {"page_count": 1}},
    )
    deck_id = created.json()["id"]
    client.post(f"/api/slide-decks/{deck_id}/outline/jobs")
    outline = client.get(f"/api/slide-decks/{deck_id}").json()["outline"]
    client.patch(f"/api/slide-decks/{deck_id}/outline", json={"outline": outline, "confirmed": True})
    client.post(f"/api/slide-decks/{deck_id}/prompt-plan/jobs")
    prompt_plan = client.get(f"/api/slide-decks/{deck_id}").json()["prompt_plan"]
    client.patch(f"/api/slide-decks/{deck_id}/prompt-plan", json={"prompt_plan": prompt_plan, "confirmed": True})
    client.post(f"/api/slide-decks/{deck_id}/generate/jobs")
    ready = client.get(f"/api/slide-decks/{deck_id}").json()
    assert ready["stage"] == "slides_ready"

    response = client.post(f"/api/slide-decks/{deck_id}/outline/jobs")

    assert response.status_code == 400
    assert "before prompt planning" in response.json()["detail"]
    unchanged = client.get(f"/api/slide-decks/{deck_id}").json()
    assert unchanged["stage"] == "slides_ready"
    assert unchanged["slides"][0]["status"] == "succeeded"


def test_slide_generation_job_records_partial_failure_and_keeps_recoverable_state(tmp_path: Path):
    client, _ = build_client(tmp_path, page_count=2, image_provider=FailingSecondImageProvider())

    created = client.post(
        "/api/slide-decks",
        json={"title": "Deck", "source_ids": ["src_alpha"], "config": {"page_count": 2}},
    )
    deck_id = created.json()["id"]
    client.post(f"/api/slide-decks/{deck_id}/outline/jobs")
    outline = client.get(f"/api/slide-decks/{deck_id}").json()["outline"]
    client.patch(f"/api/slide-decks/{deck_id}/outline", json={"outline": outline, "confirmed": True})
    client.post(f"/api/slide-decks/{deck_id}/prompt-plan/jobs")
    prompt_plan = client.get(f"/api/slide-decks/{deck_id}").json()["prompt_plan"]
    client.patch(f"/api/slide-decks/{deck_id}/prompt-plan", json={"prompt_plan": prompt_plan, "confirmed": True})

    job = client.post(f"/api/slide-decks/{deck_id}/generate/jobs")

    assert job.status_code == 200
    assert job.json()["status"] == "failed"
    assert "page 2" in job.json()["error"]

    recovered = client.get(f"/api/slide-decks/{deck_id}").json()
    assert recovered["status"] == "failed"
    assert recovered["stage"] == "slides_generating"
    assert [slide["status"] for slide in recovered["slides"]] == ["succeeded", "failed"]
    assert recovered["slides"][0]["asset_id"]
    assert "page 2" in recovered["slides"][1]["error"]

    artifacts = client.get("/api/artifacts").json()
    assert artifacts["artifacts"][0]["status"] == "failed"
    assert artifacts["artifacts"][0]["payload"]["deck_status"] == "failed"

    retry_job = client.post(f"/api/slide-decks/{deck_id}/generate/jobs")
    assert retry_job.status_code == 200
    assert retry_job.json()["status"] == "succeeded"
    retry_recovered = client.get(f"/api/slide-decks/{deck_id}").json()
    assert retry_recovered["status"] == "ready"
    assert retry_recovered["stage"] == "slides_ready"
    assert retry_recovered["error"] is None
    assert [slide["status"] for slide in retry_recovered["slides"]] == ["succeeded", "succeeded"]


def test_regenerating_failed_slide_clears_deck_error_when_all_slides_succeed(tmp_path: Path):
    client, _ = build_client(tmp_path, page_count=2, image_provider=FailingSecondImageProvider())

    created = client.post(
        "/api/slide-decks",
        json={"title": "Deck", "source_ids": ["src_alpha"], "config": {"page_count": 2}},
    )
    deck_id = created.json()["id"]
    client.post(f"/api/slide-decks/{deck_id}/outline/jobs")
    outline = client.get(f"/api/slide-decks/{deck_id}").json()["outline"]
    client.patch(f"/api/slide-decks/{deck_id}/outline", json={"outline": outline, "confirmed": True})
    client.post(f"/api/slide-decks/{deck_id}/prompt-plan/jobs")
    prompt_plan = client.get(f"/api/slide-decks/{deck_id}").json()["prompt_plan"]
    client.patch(f"/api/slide-decks/{deck_id}/prompt-plan", json={"prompt_plan": prompt_plan, "confirmed": True})
    client.post(f"/api/slide-decks/{deck_id}/generate/jobs")
    failed_deck = client.get(f"/api/slide-decks/{deck_id}").json()
    failed_slide_id = [slide for slide in failed_deck["slides"] if slide["status"] == "failed"][0]["id"]

    regenerated = client.post(f"/api/slide-decks/{deck_id}/slides/{failed_slide_id}/regenerate")

    assert regenerated.status_code == 200
    assert regenerated.json()["status"] == "ready"
    assert regenerated.json()["stage"] == "slides_ready"
    assert regenerated.json()["error"] is None
    assert [slide["status"] for slide in regenerated.json()["slides"]] == ["succeeded", "succeeded"]


def test_regenerate_and_edit_keep_distinct_asset_files_for_history(tmp_path: Path):
    client, repo = build_client(tmp_path)

    created = client.post(
        "/api/slide-decks",
        json={"title": "Deck", "source_ids": ["src_alpha"], "config": {"page_count": 1}},
    )
    deck_id = created.json()["id"]
    client.post(f"/api/slide-decks/{deck_id}/outline/jobs")
    outline = client.get(f"/api/slide-decks/{deck_id}").json()["outline"]
    client.patch(f"/api/slide-decks/{deck_id}/outline", json={"outline": outline, "confirmed": True})
    client.post(f"/api/slide-decks/{deck_id}/prompt-plan/jobs")
    prompt_plan = client.get(f"/api/slide-decks/{deck_id}").json()["prompt_plan"]
    client.patch(f"/api/slide-decks/{deck_id}/prompt-plan", json={"prompt_plan": prompt_plan, "confirmed": True})
    client.post(f"/api/slide-decks/{deck_id}/generate/jobs")
    first_slide = client.get(f"/api/slide-decks/{deck_id}").json()["slides"][0]
    slide_id = first_slide["id"]
    first_asset = repo.slide_assets[first_slide["asset_id"]]
    first_path = Path(first_asset.file_path)
    first_content = first_path.read_bytes()

    regenerated = client.post(f"/api/slide-decks/{deck_id}/slides/{slide_id}/regenerate").json()
    second_asset = repo.slide_assets[regenerated["slides"][0]["asset_id"]]
    second_path = Path(second_asset.file_path)
    assert second_path != first_path
    assert first_path.read_bytes() == first_content

    edited = client.post(
        f"/api/slide-decks/{deck_id}/slides/{slide_id}/edit",
        json={"instruction": "Make the title shorter"},
    ).json()
    edit_history = edited["slides"][0]["edit_history"][0]
    assert edit_history["previous_asset_id"] == second_asset.id
    assert edit_history["model_metadata"]["role"] == "edit_model"
    edited_asset = repo.slide_assets[edit_history["next_asset_id"]]
    assert Path(edited_asset.file_path) not in {first_path, second_path}
    assert second_path.read_bytes() != Path(edited_asset.file_path).read_bytes()
