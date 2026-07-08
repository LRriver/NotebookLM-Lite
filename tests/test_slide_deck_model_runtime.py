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
    RequestsJsonClient,
)

PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAFgwJ/lrW3MgAAAABJRU5ErkJggg=="
)
JPEG_BYTES = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////2wBDAf//////////////////////////////////////////////////////////////////////////////////////wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAX/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIQAxAAAAH/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAEFAqf/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAEDAQE/ASP/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAECAQE/ASP/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAY/Al//xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAE/IV//2gAMAwEAAgADAAAAEP/EFBQRAQAAAAAAAAAAAAAAAAAAARD/2gAIAQMBAT8QH//EFBQRAQAAAAAAAAAAAAAAAAAAARD/2gAIAQIBAT8QH//EFBABAQAAAAAAAAAAAAAAAAAAARD/2gAIAQEAAT8QH//Z"
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
        self.downloads = []
        self.download_bytes = PNG_BYTES

    async def post_json(self, url, headers, json_payload, timeout):
        self.calls.append((url, headers, json_payload, timeout))
        return self.payload

    async def get_bytes(self, url, timeout):
        self.downloads.append((url, timeout))
        return self.download_bytes


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
        config={
            "page_count": 1,
            "language": "English",
            "style": "technical",
            "source_context": "TLS protects HTTP traffic.",
        },
    )
    prompt_plan = await service.generate_prompt_plan(
        source_context="TLS protects HTTP traffic.",
        outline=outline,
        config={"page_count": 1, "source_context": "TLS protects HTTP traffic."},
    )

    assert isinstance(outline, SlideDeckOutline)
    assert isinstance(prompt_plan, SlidePromptPlanSet)
    assert llm.calls[0]["response_model"] is SlideDeckOutline
    assert llm.calls[1]["response_model"] is SlidePromptPlanSet
    assert "TLS protects HTTP traffic" in llm.calls[0]["prompt"]
    assert "source_context" not in llm.calls[0]["prompt"]
    assert "source_context" not in llm.calls[1]["prompt"]


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
    image_b64 = base64.b64encode(PNG_BYTES).decode()
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
async def test_raw_multimodal_image_provider_supports_openai_image_generations_adapter():
    http = FakeImageHttpClient({"images": [{"url": "https://cdn.example/generated.png"}]})
    provider = RawMultimodalImageProvider(
        ModelProfile(
            model="gpt-image-2",
            base_url="https://image.example/v1",
            api_key="image-key",
            adapter="openai_image",
        ),
        http_client=http,
    )

    result = await provider.generate_image("Create slide", aspect_ratio="16:9", quality="2K")

    assert result.base64_data == base64.b64encode(PNG_BYTES).decode()
    url, headers, payload, timeout = http.calls[0]
    assert url == "https://image.example/v1/images/generations"
    assert headers["Authorization"] == "Bearer image-key"
    assert payload["model"] == "gpt-image-2"
    assert payload["prompt"].startswith("Create slide")
    assert payload["size"] == "1024x576"
    assert timeout == 180
    assert http.downloads == [("https://cdn.example/generated.png", 180)]


@pytest.mark.asyncio
async def test_raw_multimodal_image_provider_supports_siliconflow_image_generations_adapter():
    http = FakeImageHttpClient({"images": [{"url": "https://cdn.example/generated.png"}]})
    provider = RawMultimodalImageProvider(
        ModelProfile(
            model="Qwen/Qwen-Image",
            base_url="https://api.siliconflow.cn/v1",
            api_key="image-key",
            adapter="siliconflow_image",
        ),
        http_client=http,
    )

    result = await provider.generate_image("Create slide", aspect_ratio="16:9", quality="2K")

    assert result.base64_data == base64.b64encode(PNG_BYTES).decode()
    url, _headers, payload, _timeout = http.calls[0]
    assert url == "https://api.siliconflow.cn/v1/images/generations"
    assert payload["model"] == "Qwen/Qwen-Image"
    assert payload["image_size"] == "1024x576"
    assert "size" not in payload


@pytest.mark.asyncio
async def test_generated_image_url_download_rejects_localhost():
    client = RequestsJsonClient()

    with pytest.raises(ValueError, match="not allowed"):
        await client.get_bytes("http://127.0.0.1/private.png", 1)


@pytest.mark.asyncio
async def test_generated_image_url_download_rejects_non_image_content(monkeypatch: pytest.MonkeyPatch):
    class FakeResponse:
        status_code = 200
        headers = {"Content-Type": "text/plain"}
        content = b"not an image"

        def raise_for_status(self):
            return None

        def iter_content(self, chunk_size: int):
            yield b"not an image"

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: FakeResponse())

    client = RequestsJsonClient()

    with pytest.raises(ValueError, match="did not return an image"):
        await client.get_bytes("https://8.8.8.8/file.txt", 1)


@pytest.mark.asyncio
async def test_raw_multimodal_image_provider_builds_edit_payload():
    edited_b64 = base64.b64encode(PNG_BYTES).decode()
    source_b64 = base64.b64encode(PNG_BYTES).decode()
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
async def test_raw_multimodal_image_provider_edit_downloads_url_response_with_safe_http_client():
    source_b64 = base64.b64encode(PNG_BYTES).decode()
    http = FakeImageHttpClient({"choices": [{"message": {"content": "![edited](https://cdn.example/edited.png)"}}]})
    provider = RawMultimodalImageProvider(
        ModelProfile(
            model="gpt-image-2",
            base_url="https://image.example/v1",
            api_key="edit-key",
            adapter="raw_chat_multimodal",
        ),
        http_client=http,
    )

    result = await provider.edit_image(source_b64, "Make title shorter")

    assert result.base64_data == base64.b64encode(PNG_BYTES).decode()
    assert http.downloads == [("https://cdn.example/edited.png", 180)]


@pytest.mark.asyncio
async def test_raw_multimodal_image_provider_rejects_generation_only_adapter_for_edit():
    source_b64 = base64.b64encode(PNG_BYTES).decode()
    http = FakeImageHttpClient({"images": [{"url": "https://cdn.example/edited.png"}]})
    provider = RawMultimodalImageProvider(
        ModelProfile(
            model="Qwen/Qwen-Image",
            base_url="https://api.siliconflow.cn/v1",
            api_key="edit-key",
            adapter="siliconflow_image",
        ),
        http_client=http,
    )

    with pytest.raises(ValueError, match="does not support image editing"):
        await provider.edit_image(source_b64, "Make title shorter")

    assert http.calls == []


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
        image_fetcher=lambda url: PNG_BYTES,
    )

    result = await provider.generate_image("Create slide")

    assert result.base64_data == base64.b64encode(PNG_BYTES).decode()
    assert result.mime_type == "image/png"


@pytest.mark.asyncio
async def test_raw_multimodal_image_provider_downloads_generation_url_with_safe_http_client():
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

    result = await provider.generate_image("Create slide")

    assert result.base64_data == base64.b64encode(PNG_BYTES).decode()
    assert http.downloads == [("https://cdn.example/slide.png", 180)]


@pytest.mark.asyncio
async def test_raw_multimodal_image_provider_preserves_downloaded_url_mime_type():
    http = FakeImageHttpClient({"choices": [{"message": {"content": "https://cdn.example/slide.jpg"}}]})
    http.download_bytes = JPEG_BYTES
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

    assert result.base64_data == base64.b64encode(JPEG_BYTES).decode()
    assert result.mime_type == "image/jpeg"


@pytest.mark.asyncio
async def test_raw_multimodal_image_provider_rejects_non_image_base64():
    not_image_b64 = base64.b64encode(b"not an image").decode()
    http = FakeImageHttpClient({"choices": [{"message": {"content": not_image_b64}}]})
    provider = RawMultimodalImageProvider(
        ModelProfile(
            model="gpt-image-2",
            base_url="https://image.example/v1",
            api_key="image-key",
            adapter="raw_chat_multimodal",
        ),
        http_client=http,
    )

    with pytest.raises(ValueError, match="did not contain a raster image"):
        await provider.generate_image("Create slide")


@pytest.mark.asyncio
async def test_raw_multimodal_image_provider_normalizes_content_block_data_url():
    image_b64 = base64.b64encode(PNG_BYTES).decode()
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
