"""Slide deck API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from ...domain.slide_deck import SlideDeckOutline, SlidePromptPlanSet, SlideRecord


class SlideDeckCreateRequest(BaseModel):
    title: str
    source_ids: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)


class SlideDeckOutlinePatchRequest(BaseModel):
    outline: SlideDeckOutline
    confirmed: bool = False


class SlideDeckPromptPlanPatchRequest(BaseModel):
    prompt_plan: SlidePromptPlanSet
    confirmed: bool = False


class SlideEditRequest(BaseModel):
    instruction: str


class SlideDeckResponse(BaseModel):
    id: str
    title: str
    source_ids: list[str]
    source_snapshot: list[dict[str, Any]]
    config_snapshot: dict[str, Any]
    outline: dict[str, Any] | None = None
    prompt_plan: dict[str, Any] | None = None
    slides: list[dict[str, Any]]
    status: str
    stage: str
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class SlideDeckListResponse(BaseModel):
    decks: list[SlideDeckResponse]
    total: int


class SlideDeckJobResponse(BaseModel):
    id: str
    deck_id: str
    stage: str
    status: str
    progress: float
    result_ref: str | None = None
    error: str | None = None


class SlideDeckJobListResponse(BaseModel):
    jobs: list[SlideDeckJobResponse]
    total: int
