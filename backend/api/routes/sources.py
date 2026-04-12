"""Knowledge-base source routes."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from ...config import Settings, get_settings
from ...core.services.source_service import SourceService
from ...dependencies import get_source_service
from ...domain.source import KnowledgeSource
from ..schemas.source import (
    SourceCreateTextRequest,
    SourceDeleteResponse,
    SourceDetail,
    SourceInfo,
    SourceListResponse,
)

router = APIRouter(prefix="/sources", tags=["Sources"])


def _info(source: KnowledgeSource) -> SourceInfo:
    return SourceInfo(
        id=source.id,
        kind=source.kind.value,
        title=source.title,
        filename=source.filename,
        mime_type=source.mime_type,
        status=source.status.value,
        error=source.error,
        chunk_count=source.chunk_count,
        char_count=source.char_count,
        metadata=source.metadata,
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


def _detail(source: KnowledgeSource) -> SourceDetail:
    return SourceDetail(**_info(source).model_dump(), text=source.text)


@router.post("/text", response_model=SourceDetail)
async def create_text_source(
    request: SourceCreateTextRequest,
    service: SourceService = Depends(get_source_service),
):
    source = await service.create_text_source(
        title=request.title,
        text=request.text,
        metadata=request.metadata,
    )
    return _detail(source)


@router.post("/upload", response_model=SourceDetail)
async def upload_source(
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
    service: SourceService = Depends(get_source_service),
):
    filename = file.filename or "upload"
    os.makedirs(settings.upload_dir, exist_ok=True)
    file_path = Path(settings.upload_dir) / f"{uuid4().hex}_{filename}"

    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        source = await service.create_file_source(
            file_path=file_path,
            filename=filename,
            mime_type=file.content_type,
        )
        return _detail(source)
    except Exception as exc:
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("", response_model=SourceListResponse)
@router.get("/", response_model=SourceListResponse)
async def list_sources(service: SourceService = Depends(get_source_service)):
    sources = await service.list_sources()
    return SourceListResponse(sources=[_info(source) for source in sources], total=len(sources))


@router.get("/{source_id}", response_model=SourceDetail)
async def get_source(source_id: str, service: SourceService = Depends(get_source_service)):
    source = await service.get_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return _detail(source)


@router.delete("/{source_id}", response_model=SourceDeleteResponse)
async def delete_source(source_id: str, service: SourceService = Depends(get_source_service)):
    source = await service.get_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    success = await service.delete_source(source_id)
    return SourceDeleteResponse(success=success, message="deleted" if success else "delete failed")
