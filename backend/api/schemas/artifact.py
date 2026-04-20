"""Studio artifact API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ArtifactGenerateRequest(BaseModel):
    artifact_type: str
    source_ids: list[str] = Field(default_factory=list)
    instruction: str = ""


class ArtifactResponse(BaseModel):
    id: str
    artifact_type: str
    title: str
    source_ids: list[str]
    payload: dict[str, Any]
    markdown: str
    file_refs: list[dict[str, Any]] = Field(default_factory=list)
    status: str
    created_at: datetime
    updated_at: datetime


class ArtifactListResponse(BaseModel):
    artifacts: list[ArtifactResponse]
    total: int


class ResearchJobRequest(BaseModel):
    query: str
    source_ids: list[str] = Field(default_factory=list)
