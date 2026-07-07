"""Native slide deck workflow service."""

from __future__ import annotations

import base64
from typing import Any

from ...domain.slide_deck import (
    SlideAsset,
    SlideAssetStage,
    SlideDeckFileKind,
    SlideDeckJob,
    SlideDeckJobStage,
    SlideDeckOutline,
    SlideDeckProject,
    SlideDeckStage,
    SlideDeckStatus,
    SlideEditHistory,
    SlidePromptPlanSet,
    SlideRecord,
    SlideStatus,
)
from ...domain.source import Artifact, ArtifactType, JobStatus, new_id, utc_now
from ...infrastructure.slide_deck_files import SlideDeckFileStore
from ..interfaces.knowledge_repository import KnowledgeRepositoryInterface


class SlideDeckService:
    def __init__(
        self,
        repository: KnowledgeRepositoryInterface,
        planning_service: Any,
        image_provider: Any,
        edit_provider: Any,
        file_store: SlideDeckFileStore,
    ) -> None:
        self.repository = repository
        self.planning = planning_service
        self.image_provider = image_provider
        self.edit_provider = edit_provider
        self.file_store = file_store

    async def create_deck(
        self,
        title: str,
        source_ids: list[str],
        config: dict[str, Any],
    ) -> SlideDeckProject:
        if not source_ids:
            raise ValueError("source_ids is required")
        snapshot = []
        context_parts = []
        for source_id in source_ids:
            source = await self.repository.get_source(source_id)
            if not source:
                raise ValueError(f"source not found: {source_id}")
            snapshot.append(
                {
                    "source_id": source.id,
                    "title": source.title,
                    "filename": source.filename,
                    "excerpt": source.text[:800],
                }
            )
            context_parts.append(f"## {source.title}\n\n{source.text[:6000]}")
        safe_config = self._sanitize_config(config)
        deck = SlideDeckProject(
            title=title,
            source_ids=source_ids,
            source_snapshot=snapshot,
            config_snapshot={**safe_config, "source_context": "\n\n---\n\n".join(context_parts)},
        )
        await self.repository.save_slide_deck(deck)
        await self._upsert_deck_artifact(deck)
        return deck

    async def list_decks(self) -> list[SlideDeckProject]:
        return await self.repository.list_slide_decks()

    async def get_deck(self, deck_id: str) -> SlideDeckProject | None:
        return await self.repository.get_slide_deck(deck_id)

    async def get_job(self, job_id: str) -> SlideDeckJob | None:
        return await self.repository.get_slide_deck_job(job_id)

    async def list_jobs(self, deck_id: str) -> list[SlideDeckJob]:
        await self._require_deck(deck_id)
        return await self.repository.list_slide_deck_jobs(deck_id)

    async def generate_outline(self, deck_id: str) -> SlideDeckJob:
        deck = await self._require_deck(deck_id)
        now = utc_now()
        job = SlideDeckJob(
            deck_id=deck.id,
            stage=SlideDeckJobStage.OUTLINE,
            status=JobStatus.RUNNING,
            started_at=now,
        )
        await self.repository.save_slide_deck_job(job)
        try:
            deck.outline = await self.planning.generate_outline(
                deck.config_snapshot.get("source_context", ""),
                deck.config_snapshot,
            )
            deck.stage = SlideDeckStage.OUTLINE_READY
            deck.status = SlideDeckStatus.PLANNING
            deck.updated_at = utc_now()
            await self.repository.save_slide_deck(deck)
            job.status = JobStatus.SUCCEEDED
            job.progress = 1.0
            job.result_ref = deck.id
        except Exception as exc:
            job.status = JobStatus.FAILED
            job.error = str(exc)
        job.finished_at = utc_now()
        await self.repository.save_slide_deck_job(job)
        return job

    async def confirm_outline(
        self,
        deck_id: str,
        outline: SlideDeckOutline,
        confirmed: bool,
    ) -> SlideDeckProject:
        deck = await self._require_deck(deck_id)
        deck.outline = outline
        if confirmed:
            deck.stage = SlideDeckStage.OUTLINE_CONFIRMED
        deck.updated_at = utc_now()
        return await self.repository.save_slide_deck(deck)

    async def generate_prompt_plan(self, deck_id: str) -> SlideDeckJob:
        deck = await self._require_deck(deck_id)
        if not deck.outline or deck.stage != SlideDeckStage.OUTLINE_CONFIRMED:
            raise ValueError("confirmed outline is required")
        job = SlideDeckJob(
            deck_id=deck.id,
            stage=SlideDeckJobStage.PROMPT_PLAN,
            status=JobStatus.RUNNING,
            started_at=utc_now(),
        )
        await self.repository.save_slide_deck_job(job)
        try:
            deck.prompt_plan = await self.planning.generate_prompt_plan(
                deck.config_snapshot.get("source_context", ""),
                deck.outline,
                deck.config_snapshot,
            )
            deck.stage = SlideDeckStage.PROMPT_PLAN_READY
            deck.updated_at = utc_now()
            await self.repository.save_slide_deck(deck)
            job.status = JobStatus.SUCCEEDED
            job.progress = 1.0
            job.result_ref = deck.id
        except Exception as exc:
            job.status = JobStatus.FAILED
            job.error = str(exc)
        job.finished_at = utc_now()
        await self.repository.save_slide_deck_job(job)
        return job

    async def confirm_prompt_plan(
        self,
        deck_id: str,
        prompt_plan: SlidePromptPlanSet,
        confirmed: bool,
    ) -> SlideDeckProject:
        deck = await self._require_deck(deck_id)
        deck.prompt_plan = prompt_plan
        if confirmed:
            deck.stage = SlideDeckStage.PROMPT_PLAN_CONFIRMED
        deck.updated_at = utc_now()
        return await self.repository.save_slide_deck(deck)

    async def generate_slides(self, deck_id: str) -> SlideDeckJob:
        deck = await self._require_deck(deck_id)
        can_start = deck.stage == SlideDeckStage.PROMPT_PLAN_CONFIRMED
        can_resume = deck.stage == SlideDeckStage.SLIDES_GENERATING and deck.status == SlideDeckStatus.FAILED
        if not deck.prompt_plan or not (can_start or can_resume):
            raise ValueError("confirmed prompt plan is required")
        job = SlideDeckJob(
            deck_id=deck.id,
            stage=SlideDeckJobStage.SLIDE_GENERATION,
            status=JobStatus.RUNNING,
            started_at=utc_now(),
        )
        await self.repository.save_slide_deck_job(job)
        deck.stage = SlideDeckStage.SLIDES_GENERATING
        deck.status = SlideDeckStatus.GENERATING
        deck.error = None
        deck.slides = self._sync_slides_from_prompt_plan(deck)
        deck.updated_at = utc_now()
        await self.repository.save_slide_deck(deck)

        errors: list[str] = []
        total = len(deck.prompt_plan.slide_prompts)
        for index, item in enumerate(deck.prompt_plan.slide_prompts):
            slide = self._slide_by_page(deck, item.page)
            if slide.status == SlideStatus.SUCCEEDED and slide.asset_id:
                job.progress = (index + 1) / total if total else 1.0
                await self.repository.save_slide_deck_job(job)
                continue
            slide.status = SlideStatus.GENERATING
            slide.error = None
            slide.updated_at = utc_now()
            deck.updated_at = utc_now()
            await self.repository.save_slide_deck(deck)
            try:
                image = await self.image_provider.generate_image(
                    item.prompt,
                    aspect_ratio=str(deck.config_snapshot.get("aspect_ratio", "16:9")),
                    quality=str(deck.config_snapshot.get("quality", "2K")),
                )
                asset = await self._store_image_asset(deck.id, slide.id, image.base64_data, SlideAssetStage.GENERATED)
                slide.asset_id = asset.id
                slide.status = SlideStatus.SUCCEEDED
            except Exception as exc:
                slide.status = SlideStatus.FAILED
                slide.error = str(exc)
                errors.append(f"page {item.page}: {exc}")
            slide.updated_at = utc_now()
            deck.updated_at = utc_now()
            job.progress = (index + 1) / total if total else 1.0
            await self.repository.save_slide_deck(deck)
            await self.repository.save_slide_deck_job(job)

        if errors:
            deck.status = SlideDeckStatus.FAILED
            deck.stage = SlideDeckStage.SLIDES_GENERATING
            deck.error = "; ".join(errors)
            job.status = JobStatus.FAILED
            job.error = deck.error
        else:
            deck.stage = SlideDeckStage.SLIDES_READY
            deck.status = SlideDeckStatus.READY
            deck.error = None
            job.status = JobStatus.SUCCEEDED
            job.result_ref = deck.id
        deck.updated_at = utc_now()
        job.finished_at = utc_now()
        await self.repository.save_slide_deck(deck)
        await self._upsert_deck_artifact(deck)
        await self.repository.save_slide_deck_job(job)
        return job

    async def regenerate_slide(self, deck_id: str, slide_id: str) -> SlideDeckProject:
        deck = await self._require_deck(deck_id)
        slide = self._slide(deck, slide_id)
        image = await self.image_provider.generate_image(
            slide.prompt,
            aspect_ratio=str(deck.config_snapshot.get("aspect_ratio", "16:9")),
            quality=str(deck.config_snapshot.get("quality", "2K")),
        )
        asset = await self._store_image_asset(deck.id, slide.id, image.base64_data, SlideAssetStage.GENERATED)
        slide.asset_id = asset.id
        slide.status = SlideStatus.SUCCEEDED
        slide.error = None
        slide.updated_at = utc_now()
        self._refresh_deck_generation_status(deck)
        deck.updated_at = utc_now()
        await self.repository.save_slide_deck(deck)
        await self._upsert_deck_artifact(deck)
        return deck

    async def edit_slide(self, deck_id: str, slide_id: str, instruction: str) -> SlideDeckProject:
        deck = await self._require_deck(deck_id)
        slide = self._slide(deck, slide_id)
        previous_asset_id = slide.asset_id
        image_b64 = ""
        if previous_asset_id:
            asset = await self.repository.get_slide_asset(previous_asset_id)
            if asset:
                with open(asset.file_path, "rb") as file:
                    image_b64 = base64.b64encode(file.read()).decode()
        edited = await self.edit_provider.edit_image(
            image_b64,
            instruction,
            aspect_ratio=str(deck.config_snapshot.get("aspect_ratio", "16:9")),
            quality=str(deck.config_snapshot.get("quality", "2K")),
        )
        asset = await self._store_image_asset(deck.id, slide.id, edited.base64_data, SlideAssetStage.EDITED)
        slide.edit_history.append(
            SlideEditHistory(
                instruction=instruction,
                previous_asset_id=previous_asset_id,
                next_asset_id=asset.id,
            )
        )
        slide.asset_id = asset.id
        slide.updated_at = utc_now()
        deck.updated_at = utc_now()
        await self.repository.save_slide_deck(deck)
        await self._upsert_deck_artifact(deck)
        return deck

    async def _store_image_asset(
        self,
        deck_id: str,
        slide_id: str,
        image_base64: str,
        stage: SlideAssetStage,
    ) -> SlideAsset:
        content = base64.b64decode(image_base64)
        stored = self.file_store.save_file(
            deck_id=deck_id,
            kind=SlideDeckFileKind.SLIDE_IMAGE,
            filename=f"{slide_id}-{new_id('assetfile')}.png",
            content=content,
        )
        asset = SlideAsset(
            deck_id=deck_id,
            slide_id=slide_id,
            file_path=str(stored.path),
            mime_type="image/png",
            byte_size=stored.byte_size,
            checksum=stored.checksum,
            download_ref=stored.download_ref,
            stage=stage,
        )
        return await self.repository.save_slide_asset(asset)

    async def _upsert_deck_artifact(self, deck: SlideDeckProject) -> None:
        artifact = Artifact(
            id=f"art_{deck.id}",
            artifact_type=ArtifactType.SLIDE_DECK,
            title=deck.title,
            source_ids=deck.source_ids,
            payload={
                "deck_id": deck.id,
                "stage": deck.stage.value,
                "deck_status": deck.status.value,
                "slide_count": len(deck.slides),
                "error": deck.error,
            },
            markdown=f"# {deck.title}\n\nSlide Deck artifact: {deck.id}\n",
            status=JobStatus.FAILED if deck.status == SlideDeckStatus.FAILED else JobStatus.SUCCEEDED,
            error=deck.error,
        )
        await self.repository.save_artifact(artifact)

    async def _require_deck(self, deck_id: str) -> SlideDeckProject:
        deck = await self.repository.get_slide_deck(deck_id)
        if not deck:
            raise ValueError("slide deck not found")
        return deck

    @staticmethod
    def _slide(deck: SlideDeckProject, slide_id: str) -> SlideRecord:
        for slide in deck.slides:
            if slide.id == slide_id:
                return slide
        raise ValueError("slide not found")

    @staticmethod
    def _slide_by_page(deck: SlideDeckProject, page_number: int) -> SlideRecord:
        for slide in deck.slides:
            if slide.page_number == page_number:
                return slide
        raise ValueError(f"slide page not found: {page_number}")

    @staticmethod
    def _sync_slides_from_prompt_plan(deck: SlideDeckProject) -> list[SlideRecord]:
        if not deck.prompt_plan:
            return deck.slides
        existing_by_page = {slide.page_number: slide for slide in deck.slides}
        slides: list[SlideRecord] = []
        for item in deck.prompt_plan.slide_prompts:
            slide = existing_by_page.get(item.page)
            if slide is None:
                slide = SlideRecord(deck_id=deck.id, page_number=item.page, title=item.title)
            slide.title = item.title
            slide.prompt = item.prompt
            slide.display_content = item.display_content
            slide.content_summary = item.content_summary
            slides.append(slide)
        return slides

    @staticmethod
    def _refresh_deck_generation_status(deck: SlideDeckProject) -> None:
        if not deck.slides:
            return
        if all(slide.status == SlideStatus.SUCCEEDED for slide in deck.slides):
            deck.status = SlideDeckStatus.READY
            deck.stage = SlideDeckStage.SLIDES_READY
            deck.error = None
            return
        failed_errors = [
            f"page {slide.page_number}: {slide.error}"
            for slide in deck.slides
            if slide.status == SlideStatus.FAILED and slide.error
        ]
        if failed_errors:
            deck.status = SlideDeckStatus.FAILED
            deck.stage = SlideDeckStage.SLIDES_GENERATING
            deck.error = "; ".join(failed_errors)

    @classmethod
    def _sanitize_config(cls, value: Any) -> Any:
        if isinstance(value, dict):
            sanitized: dict[str, Any] = {}
            for key, item in value.items():
                if cls._is_sensitive_config_key(str(key)):
                    continue
                sanitized[key] = cls._sanitize_config(item)
            return sanitized
        if isinstance(value, list):
            return [cls._sanitize_config(item) for item in value]
        return value

    @staticmethod
    def _is_sensitive_config_key(key: str) -> bool:
        normalized = key.lower().replace("-", "_")
        sensitive_terms = (
            "api_key",
            "apikey",
            "authorization",
            "access_token",
            "refresh_token",
            "token",
            "bearer",
            "auth",
            "secret",
            "password",
            "credential",
            "headers",
            "cookie",
        )
        return any(term in normalized for term in sensitive_terms)
