"""Slide deck domain models for native Studio deck generation."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from .source import JobStatus
from .source import new_id, utc_now


class SlideDeckStatus(str, Enum):
    DRAFT = "draft"
    PLANNING = "planning"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


class SlideDeckStage(str, Enum):
    CREATED = "created"
    OUTLINE_READY = "outline_ready"
    OUTLINE_CONFIRMED = "outline_confirmed"
    PROMPT_PLAN_READY = "prompt_plan_ready"
    PROMPT_PLAN_CONFIRMED = "prompt_plan_confirmed"
    SLIDES_GENERATING = "slides_generating"
    SLIDES_READY = "slides_ready"
    EXPORTED = "exported"


class SlideStatus(str, Enum):
    PENDING = "pending"
    GENERATING = "generating"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class SlideAssetStage(str, Enum):
    GENERATED = "generated"
    EDITED = "edited"
    IMPORTED = "imported"


class SlideExportFormat(str, Enum):
    PPTX = "pptx"
    PDF = "pdf"


class SlideExportStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class SlideDeckJobStage(str, Enum):
    OUTLINE = "outline"
    PROMPT_PLAN = "prompt_plan"
    SLIDE_GENERATION = "slide_generation"
    SLIDE_REGENERATION = "slide_regeneration"
    SLIDE_EDIT = "slide_edit"
    EXPORT = "export"


class SlideDeckFileKind(str, Enum):
    SLIDE_IMAGE = "slide_image"
    EXPORT = "export"


class SlideOutline(BaseModel):
    page: int = Field(..., ge=1)
    title: str = Field(..., min_length=1)
    narrative_goal: str = Field(..., min_length=1)
    key_points: list[str] = Field(default_factory=list)
    visual_direction: str = Field(..., min_length=1)


class SlideDeckOutline(BaseModel):
    title: str = Field(..., min_length=1)
    user_requirements: str = ""
    design_style: str = Field(..., min_length=1)
    audience: str = Field(..., min_length=1)
    slides: list[SlideOutline] = Field(default_factory=list)


class SlidePromptPlan(BaseModel):
    page: int = Field(..., ge=1)
    title: str = Field(..., min_length=1)
    content_summary: str = Field(..., min_length=1)
    display_content: str = Field(..., min_length=1)
    prompt: str = Field(..., min_length=1)


class SlidePromptPlanSet(BaseModel):
    slide_prompts: list[SlidePromptPlan] = Field(default_factory=list)


class SlideEditHistory(BaseModel):
    id: str = Field(default_factory=lambda: new_id("sedit"))
    instruction: str
    previous_asset_id: Optional[str] = None
    next_asset_id: Optional[str] = None
    model_metadata: dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)


class SlideRecord(BaseModel):
    id: str = Field(default_factory=lambda: new_id("slide"))
    deck_id: str
    page_number: int = Field(..., ge=1)
    title: str
    prompt: str = ""
    display_content: str = ""
    content_summary: str = ""
    asset_id: Optional[str] = None
    status: SlideStatus = SlideStatus.PENDING
    error: Optional[str] = None
    edit_history: list[SlideEditHistory] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class SlideAsset(BaseModel):
    id: str = Field(default_factory=lambda: new_id("sasset"))
    deck_id: str
    slide_id: str
    file_path: str
    mime_type: str = "image/png"
    byte_size: int = 0
    checksum: str = ""
    download_ref: str = ""
    width: Optional[int] = None
    height: Optional[int] = None
    stage: SlideAssetStage = SlideAssetStage.GENERATED
    model_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class SlideDeckExport(BaseModel):
    id: str = Field(default_factory=lambda: new_id("sexport"))
    deck_id: str
    format: SlideExportFormat = SlideExportFormat.PPTX
    file_path: str
    filename: str
    byte_size: int = 0
    checksum: str = ""
    download_ref: str = ""
    slide_count: int = 0
    status: SlideExportStatus = SlideExportStatus.PENDING
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class SlideDeckJob(BaseModel):
    id: str = Field(default_factory=lambda: new_id("sdjob"))
    deck_id: str
    stage: SlideDeckJobStage
    status: JobStatus = JobStatus.PENDING
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    retry_count: int = Field(default=0, ge=0)
    request: dict[str, Any] = Field(default_factory=dict)
    result_ref: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class SlideDeckProject(BaseModel):
    id: str = Field(default_factory=lambda: new_id("deck"))
    title: str
    source_ids: list[str] = Field(default_factory=list)
    source_snapshot: list[dict[str, Any]] = Field(default_factory=list)
    config_snapshot: dict[str, Any] = Field(default_factory=dict)
    outline: SlideDeckOutline | None = None
    prompt_plan: SlidePromptPlanSet | None = None
    slides: list[SlideRecord] = Field(default_factory=list)
    status: SlideDeckStatus = SlideDeckStatus.DRAFT
    stage: SlideDeckStage = SlideDeckStage.CREATED
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
