"""Knowledge-base source, chunk, artifact, and job domain models."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class SourceKind(str, Enum):
    FILE = "file"
    TEXT = "text"
    CHAT_ANSWER = "chat_answer"
    DEEP_RESEARCH = "deep_research"
    ARTIFACT = "artifact"


class SourceStatus(str, Enum):
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"
    DELETED = "deleted"


class ArtifactType(str, Enum):
    MIND_MAP = "mind_map"
    FAQ = "faq"
    FLASHCARDS = "flashcards"
    QUIZ = "quiz"
    REPORT = "report"
    STUDY_GUIDE = "study_guide"
    DATA_TABLE = "data_table"
    PODCAST_SCRIPT = "podcast_script"
    PPT_OUTLINE = "ppt_outline"
    SLIDE_DECK = "slide_deck"
    VIDEO_OVERVIEW = "video_overview"
    INFOGRAPHIC = "infographic"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class KnowledgeSource(BaseModel):
    id: str = Field(default_factory=lambda: new_id("src"))
    kind: SourceKind
    title: str
    filename: Optional[str] = None
    mime_type: Optional[str] = None
    file_path: Optional[str] = None
    text: str = ""
    status: SourceStatus = SourceStatus.PROCESSING
    error: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    chunk_count: int = 0
    char_count: int = 0
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class KnowledgeChunk(BaseModel):
    id: str
    source_id: str
    content: str
    chunk_index: int
    start_offset: Optional[int] = None
    end_offset: Optional[int] = None
    embedding: Optional[list[float]] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class Artifact(BaseModel):
    id: str = Field(default_factory=lambda: new_id("art"))
    artifact_type: ArtifactType
    title: str
    source_ids: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    markdown: str = ""
    file_refs: list[dict[str, Any]] = Field(default_factory=list)
    status: JobStatus = JobStatus.SUCCEEDED
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Note(BaseModel):
    id: str = Field(default_factory=lambda: new_id("note"))
    title: str
    body: str
    source_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Job(BaseModel):
    id: str = Field(default_factory=lambda: new_id("job"))
    job_type: str
    status: JobStatus = JobStatus.PENDING
    source_ids: list[str] = Field(default_factory=list)
    request: dict[str, Any] = Field(default_factory=dict)
    result_ref: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
