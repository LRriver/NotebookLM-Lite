"""Notebook notes routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...core.services.note_service import NoteService
from ...dependencies import get_knowledge_repository, get_source_service
from ...domain.source import KnowledgeSource, Note
from ..schemas.note import NoteCreateRequest, NoteListResponse, NoteResponse, NoteUpdateRequest

router = APIRouter(prefix="/notes", tags=["Notes"])


def _note_response(note: Note) -> NoteResponse:
    return NoteResponse(
        id=note.id,
        title=note.title,
        body=note.body,
        source_ids=note.source_ids,
        tags=note.tags,
        metadata=note.metadata,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


def _source_response(source: KnowledgeSource) -> dict:
    return {
        "id": source.id,
        "kind": source.kind.value,
        "title": source.title,
        "filename": source.filename,
        "status": source.status.value,
        "error": source.error,
        "metadata": source.metadata,
        "chunk_count": source.chunk_count,
        "char_count": source.char_count,
        "created_at": source.created_at,
        "updated_at": source.updated_at,
    }


def get_note_service(
    repository=Depends(get_knowledge_repository),
    source_service=Depends(get_source_service),
) -> NoteService:
    return NoteService(repository=repository, source_service=source_service)


@router.post("", response_model=NoteResponse)
async def create_note(request: NoteCreateRequest, service: NoteService = Depends(get_note_service)):
    if not request.body.strip():
        raise HTTPException(status_code=400, detail="body is required")
    note = await service.create_note(
        title=request.title,
        body=request.body,
        source_ids=request.source_ids,
        tags=request.tags,
        metadata=request.metadata,
    )
    return _note_response(note)


@router.get("", response_model=NoteListResponse)
async def list_notes(query: str | None = None, service: NoteService = Depends(get_note_service)):
    notes = await service.list_notes(query=query)
    return NoteListResponse(notes=[_note_response(note) for note in notes], total=len(notes))


@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(note_id: str, service: NoteService = Depends(get_note_service)):
    note = await service.get_note(note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return _note_response(note)


@router.patch("/{note_id}", response_model=NoteResponse)
async def update_note(note_id: str, request: NoteUpdateRequest, service: NoteService = Depends(get_note_service)):
    note = await service.update_note(
        note_id=note_id,
        title=request.title,
        body=request.body,
        source_ids=request.source_ids,
        tags=request.tags,
        metadata=request.metadata,
    )
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return _note_response(note)


@router.post("/{note_id}/source")
async def convert_note_to_source(note_id: str, service: NoteService = Depends(get_note_service)):
    source = await service.convert_note_to_source(note_id)
    if not source:
        raise HTTPException(status_code=404, detail="Note not found")
    return _source_response(source)


@router.delete("/{note_id}")
async def delete_note(note_id: str, service: NoteService = Depends(get_note_service)):
    note = await service.get_note(note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"success": await service.delete_note(note_id)}
