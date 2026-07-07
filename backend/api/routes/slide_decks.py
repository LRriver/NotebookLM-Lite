"""Native slide deck workflow routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...config import get_settings
from ...core.services.slide_deck_planning_service import SlideDeckPlanningService
from ...core.services.slide_deck_service import SlideDeckService
from ...dependencies import get_knowledge_repository, get_llm_provider
from ...domain.slide_deck import SlideDeckJob, SlideDeckProject
from ...infrastructure.image_providers.raw_multimodal_provider import RawMultimodalImageProvider
from ...infrastructure.slide_deck_files import SlideDeckFileStore
from ..schemas.slide_deck import (
    SlideDeckCreateRequest,
    SlideDeckJobListResponse,
    SlideDeckJobResponse,
    SlideDeckListResponse,
    SlideDeckOutlinePatchRequest,
    SlideDeckPromptPlanPatchRequest,
    SlideDeckResponse,
    SlideEditRequest,
)

router = APIRouter(tags=["Slide Decks"])


def get_slide_deck_service(
    repository=Depends(get_knowledge_repository),
) -> SlideDeckService:
    settings = get_settings()
    llm = get_llm_provider(provider="litellm", api_key="", base_url=None, model=None)
    return SlideDeckService(
        repository=repository,
        planning_service=SlideDeckPlanningService(llm),
        image_provider=RawMultimodalImageProvider(settings.api.models.image_model),
        edit_provider=RawMultimodalImageProvider(settings.api.models.edit_model),
        file_store=SlideDeckFileStore(settings.output_dir),
    )


def _deck_response(deck: SlideDeckProject) -> SlideDeckResponse:
    return SlideDeckResponse(
        id=deck.id,
        title=deck.title,
        source_ids=deck.source_ids,
        source_snapshot=deck.source_snapshot,
        config_snapshot={k: v for k, v in deck.config_snapshot.items() if k != "source_context"},
        outline=deck.outline.model_dump() if deck.outline else None,
        prompt_plan=deck.prompt_plan.model_dump() if deck.prompt_plan else None,
        slides=[slide.model_dump(mode="json") for slide in deck.slides],
        status=deck.status.value,
        stage=deck.stage.value,
        error=deck.error,
        created_at=deck.created_at,
        updated_at=deck.updated_at,
    )


def _job_response(job: SlideDeckJob) -> SlideDeckJobResponse:
    return SlideDeckJobResponse(
        id=job.id,
        deck_id=job.deck_id,
        stage=job.stage.value,
        status=job.status.value,
        progress=job.progress,
        result_ref=job.result_ref,
        error=job.error,
    )


@router.post("/slide-decks", response_model=SlideDeckResponse)
async def create_slide_deck(
    request: SlideDeckCreateRequest,
    service: SlideDeckService = Depends(get_slide_deck_service),
):
    try:
        return _deck_response(await service.create_deck(request.title, request.source_ids, request.config))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/slide-decks", response_model=SlideDeckListResponse)
async def list_slide_decks(service: SlideDeckService = Depends(get_slide_deck_service)):
    decks = await service.list_decks()
    return SlideDeckListResponse(decks=[_deck_response(deck) for deck in decks], total=len(decks))


@router.get("/slide-decks/{deck_id}", response_model=SlideDeckResponse)
async def get_slide_deck(deck_id: str, service: SlideDeckService = Depends(get_slide_deck_service)):
    deck = await service.get_deck(deck_id)
    if not deck:
        raise HTTPException(status_code=404, detail="slide deck not found")
    return _deck_response(deck)


@router.get("/slide-decks/jobs/{job_id}", response_model=SlideDeckJobResponse)
async def get_slide_deck_job(job_id: str, service: SlideDeckService = Depends(get_slide_deck_service)):
    job = await service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="slide deck job not found")
    return _job_response(job)


@router.get("/slide-decks/{deck_id}/jobs", response_model=SlideDeckJobListResponse)
async def list_slide_deck_jobs(deck_id: str, service: SlideDeckService = Depends(get_slide_deck_service)):
    try:
        jobs = await service.list_jobs(deck_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SlideDeckJobListResponse(jobs=[_job_response(job) for job in jobs], total=len(jobs))


@router.post("/slide-decks/{deck_id}/outline/jobs", response_model=SlideDeckJobResponse)
async def generate_outline(deck_id: str, service: SlideDeckService = Depends(get_slide_deck_service)):
    try:
        return _job_response(await service.generate_outline(deck_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/slide-decks/{deck_id}/outline", response_model=SlideDeckResponse)
async def patch_outline(
    deck_id: str,
    request: SlideDeckOutlinePatchRequest,
    service: SlideDeckService = Depends(get_slide_deck_service),
):
    try:
        return _deck_response(await service.confirm_outline(deck_id, request.outline, request.confirmed))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/slide-decks/{deck_id}/prompt-plan/jobs", response_model=SlideDeckJobResponse)
async def generate_prompt_plan(deck_id: str, service: SlideDeckService = Depends(get_slide_deck_service)):
    try:
        return _job_response(await service.generate_prompt_plan(deck_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/slide-decks/{deck_id}/prompt-plan", response_model=SlideDeckResponse)
async def patch_prompt_plan(
    deck_id: str,
    request: SlideDeckPromptPlanPatchRequest,
    service: SlideDeckService = Depends(get_slide_deck_service),
):
    try:
        return _deck_response(await service.confirm_prompt_plan(deck_id, request.prompt_plan, request.confirmed))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/slide-decks/{deck_id}/generate/jobs", response_model=SlideDeckJobResponse)
async def generate_slides(deck_id: str, service: SlideDeckService = Depends(get_slide_deck_service)):
    try:
        return _job_response(await service.generate_slides(deck_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/slide-decks/{deck_id}/slides/{slide_id}/regenerate", response_model=SlideDeckResponse)
async def regenerate_slide(
    deck_id: str,
    slide_id: str,
    service: SlideDeckService = Depends(get_slide_deck_service),
):
    try:
        return _deck_response(await service.regenerate_slide(deck_id, slide_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/slide-decks/{deck_id}/slides/{slide_id}/edit", response_model=SlideDeckResponse)
async def edit_slide(
    deck_id: str,
    slide_id: str,
    request: SlideEditRequest,
    service: SlideDeckService = Depends(get_slide_deck_service),
):
    try:
        return _deck_response(await service.edit_slide(deck_id, slide_id, request.instruction))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
