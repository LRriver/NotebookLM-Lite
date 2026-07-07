from __future__ import annotations

import base64

import pytest

from backend.config import ModelProfile
from backend.core.services.slide_deck_planning_service import SlideDeckPlanningService
from backend.domain.slide_deck import (
    SlideDeckOutline,
    SlideOutline,
    SlidePromptPlan,
    SlidePromptPlanSet,
)
from backend.infrastructure.image_providers.raw_multimodal_provider import (
    RawMultimodalImageProvider,
)


class FakeStructuredLLM:
    def __init__(self) -> None:
        self.calls = []
        self.responses = []

    def push(self, value):
        self.responses.append(value)

    async def generate_structured(self, prompt, response_model, system_prompt=None, temperature=0.7, **kwargs):
        self.calls.append(
            {
                "prompt": prompt,
                "response_model": response_model,
                "system_prompt": system_prompt,
                "temperature": temperature,
                "kwargs": kwargs,
            }
        )
        value = self.responses.pop(0)
        return response_model.model_validate(value)


class FakeImageHttpClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    async def post_json(self, url, headers, json_payload, timeout):
        self.calls.append((url, headers, json_payload, timeout))
        return self.payload


@pytest.mark.asyncio
async def test_slide_deck_planning_uses_litellm_structured_models():
    llm = FakeStructuredLLM()
    llm.push(
        {
            "title": "Security Deck",
            "design_style": "technical briefing",
            "audience": "engineers",
            "slides": [
                {
                    "page": 1,
                    "title": "TLS",
                    "narrative_goal": "Explain TLS",
                    "key_points": ["Encryption"],
                    "visual_direction": "Protocol diagram",
                }
            ],
        }
    )
    llm.push(
        {
            "slide_prompts": [
                {
                    "page": 1,
                    "title": "TLS",
                    "content_summary": "TLS protects HTTP.",
                    "display_content": "TLS protects HTTP.",
                    "prompt": "Create a protocol diagram slide.",
                }
            ]
        }
    )
    service = SlideDeckPlanningService(llm)

    outline = await service.generate_outline(
        source_context="TLS protects HTTP traffic.",
        config={"page_count": 1, "language": "English", "style": "technical"},
    )
    prompt_plan = await service.generate_prompt_plan(
        source_context="TLS protects HTTP traffic.",
        outline=outline,
        config={"page_count": 1},
    )

    assert isinstance(outline, SlideDeckOutline)
    assert isinstance(prompt_plan, SlidePromptPlanSet)
    assert llm.calls[0]["response_model"] is SlideDeckOutline
    assert llm.calls[1]["response_model"] is SlidePromptPlanSet
    assert "TLS protects HTTP traffic" in llm.calls[0]["prompt"]


@pytest.mark.asyncio
async def test_slide_deck_planning_rejects_prompt_plan_page_count_mismatch():
    llm = FakeStructuredLLM()
    outline = SlideDeckOutline(
        title="Deck",
        design_style="technical",
        audience="engineers",
        slides=[
            SlideOutline(
                page=1,
                title="One",
                narrative_goal="Goal",
                visual_direction="Visual",
            )
        ],
    )
    llm.push(
        {
            "slide_prompts": [
                {
                    "page": 2,
                    "title": "Wrong page",
                    "content_summary": "Summary",
                    "display_content": "Display",
                    "prompt": "Prompt",
                }
            ]
        }
    )
    llm.push(
        {
            "slide_prompts": [
                {
                    "page": 2,
                    "title": "Still wrong",
                    "content_summary": "Summary",
                    "display_content": "Display",
                    "prompt": "Prompt",
                }
            ]
        }
    )
    service = SlideDeckPlanningService(llm)

    with pytest.raises(ValueError, match="page sequence"):
        await service.generate_prompt_plan("context", outline, {"page_count": 1})


@pytest.mark.asyncio
async def test_slide_deck_planning_repairs_outline_page_sequence_once():
    llm = FakeStructuredLLM()
    llm.push(
        {
            "title": "Deck",
            "design_style": "technical",
            "audience": "engineers",
            "slides": [
                {
                    "page": 2,
                    "title": "Wrong page",
                    "narrative_goal": "Goal",
                    "visual_direction": "Visual",
                }
            ],
        }
    )
    llm.push(
        {
            "title": "Deck",
            "design_style": "technical",
            "audience": "engineers",
            "slides": [
                {
                    "page": 1,
                    "title": "Correct page",
                    "narrative_goal": "Goal",
                    "visual_direction": "Visual",
                }
            ],
        }
    )
    service = SlideDeckPlanningService(llm)

    outline = await service.generate_outline("context", {"page_count": 1})

    assert outline.slides[0].page == 1
    assert len(llm.calls) == 2
    assert "Fix the deck outline" in llm.calls[1]["prompt"]


@pytest.mark.asyncio
async def test_slide_deck_planning_repairs_prompt_plan_page_sequence_once():
    llm = FakeStructuredLLM()
    outline = SlideDeckOutline(
        title="Deck",
        design_style="technical",
        audience="engineers",
        slides=[
            SlideOutline(
                page=1,
                title="One",
                narrative_goal="Goal",
                visual_direction="Visual",
            )
        ],
    )
    llm.push(
        {
            "slide_prompts": [
                {
                    "page": 2,
                    "title": "Wrong page",
                    "content_summary": "Summary",
                    "display_content": "Display",
                    "prompt": "Prompt",
                }
            ]
        }
    )
    llm.push(
        {
            "slide_prompts": [
                {
                    "page": 1,
                    "title": "Correct page",
                    "content_summary": "Summary",
                    "display_content": "Display",
                    "prompt": "Prompt",
                }
            ]
        }
    )
    service = SlideDeckPlanningService(llm)

    plan = await service.generate_prompt_plan("context", outline, {"page_count": 1})

    assert plan.slide_prompts[0].page == 1
    assert len(llm.calls) == 2
    assert "Fix the slide prompt plan" in llm.calls[1]["prompt"]


@pytest.mark.asyncio
async def test_raw_multimodal_image_provider_builds_generation_payload():
    image_b64 = base64.b64encode(b"image-bytes").decode()
    http = FakeImageHttpClient({"choices": [{"message": {"content": image_b64}}]})
    provider = RawMultimodalImageProvider(
        ModelProfile(
            model="gpt-image-2",
            base_url="https://image.example/v1",
            api_key="image-key",
            adapter="raw_chat_multimodal",
        ),
        http_client=http,
    )

    result = await provider.generate_image("Create slide", aspect_ratio="16:9", quality="2K")

    assert result.base64_data == image_b64
    url, headers, payload, timeout = http.calls[0]
    assert url == "https://image.example/v1/chat/completions"
    assert headers["Authorization"] == "Bearer image-key"
    assert payload["model"] == "gpt-image-2"
    assert "Create slide" in payload["messages"][0]["content"]
    assert "16:9" in payload["messages"][0]["content"]
    assert timeout == 180


@pytest.mark.asyncio
async def test_raw_multimodal_image_provider_builds_edit_payload():
    edited_b64 = base64.b64encode(b"edited-image").decode()
    source_b64 = base64.b64encode(b"source-image").decode()
    http = FakeImageHttpClient({"choices": [{"message": {"content": edited_b64}}]})
    provider = RawMultimodalImageProvider(
        ModelProfile(
            model="gpt-image-2",
            base_url="https://image.example/v1",
            api_key="edit-key",
            adapter="raw_chat_multimodal",
        ),
        http_client=http,
    )

    result = await provider.edit_image(source_b64, "Make title shorter", aspect_ratio="4:3", quality="1K")

    assert result.base64_data == edited_b64
    content = http.calls[0][2]["messages"][0]["content"]
    assert content[0]["type"] == "text"
    assert "Make title shorter" in content[0]["text"]
    assert content[1]["image_url"]["url"] == f"data:image/png;base64,{source_b64}"


@pytest.mark.asyncio
async def test_raw_multimodal_image_provider_normalizes_markdown_url_response():
    http = FakeImageHttpClient({"choices": [{"message": {"content": "![slide](https://cdn.example/slide.png)"}}]})
    provider = RawMultimodalImageProvider(
        ModelProfile(
            model="gpt-image-2",
            base_url="https://image.example/v1",
            api_key="image-key",
            adapter="raw_chat_multimodal",
        ),
        http_client=http,
        image_fetcher=lambda url: b"url-image-bytes",
    )

    result = await provider.generate_image("Create slide")

    assert result.base64_data == base64.b64encode(b"url-image-bytes").decode()
    assert result.mime_type == "image/png"


@pytest.mark.asyncio
async def test_raw_multimodal_image_provider_rejects_url_without_safe_fetcher():
    http = FakeImageHttpClient({"choices": [{"message": {"content": "![slide](https://cdn.example/slide.png)"}}]})
    provider = RawMultimodalImageProvider(
        ModelProfile(
            model="gpt-image-2",
            base_url="https://image.example/v1",
            api_key="image-key",
            adapter="raw_chat_multimodal",
        ),
        http_client=http,
    )

    with pytest.raises(ValueError, match="safe image_fetcher"):
        await provider.generate_image("Create slide")


@pytest.mark.asyncio
async def test_raw_multimodal_image_provider_normalizes_content_block_data_url():
    image_b64 = base64.b64encode(b"block-image").decode()
    http = FakeImageHttpClient(
        {
            "choices": [
                {
                    "message": {
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                            }
                        ]
                    }
                }
            ]
        }
    )
    provider = RawMultimodalImageProvider(
        ModelProfile(
            model="gpt-image-2",
            base_url="https://image.example/v1",
            api_key="image-key",
            adapter="raw_chat_multimodal",
        ),
        http_client=http,
    )

    result = await provider.generate_image("Create slide")

    assert result.base64_data == image_b64


@pytest.mark.asyncio
async def test_raw_multimodal_image_provider_requires_configured_model():
    provider = RawMultimodalImageProvider(ModelProfile(model="", base_url="", api_key=""))

    with pytest.raises(ValueError, match="image model is not configured"):
        await provider.generate_image("Create slide")
