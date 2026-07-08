"""Native slide deck workflow service."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import struct
from typing import Any
from urllib.parse import urlparse

from ...domain.slide_deck import (
    SlideAsset,
    SlideAssetStage,
    SlideDeckExport,
    SlideDeckFileKind,
    SlideDeckJob,
    SlideDeckJobStage,
    SlideDeckOutline,
    SlideDeckProject,
    SlideDeckStage,
    SlideDeckStatus,
    SlideEditHistory,
    SlideExportFormat,
    SlideExportStatus,
    SlidePromptPlanSet,
    SlideRecord,
    SlideStatus,
)
from ...domain.source import Artifact, ArtifactType, JobStatus, new_id, utc_now
from ...infrastructure.slide_deck_files import SlideDeckFileStore
from ..interfaces.knowledge_repository import KnowledgeRepositoryInterface
from .slide_deck_export_service import SlideDeckPPTXExporter

logger = logging.getLogger(__name__)


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
        self.pptx_exporter = SlideDeckPPTXExporter()
        self._background_tasks: dict[str, asyncio.Task] = {}

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
                    "mime_type": source.mime_type,
                    "char_count": len(source.text),
                    "content_sha256": hashlib.sha256(source.text.encode("utf-8")).hexdigest(),
                    "created_at": source.created_at,
                    "updated_at": source.updated_at,
                    "excerpt": source.text[:800],
                }
            )
            context_parts.append(f"## {source.title}\n\n{source.text[:6000]}")
        safe_config = self._sanitize_config(config)
        model_lineage = {
            "text_model": self._provider_model_metadata(getattr(self.planning, "llm", None), "text_model"),
            "image_model": self._provider_model_metadata(self.image_provider, "image_model"),
            "edit_model": self._provider_model_metadata(self.edit_provider, "edit_model"),
        }
        source_context = "\n\n---\n\n".join(context_parts)
        deck = SlideDeckProject(
            title=title,
            source_ids=source_ids,
            source_snapshot=snapshot,
            config_snapshot={
                **safe_config,
                "source_context": source_context,
                "source_context_sha256": hashlib.sha256(source_context.encode("utf-8")).hexdigest(),
                "model_lineage": model_lineage,
            },
        )
        await self.repository.save_slide_deck(deck)
        await self._upsert_deck_artifact(deck)
        return deck

    async def list_decks(self) -> list[SlideDeckProject]:
        decks = await self.repository.list_slide_decks()
        return [await self._reconcile_interrupted_slide_generation(deck) for deck in decks]

    async def get_deck(self, deck_id: str) -> SlideDeckProject | None:
        deck = await self.repository.get_slide_deck(deck_id)
        if not deck:
            return None
        return await self._reconcile_interrupted_slide_generation(deck)

    async def get_job(self, job_id: str) -> SlideDeckJob | None:
        job = await self.repository.get_slide_deck_job(job_id)
        if not job:
            return None
        deck = await self.repository.get_slide_deck(job.deck_id)
        if deck:
            await self._reconcile_interrupted_slide_generation(deck)
            job = await self.repository.get_slide_deck_job(job_id)
        return job

    async def list_jobs(self, deck_id: str) -> list[SlideDeckJob]:
        deck = await self._require_deck(deck_id)
        await self._reconcile_interrupted_slide_generation(deck)
        return await self.repository.list_slide_deck_jobs(deck_id)

    async def generate_outline(self, deck_id: str) -> SlideDeckJob:
        deck = await self._require_deck(deck_id)
        if deck.stage not in {
            SlideDeckStage.CREATED,
            SlideDeckStage.OUTLINE_READY,
            SlideDeckStage.OUTLINE_CONFIRMED,
        }:
            raise ValueError("outline can only be generated before prompt planning starts")
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
        if deck.stage not in {
            SlideDeckStage.CREATED,
            SlideDeckStage.OUTLINE_READY,
            SlideDeckStage.OUTLINE_CONFIRMED,
        }:
            raise ValueError("outline cannot be changed after prompt planning starts")
        if confirmed:
            self._validate_page_sequence([slide.page for slide in outline.slides], deck.config_snapshot)
        deck.outline = outline
        if confirmed and deck.stage in {
            SlideDeckStage.CREATED,
            SlideDeckStage.OUTLINE_READY,
            SlideDeckStage.OUTLINE_CONFIRMED,
        }:
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
        if deck.stage not in {
            SlideDeckStage.OUTLINE_CONFIRMED,
            SlideDeckStage.PROMPT_PLAN_READY,
            SlideDeckStage.PROMPT_PLAN_CONFIRMED,
        }:
            raise ValueError("prompt plan cannot be changed after slide generation starts")
        if confirmed:
            self._validate_page_sequence([slide.page for slide in prompt_plan.slide_prompts], deck.config_snapshot)
        deck.prompt_plan = prompt_plan
        if confirmed and deck.stage in {
            SlideDeckStage.OUTLINE_CONFIRMED,
            SlideDeckStage.PROMPT_PLAN_READY,
            SlideDeckStage.PROMPT_PLAN_CONFIRMED,
        }:
            deck.stage = SlideDeckStage.PROMPT_PLAN_CONFIRMED
        deck.updated_at = utc_now()
        return await self.repository.save_slide_deck(deck)

    async def generate_slides(self, deck_id: str) -> SlideDeckJob:
        deck = await self._require_deck(deck_id)
        self._validate_slide_generation_ready(deck)
        job = SlideDeckJob(
            deck_id=deck.id,
            stage=SlideDeckJobStage.SLIDE_GENERATION,
            status=JobStatus.RUNNING,
            started_at=utc_now(),
        )
        await self.repository.save_slide_deck_job(job)
        return await self._run_slide_generation_job(deck.id, job.id)

    async def queue_generate_slides(self, deck_id: str) -> SlideDeckJob:
        deck = await self._require_deck(deck_id)
        self._validate_slide_generation_ready(deck)
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
        self._track_background_task(job.id, self._run_slide_generation_job(deck.id, job.id))
        return job

    def _track_background_task(self, job_id: str, coroutine) -> None:
        task = asyncio.create_task(coroutine)
        self._background_tasks[job_id] = task

        def cleanup(completed: asyncio.Task) -> None:
            self._background_tasks.pop(job_id, None)
            try:
                completed.result()
            except asyncio.CancelledError:
                logger.info("Slide generation background task was cancelled for job %s", job_id)
            except Exception as exc:
                logger.exception("Slide generation background task crashed for job %s: %s", job_id, exc)

        task.add_done_callback(cleanup)

    async def _reconcile_interrupted_slide_generation(self, deck: SlideDeckProject) -> SlideDeckProject:
        if deck.stage != SlideDeckStage.SLIDES_GENERATING or deck.status != SlideDeckStatus.GENERATING:
            return deck

        jobs = [
            job
            for job in await self.repository.list_slide_deck_jobs(deck.id)
            if job.stage == SlideDeckJobStage.SLIDE_GENERATION and job.status in {JobStatus.PENDING, JobStatus.RUNNING}
        ]
        if jobs and any(
            (task := self._background_tasks.get(job.id)) is not None and not task.done()
            for job in jobs
        ):
            return deck

        error = "Slide generation was interrupted before completion. Retry generation to continue."
        for job in jobs:
            job.status = JobStatus.FAILED
            job.error = error
            job.finished_at = utc_now()
            await self.repository.save_slide_deck_job(job)

        for slide in deck.slides:
            if slide.status in {SlideStatus.PENDING, SlideStatus.GENERATING}:
                slide.status = SlideStatus.FAILED
                slide.error = error
                slide.updated_at = utc_now()
        deck.status = SlideDeckStatus.FAILED
        deck.error = error
        deck.updated_at = utc_now()
        await self.repository.save_slide_deck(deck)
        await self._upsert_deck_artifact(deck)
        return deck

    def _validate_slide_generation_ready(self, deck: SlideDeckProject) -> None:
        can_start = deck.stage == SlideDeckStage.PROMPT_PLAN_CONFIRMED
        can_resume = deck.stage == SlideDeckStage.SLIDES_GENERATING and deck.status == SlideDeckStatus.FAILED
        if not deck.prompt_plan or not (can_start or can_resume):
            raise ValueError("confirmed prompt plan is required")
        self._validate_page_sequence([slide.page for slide in deck.prompt_plan.slide_prompts], deck.config_snapshot)

    @classmethod
    def _validate_page_sequence(cls, pages: list[int], config: dict[str, Any]) -> None:
        expected = list(range(1, cls._page_count(config) + 1))
        if pages != expected:
            raise ValueError(f"page sequence must be {expected}, got {pages}")

    @staticmethod
    def _page_count(config: dict[str, Any]) -> int:
        page_count = int(config.get("page_count") or config.get("num_pages") or 0)
        if page_count < 1:
            raise ValueError("page_count must be at least 1")
        return page_count

    async def _run_slide_generation_job(self, deck_id: str, job_id: str) -> SlideDeckJob:
        deck = await self._require_deck(deck_id)
        job = await self.repository.get_slide_deck_job(job_id)
        if not job:
            raise ValueError("slide deck job not found")
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
                asset = await self._store_image_asset(
                    deck.id,
                    slide.id,
                    image.base64_data,
                    SlideAssetStage.GENERATED,
                    image.mime_type,
                    self._provider_model_metadata(self.image_provider, "image_model"),
                )
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
        asset = await self._store_image_asset(
            deck.id,
            slide.id,
            image.base64_data,
            SlideAssetStage.GENERATED,
            image.mime_type,
            self._provider_model_metadata(self.image_provider, "image_model"),
        )
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
        if not previous_asset_id:
            raise ValueError("slide image is required before editing")
        asset = await self.repository.get_slide_asset(previous_asset_id)
        if not asset:
            raise ValueError("slide image is required before editing")
        with open(asset.file_path, "rb") as file:
            image_b64 = base64.b64encode(file.read()).decode()
        edited = await self.edit_provider.edit_image(
            image_b64,
            instruction,
            aspect_ratio=str(deck.config_snapshot.get("aspect_ratio", "16:9")),
            quality=str(deck.config_snapshot.get("quality", "2K")),
        )
        asset = await self._store_image_asset(
            deck.id,
            slide.id,
            edited.base64_data,
            SlideAssetStage.EDITED,
            edited.mime_type,
            self._provider_model_metadata(self.edit_provider, "edit_model"),
        )
        slide.edit_history.append(
            SlideEditHistory(
                instruction=instruction,
                previous_asset_id=previous_asset_id,
                next_asset_id=asset.id,
                model_metadata=self._provider_model_metadata(self.edit_provider, "edit_model"),
            )
        )
        slide.asset_id = asset.id
        slide.updated_at = utc_now()
        self._refresh_deck_generation_status(deck)
        deck.updated_at = utc_now()
        await self.repository.save_slide_deck(deck)
        await self._upsert_deck_artifact(deck)
        return deck

    async def export_pptx(self, deck_id: str) -> SlideDeckJob:
        deck = await self._require_deck(deck_id)
        job = SlideDeckJob(
            deck_id=deck.id,
            stage=SlideDeckJobStage.EXPORT,
            status=JobStatus.RUNNING,
            started_at=utc_now(),
        )
        await self.repository.save_slide_deck_job(job)
        export = SlideDeckExport(
            deck_id=deck.id,
            format=SlideExportFormat.PPTX,
            file_path="",
            filename=f"{deck.id}.pptx",
            status=SlideExportStatus.RUNNING,
        )
        await self.repository.save_slide_export(export)
        try:
            image_paths = await self._exportable_slide_image_paths(deck)
            pptx_content = self.pptx_exporter.export(
                image_paths,
                aspect_ratio=str(deck.config_snapshot.get("aspect_ratio", "16:9")),
            )
            filename = f"{deck.id}-{new_id('export')}.pptx"
            stored = self.file_store.save_file(
                deck_id=deck.id,
                kind=SlideDeckFileKind.EXPORT,
                filename=filename,
                content=pptx_content,
            )
            export.file_path = str(stored.path)
            export.filename = filename
            export.byte_size = stored.byte_size
            export.checksum = stored.checksum
            export.download_ref = stored.download_ref
            export.slide_count = len(image_paths)
            export.slide_asset_signature = await self._current_slide_asset_signature(deck)
            export.status = SlideExportStatus.SUCCEEDED
            export.model_metadata = deck.config_snapshot.get("model_lineage", {})
            export.error = None
            export.updated_at = utc_now()
            await self.repository.save_slide_export(export)
            deck.stage = SlideDeckStage.EXPORTED
            deck.updated_at = utc_now()
            await self.repository.save_slide_deck(deck)
            await self._upsert_deck_artifact(deck)
            job.status = JobStatus.SUCCEEDED
            job.progress = 1.0
            job.result_ref = export.id
        except Exception as exc:
            export.status = SlideExportStatus.FAILED
            export.error = str(exc)
            export.updated_at = utc_now()
            await self.repository.save_slide_export(export)
            job.status = JobStatus.FAILED
            job.error = str(exc)
        job.finished_at = utc_now()
        await self.repository.save_slide_deck_job(job)
        return job

    async def get_latest_export(self, deck_id: str, format: SlideExportFormat = SlideExportFormat.PPTX) -> SlideDeckExport | None:
        deck = await self._require_deck(deck_id)
        try:
            current_signature = await self._current_slide_asset_signature(deck)
        except ValueError:
            return None
        exports = await self.repository.list_slide_exports(deck_id)
        matching = [
            export
            for export in exports
            if (
                export.format == format
                and export.status == SlideExportStatus.SUCCEEDED
                and export.slide_asset_signature == current_signature
            )
        ]
        if not matching:
            return None
        return sorted(matching, key=lambda export: export.created_at, reverse=True)[0]

    async def get_slide_image_asset(self, deck_id: str, slide_id: str) -> SlideAsset:
        deck = await self._require_deck(deck_id)
        slide = self._slide(deck, slide_id)
        if not slide.asset_id:
            raise ValueError("slide image not found")
        asset = await self.repository.get_slide_asset(slide.asset_id)
        if not asset:
            raise ValueError("slide image not found")
        return asset

    async def _store_image_asset(
        self,
        deck_id: str,
        slide_id: str,
        image_base64: str,
        stage: SlideAssetStage,
        mime_type: str = "image/png",
        model_metadata: dict[str, Any] | None = None,
    ) -> SlideAsset:
        content = base64.b64decode(image_base64)
        width, height = self._image_dimensions(content)
        stored = self.file_store.save_file(
            deck_id=deck_id,
            kind=SlideDeckFileKind.SLIDE_IMAGE,
            filename=f"{slide_id}-{new_id('assetfile')}{self._image_extension(mime_type)}",
            content=content,
        )
        asset = SlideAsset(
            deck_id=deck_id,
            slide_id=slide_id,
            file_path=str(stored.path),
            mime_type=mime_type,
            byte_size=stored.byte_size,
            checksum=stored.checksum,
            download_ref=stored.download_ref,
            width=width,
            height=height,
            stage=stage,
            model_metadata=model_metadata or {},
        )
        return await self.repository.save_slide_asset(asset)

    @staticmethod
    def _provider_model_metadata(provider: Any, role: str) -> dict[str, Any]:
        profile = getattr(provider, "profile", None)
        if not profile:
            return {"role": role}
        host = ""
        if getattr(profile, "base_url", ""):
            host = urlparse(profile.base_url).netloc
        return {
            "role": role,
            "model": getattr(profile, "model", ""),
            "adapter": getattr(profile, "adapter", ""),
            "base_url_host": host,
            "api_key_set": bool(getattr(profile, "api_key", "")),
        }

    @staticmethod
    def _image_extension(mime_type: str) -> str:
        return {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/gif": ".gif",
            "image/webp": ".webp",
        }.get(mime_type, ".png")

    @staticmethod
    def _image_dimensions(content: bytes) -> tuple[int | None, int | None]:
        if content.startswith(b"\x89PNG\r\n\x1a\n") and len(content) >= 24:
            return struct.unpack(">II", content[16:24])
        if (content.startswith(b"GIF87a") or content.startswith(b"GIF89a")) and len(content) >= 10:
            return struct.unpack("<HH", content[6:10])
        if content.startswith(b"RIFF") and len(content) >= 30 and content[8:12] == b"WEBP":
            if content[12:16] == b"VP8X" and len(content) >= 30:
                width = int.from_bytes(content[24:27], "little") + 1
                height = int.from_bytes(content[27:30], "little") + 1
                return width, height
            return None, None
        if content.startswith(b"\xff\xd8\xff"):
            return SlideDeckService._jpeg_dimensions(content)
        return None, None

    @staticmethod
    def _jpeg_dimensions(content: bytes) -> tuple[int | None, int | None]:
        index = 2
        while index + 9 < len(content):
            if content[index] != 0xFF:
                index += 1
                continue
            marker = content[index + 1]
            index += 2
            if marker in {0xD8, 0xD9}:
                continue
            if index + 2 > len(content):
                break
            segment_length = int.from_bytes(content[index : index + 2], "big")
            if segment_length < 2 or index + segment_length > len(content):
                break
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                height = int.from_bytes(content[index + 3 : index + 5], "big")
                width = int.from_bytes(content[index + 5 : index + 7], "big")
                return width, height
            index += segment_length
        return None, None

    async def _exportable_slide_image_paths(self, deck: SlideDeckProject) -> list[str]:
        if deck.status != SlideDeckStatus.READY and deck.stage != SlideDeckStage.EXPORTED:
            raise ValueError("generated slide images are required before PPTX export")
        if not deck.slides:
            raise ValueError("generated slide images are required before PPTX export")
        image_paths: list[str] = []
        for slide in sorted(deck.slides, key=lambda item: item.page_number):
            if slide.status != SlideStatus.SUCCEEDED or not slide.asset_id:
                raise ValueError("generated slide images are required before PPTX export")
            asset = await self.repository.get_slide_asset(slide.asset_id)
            if not asset or not asset.file_path:
                raise ValueError("generated slide images are required before PPTX export")
            image_paths.append(asset.file_path)
        return image_paths

    async def _current_slide_asset_signature(self, deck: SlideDeckProject) -> str:
        if not deck.slides:
            raise ValueError("generated slide images are required before PPTX export")
        parts: list[dict[str, Any]] = []
        for slide in sorted(deck.slides, key=lambda item: item.page_number):
            if slide.status != SlideStatus.SUCCEEDED or not slide.asset_id:
                raise ValueError("generated slide images are required before PPTX export")
            asset = await self.repository.get_slide_asset(slide.asset_id)
            if not asset or not asset.file_path:
                raise ValueError("generated slide images are required before PPTX export")
            parts.append(
                {
                    "page_number": slide.page_number,
                    "slide_id": slide.id,
                    "asset_id": asset.id,
                    "checksum": asset.checksum,
                }
            )
        serialized = json.dumps(parts, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

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
