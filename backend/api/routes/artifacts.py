"""Studio artifact routes."""

from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Response

from ...core.services.artifact_service import ArtifactService
from ...dependencies import get_knowledge_repository, get_llm_provider
from ...domain.source import Artifact
from ..schemas.artifact import (
    ArtifactGenerateRequest,
    ArtifactListResponse,
    ArtifactResponse,
    ResearchJobRequest,
)

router = APIRouter(tags=["Studio Artifacts"])


def get_artifact_llm_factory() -> Callable:
    return get_llm_provider


def _response(artifact: Artifact) -> ArtifactResponse:
    return ArtifactResponse(
        id=artifact.id,
        artifact_type=artifact.artifact_type.value,
        title=artifact.title,
        source_ids=artifact.source_ids,
        payload=artifact.payload,
        markdown=artifact.markdown,
        file_refs=artifact.file_refs,
        status=artifact.status.value,
        created_at=artifact.created_at,
        updated_at=artifact.updated_at,
    )


@router.post("/artifacts/generate", response_model=ArtifactResponse)
async def generate_artifact(
    request: ArtifactGenerateRequest,
    repository=Depends(get_knowledge_repository),
    llm_factory: Callable = Depends(get_artifact_llm_factory),
):
    try:
        llm = llm_factory(provider="litellm", api_key="", base_url=None, model=None)
        service = ArtifactService(repository=repository, llm_provider=llm)
        artifact = await service.generate_artifact(
            artifact_type=request.artifact_type,
            source_ids=request.source_ids,
            instruction=request.instruction,
        )
        return _response(artifact)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/artifacts", response_model=ArtifactListResponse)
async def list_artifacts(repository=Depends(get_knowledge_repository)):
    artifacts = await repository.list_artifacts()
    return ArtifactListResponse(artifacts=[_response(item) for item in artifacts], total=len(artifacts))


@router.get("/artifacts/{artifact_id}", response_model=ArtifactResponse)
async def get_artifact(artifact_id: str, repository=Depends(get_knowledge_repository)):
    artifact = await repository.get_artifact(artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return _response(artifact)


@router.get("/artifacts/{artifact_id}/download")
async def download_artifact(artifact_id: str, format: str = "markdown", repository=Depends(get_knowledge_repository)):
    artifact = await repository.get_artifact(artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    if format == "json":
        return Response(
            content=ArtifactService.artifact_as_json(artifact),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{artifact.id}.json"'},
        )
    if format == "svg":
        svg = artifact.payload.get("svg")
        if artifact.artifact_type.value != "infographic" or not svg:
            raise HTTPException(status_code=400, detail="SVG download is only available for infographic artifacts")
        return Response(
            content=svg,
            media_type="image/svg+xml",
            headers={"Content-Disposition": f'attachment; filename="{artifact.id}.svg"'},
        )
    return Response(
        content=artifact.markdown,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{artifact.id}.md"'},
    )


@router.post("/research/jobs")
async def create_research_job(
    request: ResearchJobRequest,
    repository=Depends(get_knowledge_repository),
    llm_factory: Callable = Depends(get_artifact_llm_factory),
):
    service = ArtifactService(repository=repository, llm_provider=llm_factory(provider="litellm", api_key="", base_url=None, model=None))
    job = await service.create_research_placeholder(query=request.query, source_ids=request.source_ids)
    return {"id": job.id, "status": job.status.value, "job_type": job.job_type, "request": job.request}
