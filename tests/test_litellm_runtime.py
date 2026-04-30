from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel

from backend.config import ModelProfile, ThinkingConfig
from backend.dependencies import DependencyContainer
from backend.infrastructure.llm_providers.litellm_provider import LiteLLMProvider
from backend.infrastructure.tts_providers.audio_speech_provider import AudioSpeechProvider


class MiniSchema(BaseModel):
    title: str
    bullets: list[str]


@pytest.mark.asyncio
async def test_litellm_text_generation_forwards_base_url_and_thinking(fake_litellm_client):
    profile = ModelProfile(
        model="openai/test-chat",
        base_url="https://model.example/v1",
        api_key="test-key",
        thinking=ThinkingConfig(type="disabled"),
    )
    fake_litellm_client.push_response({"choices": [{"message": {"content": "hello"}}]})
    provider = LiteLLMProvider(profile=profile, client=fake_litellm_client)

    text = await provider.generate("Say hi", temperature=0.2)

    assert text == "hello"
    call = fake_litellm_client.completion_calls[0]
    assert call["model"] == "openai/test-chat"
    assert call["api_base"] == "https://model.example/v1"
    assert call["api_key"] == "test-key"
    assert call["thinking"] == {"type": "disabled"}


@pytest.mark.asyncio
async def test_openai_compatible_profile_adds_litellm_provider_prefix(fake_litellm_client):
    profile = ModelProfile(
        model="DeepSeek-V4-Pro",
        base_url="https://model.example/v1",
        api_key="test-key",
        adapter="openai_chat",
    )
    fake_litellm_client.push_response({"choices": [{"message": {"content": "hello"}}]})
    provider = LiteLLMProvider(profile=profile, client=fake_litellm_client)

    await provider.generate("Say hi")

    assert fake_litellm_client.completion_calls[0]["model"] == "openai/DeepSeek-V4-Pro"


@pytest.mark.asyncio
async def test_structured_output_retries_after_validation_failure(fake_litellm_client):
    profile = ModelProfile(model="openai/test-chat", api_key="test-key")
    fake_litellm_client.push_response({"choices": [{"message": {"content": '{"title": 1}'}}]})
    fake_litellm_client.push_response(
        {"choices": [{"message": {"content": '{"title": "ok", "bullets": ["a"]}'}}]}
    )
    provider = LiteLLMProvider(profile=profile, client=fake_litellm_client)

    parsed = await provider.generate_structured("Make JSON", MiniSchema)

    assert parsed.title == "ok"
    assert len(fake_litellm_client.completion_calls) == 2
    assert "Fix the JSON" in fake_litellm_client.completion_calls[1]["messages"][-1]["content"]


@pytest.mark.asyncio
async def test_embedding_uses_configured_profile(fake_litellm_client):
    profile = ModelProfile(model="openai/text-embedding-test", api_key="embedding-key")
    provider = LiteLLMProvider(profile=profile, client=fake_litellm_client)

    embedding = await provider.embed("source text")

    assert embedding == [0.1, 0.2, 0.3]
    assert fake_litellm_client.embedding_calls[0]["model"] == "openai/text-embedding-test"
    assert fake_litellm_client.embedding_calls[0]["input"] == ["source text"]


@pytest.mark.asyncio
async def test_openai_compatible_embedding_prefixes_models_with_internal_slashes(
    fake_litellm_client,
):
    profile = ModelProfile(
        model="Pro/BAAI/bge-m3",
        base_url="https://model.example/v1",
        api_key="embedding-key",
        adapter="openai_embedding",
    )
    provider = LiteLLMProvider(profile=profile, client=fake_litellm_client)

    await provider.embed("source text")

    assert fake_litellm_client.embedding_calls[0]["model"] == "openai/Pro/BAAI/bge-m3"


@pytest.mark.asyncio
async def test_audio_provider_writes_streaming_mp3_payload(tmp_path: Path):
    class FakeHttpClient:
        def __init__(self) -> None:
            self.calls = []

        async def post_stream(self, url, headers, json_payload, output_path):
            self.calls.append((url, headers, json_payload, output_path))
            Path(output_path).write_bytes(b"mp3-bytes")
            return {"status_code": 200, "bytes": 9}

    profile = ModelProfile(
        model="fnlp/MOSS-TTSD-v0.5",
        base_url="https://api.siliconflow.cn/v1",
        api_key="audio-key",
        voice="fnlp/MOSS-TTSD-v0.5:alex",
        response_format="mp3",
        stream=True,
    )
    http_client = FakeHttpClient()
    provider = AudioSpeechProvider(profile=profile, http_client=http_client)

    result = await provider.synthesize("hello transcript", tmp_path / "podcast.mp3")

    assert result["status"] == "succeeded"
    assert Path(result["path"]).read_bytes() == b"mp3-bytes"
    url, headers, payload, _ = http_client.calls[0]
    assert url == "https://api.siliconflow.cn/v1/audio/speech"
    assert headers["Authorization"] == "Bearer audio-key"
    assert payload["model"] == "fnlp/MOSS-TTSD-v0.5"
    assert payload["input"] == "hello transcript"
    assert payload["voice"] == "fnlp/MOSS-TTSD-v0.5:alex"
    assert payload["response_format"] == "mp3"
    assert payload["stream"] is True


def test_provider_mapping_adds_litellm_prefixes(sample_config_file):
    from backend.config import load_settings

    settings = load_settings(sample_config_file)

    anthropic = DependencyContainer._map_litellm_profile(
        provider="anthropic",
        api_key="key",
        base_url=None,
        model="claude-sonnet-4-5",
        settings=settings,
    )
    gemini = DependencyContainer._map_litellm_profile(
        provider="gemini",
        api_key="key",
        base_url=None,
        model="gemini-2.5-pro",
        settings=settings,
    )
    openai = DependencyContainer._map_litellm_profile(
        provider="openai",
        api_key="key",
        base_url="https://openai.example/v1",
        model="gpt-4o",
        settings=settings,
    )

    assert anthropic.model == "anthropic/claude-sonnet-4-5"
    assert gemini.model == "gemini/gemini-2.5-pro"
    assert openai.model == "openai/gpt-4o"
    assert openai.base_url == "https://openai.example/v1"
