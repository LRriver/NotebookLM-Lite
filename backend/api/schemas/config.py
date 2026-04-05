"""Runtime configuration schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PublicModelProfile(BaseModel):
    model: str = ""
    base_url: str = ""
    adapter: str = ""
    thinking: dict[str, Any] | None = None
    voice: str | None = None
    response_format: str = "mp3"
    stream: bool = True
    api_key_set: bool = False


class RuntimeModelProfile(BaseModel):
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    adapter: str | None = None
    thinking: dict[str, Any] | None = None
    voice: str | None = None
    response_format: str | None = None
    stream: bool | None = None


class RuntimeConfigResponse(BaseModel):
    models: dict[str, PublicModelProfile]
    chunking: dict[str, Any]
    storage: dict[str, Any]
    message: str = ""


class RuntimeConfigUpdate(BaseModel):
    models: dict[str, RuntimeModelProfile] = Field(default_factory=dict)
