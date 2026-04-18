"""Notebook note management and conversion into knowledge sources."""

from __future__ import annotations

from typing import Any

from ...core.interfaces.knowledge_repository import KnowledgeRepositoryInterface
from ...domain.source import Note
from .source_service import SourceService


class NoteService:
    def __init__(self, repository: KnowledgeRepositoryInterface, source_service: SourceService) -> None:
        self.repository = repository
        self.source_service = source_service

    async def create_note(
        self,
        title: str,
        body: str,
        source_ids: list[str] | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Note:
        note = Note(
            title=title.strip() or "Untitled note",
            body=body.strip(),
            source_ids=source_ids or [],
            tags=tags or [],
            metadata=metadata or {},
        )
        return await self.repository.save_note(note)

    async def update_note(
        self,
        note_id: str,
        title: str | None = None,
        body: str | None = None,
        source_ids: list[str] | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Note | None:
        note = await self.repository.get_note(note_id)
        if not note:
            return None
        if title is not None:
            note.title = title.strip() or note.title
        if body is not None:
            note.body = body.strip()
        if source_ids is not None:
            note.source_ids = source_ids
        if tags is not None:
            note.tags = tags
        if metadata is not None:
            note.metadata = {**note.metadata, **metadata}
        return await self.repository.save_note(note)

    async def list_notes(self, query: str | None = None) -> list[Note]:
        return await self.repository.list_notes(query=query)

    async def get_note(self, note_id: str) -> Note | None:
        return await self.repository.get_note(note_id)

    async def delete_note(self, note_id: str) -> bool:
        return await self.repository.delete_note(note_id)

    async def convert_note_to_source(self, note_id: str):
        note = await self.repository.get_note(note_id)
        if not note:
            return None
        text = f"# {note.title}\n\n{note.body}".strip()
        return await self.source_service.create_text_source(
            title=note.title,
            text=text,
            metadata={
                "origin": "note",
                "note_id": note.id,
                "source_ids": note.source_ids,
                "tags": note.tags,
            },
        )
