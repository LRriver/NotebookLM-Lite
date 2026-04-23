"""Boundary for future OpenNotebookLM-AIPPT integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AIPPTSourceBundle:
    title: str
    source_text: str
    source_ids: list[str] = field(default_factory=list)
    requirements: str = ""


@dataclass(frozen=True)
class AIPPTIntegrationPlan:
    adapter_status: str
    aippt_project_path: str
    expected_modules: list[str]
    entrypoints: list[str]
    request_shape: dict[str, Any]


class AIPPTAdapter:
    """Adapter contract for merging OpenNotebookLM-AIPPT without coupling imports yet."""

    def __init__(self, aippt_project_path: str = "/Users/lzj/proj/notebook/OpenNotebookLM-AIPPT") -> None:
        self.aippt_project_path = Path(aippt_project_path)

    def integration_plan(self, bundle: AIPPTSourceBundle) -> AIPPTIntegrationPlan:
        return AIPPTIntegrationPlan(
            adapter_status="coming_soon",
            aippt_project_path=str(self.aippt_project_path),
            expected_modules=[
                "src.generator.PPTGenerator",
                "src.models",
                "src.prompts.templates",
                "src.exporter",
            ],
            entrypoints=[
                "generate outline from source_text",
                "generate slide prompts and images",
                "export pptx/pdf assets",
            ],
            request_shape={
                "title": bundle.title,
                "source_ids": bundle.source_ids,
                "source_text": bundle.source_text,
                "requirements": bundle.requirements,
            },
        )

    async def outline_placeholder(self, title: str, bullets: list[str]) -> dict:
        return {
            "title": title,
            "slides": [{"title": bullet, "bullets": []} for bullet in bullets],
            "adapter_status": "placeholder",
        }
