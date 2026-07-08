"""Slide deck outline and prompt-plan generation through the shared LLM runtime."""

from __future__ import annotations

import json
from typing import Any

from ...domain.slide_deck import SlideDeckOutline, SlidePromptPlanSet


class SlideDeckPlanningService:
    def __init__(self, llm_provider: Any) -> None:
        self.llm = llm_provider

    async def generate_outline(
        self,
        source_context: str,
        config: dict[str, Any],
        instruction: str = "",
    ) -> SlideDeckOutline:
        page_count = self._page_count(config)
        prompt_config = self._prompt_config(config)
        prompt = (
            "Generate a source-grounded slide deck outline.\n\n"
            f"Required page count: {page_count}\n"
            f"Config: {json.dumps(prompt_config, ensure_ascii=False)}\n"
            f"Instruction: {instruction or 'Use the source material faithfully.'}\n\n"
            f"Sources:\n{source_context}"
        )
        last_error = ""
        current_prompt = prompt
        for attempt in range(2):
            outline = await self.llm.generate_structured(
                current_prompt,
                SlideDeckOutline,
                system_prompt="You create concise, source-grounded slide deck outlines.",
                temperature=0.2,
            )
            pages = [slide.page for slide in outline.slides]
            expected = list(range(1, page_count + 1))
            if pages == expected:
                return outline
            last_error = f"outline page sequence must be {expected}, got {pages}"
            current_prompt = (
                f"{prompt}\n\n"
                "Fix the deck outline so it validates against the required page sequence. "
                f"Validation error: {last_error}"
            )
        raise ValueError(last_error)

    async def generate_prompt_plan(
        self,
        source_context: str,
        outline: SlideDeckOutline,
        config: dict[str, Any],
        instruction: str = "",
    ) -> SlidePromptPlanSet:
        page_count = self._page_count(config)
        prompt_config = self._prompt_config(config)
        prompt = (
            "Generate per-slide display content and image prompts from the confirmed outline.\n\n"
            f"Required page count: {page_count}\n"
            f"Config: {json.dumps(prompt_config, ensure_ascii=False)}\n"
            f"Instruction: {instruction or 'Use the confirmed outline faithfully.'}\n\n"
            f"Confirmed outline:\n{outline.model_dump_json()}\n\n"
            f"Sources:\n{source_context}"
        )
        last_error = ""
        current_prompt = prompt
        for attempt in range(2):
            plan = await self.llm.generate_structured(
                current_prompt,
                SlidePromptPlanSet,
                system_prompt="You create precise slide image prompt plans from confirmed outlines.",
                temperature=0.2,
            )
            pages = [slide.page for slide in plan.slide_prompts]
            expected = list(range(1, page_count + 1))
            if pages == expected:
                return plan
            last_error = f"prompt plan page sequence must be {expected}, got {pages}"
            current_prompt = (
                f"{prompt}\n\n"
                "Fix the slide prompt plan so it validates against the required page sequence. "
                f"Validation error: {last_error}"
            )
        raise ValueError(last_error)

    @staticmethod
    def _page_count(config: dict[str, Any]) -> int:
        page_count = int(config.get("page_count") or config.get("num_pages") or 0)
        if page_count < 1:
            raise ValueError("page_count must be at least 1")
        return page_count

    @staticmethod
    def _prompt_config(config: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in config.items() if key != "source_context"}
