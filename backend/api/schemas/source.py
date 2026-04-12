"""API schemas for knowledge-base sources."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class SourceCreateTextRequest(BaseModel):
    title: str = Field(default="Pasted text")
    text: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceInfo(BaseModel):
    id: str
    kind: str
    title: str
    filename: Optional[str] = None
    mime_type: Optional[str] = None
    status: str
    error: Optional[str] = None
    chunk_count: int
    char_count: int
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class SourceDetail(SourceInfo):
    text: str = ""


class SourceListResponse(BaseModel):
    sources: list[SourceInfo]
    total: int


class SourceDeleteResponse(BaseModel):
    success: bool
    message: str
