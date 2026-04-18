"""Note API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NoteCreateRequest(BaseModel):
    title: str
    body: str
    source_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class NoteUpdateRequest(BaseModel):
    title: str | None = None
    body: str | None = None
    source_ids: list[str] | None = None
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None


class NoteResponse(BaseModel):
    id: str
    title: str
    body: str
    source_ids: list[str]
    tags: list[str]
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class NoteListResponse(BaseModel):
    notes: list[NoteResponse]
    total: int
