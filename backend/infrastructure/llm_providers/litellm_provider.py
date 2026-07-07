"""LiteLLM provider for text, structured output, and embeddings."""

from __future__ import annotations

import inspect
import json
from typing import Any, AsyncIterator, Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

from ...config import ModelProfile
from ...core.interfaces.llm_provider import LLMProviderInterface

T = TypeVar("T", bound=BaseModel)

OPENAI_COMPATIBLE_ADAPTERS = {"openai_chat", "openai_embedding"}
KNOWN_LITELLM_PROVIDER_PREFIXES = (
    "anthropic/",
    "azure/",
    "azure_ai/",
    "bedrock/",
    "cohere/",
    "deepseek/",
    "fireworks_ai/",
    "gemini/",
    "groq/",
    "huggingface/",
    "mistral/",
    "ollama/",
    "openai/",
    "openrouter/",
    "replicate/",
    "together_ai/",
    "vertex_ai/",
)


class LiteLLMProvider(LLMProviderInterface):
    def __init__(self, profile: ModelProfile, client: Any | None = None) -> None:
        self.profile = profile
        self.client = client or self._default_client()

    @staticmethod
    def _default_client() -> Any:
        try:
            import litellm
        except Exception:
            litellm = None

        class Client:
            async def completion(self, **kwargs: Any) -> Any:
                if litellm is not None:
                    return await litellm.acompletion(**kwargs)
                from openai import AsyncOpenAI

                client = AsyncOpenAI(
                    api_key=kwargs.get("api_key") or "not-set",
                    base_url=kwargs.get("api_base") or None,
                )
                model = kwargs["model"]
                if model.startswith("openai/"):
                    model = model.split("/", 1)[1]
                return await client.chat.completions.create(
                    model=model,
                    messages=kwargs["messages"],
                    temperature=kwargs.get("temperature", 0.7),
                    max_tokens=kwargs.get("max_tokens"),
                    response_format=kwargs.get("response_format"),
                )

            async def embedding(self, **kwargs: Any) -> Any:
                if litellm is not None:
                    return await litellm.aembedding(**kwargs)
                from openai import AsyncOpenAI

                client = AsyncOpenAI(
                    api_key=kwargs.get("api_key") or "not-set",
                    base_url=kwargs.get("api_base") or None,
                )
                model = kwargs["model"]
                if model.startswith("openai/"):
                    model = model.split("/", 1)[1]
                return await client.embeddings.create(model=model, input=kwargs["input"])

        return Client()

    @property
    def model_name(self) -> str:
        return self.profile.model

    @property
    def provider_name(self) -> str:
        return "litellm"

    def _model_for_litellm(self) -> str:
        model = self.profile.model
        has_litellm_prefix = model.startswith(KNOWN_LITELLM_PROVIDER_PREFIXES)
        if self.profile.adapter in OPENAI_COMPATIBLE_ADAPTERS and not has_litellm_prefix:
            return f"openai/{model}"
        return model

    def _completion_kwargs(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._model_for_litellm(),
            "messages": messages,
            "temperature": temperature,
            **kwargs,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if self.profile.api_key:
            payload["api_key"] = self.profile.api_key
        if self.profile.base_url:
            payload["api_base"] = self.profile.base_url
        if self.profile.thinking is not None and self.profile.thinking.type != "disabled":
            payload["thinking"] = {"type": self.profile.thinking.type}
        return payload

    @staticmethod
    async def _maybe_await(value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value

    @staticmethod
    def _content_from_response(response: Any) -> str:
        if isinstance(response, dict):
            return response["choices"][0]["message"]["content"]
        return response.choices[0].message.content

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        response = await self._maybe_await(
            self.client.completion(
                **self._completion_kwargs(messages, temperature, max_tokens=max_tokens, **kwargs)
            )
        )
        return self._content_from_response(response)

    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> T:
        schema = json.dumps(response_model.model_json_schema(), ensure_ascii=False)
        structured_prompt = (
            f"{prompt}\n\nReturn only valid JSON that conforms to this JSON Schema:\n{schema}"
        )
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": structured_prompt})

        last_error: Exception | None = None
        for attempt in range(2):
            response = await self._maybe_await(
                self.client.completion(
                    **self._completion_kwargs(
                        messages,
                        temperature,
                        response_format={"type": "json_object"},
                        **kwargs,
                    )
                )
            )
            content = self._content_from_response(response)
            try:
                return response_model.model_validate_json(content)
            except ValidationError as exc:
                last_error = exc
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Fix the JSON so it validates against the schema. "
                            f"Validation error: {exc}. Previous JSON: {content}"
                        ),
                    }
                )
        assert last_error is not None
        raise last_error

    async def generate_with_context(
        self,
        query: str,
        context: list[str],
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        context_text = "\n\n---\n\n".join(context)
        prompt = f"""基于以下参考资料回答问题。如果资料中没有相关信息，请如实说明。

【参考资料】
{context_text}

【问题】
{query}

【回答】"""
        return await self.generate(
            prompt=prompt,
            system_prompt=system_prompt or "你是一个基于资料回答问题的助手。",
            **kwargs,
        )

    async def stream_generate_with_context(
        self,
        query: str,
        context: list[str],
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        context_text = "\n\n---\n\n".join(context)
        prompt = f"""基于以下参考资料回答问题。如果资料中没有相关信息，请如实说明。

【参考资料】
{context_text}

【问题】
{query}

【回答】"""
        messages = [
            {"role": "system", "content": system_prompt or "你是一个基于资料回答问题的助手。"},
            {"role": "user", "content": prompt},
        ]
        stream = await self._maybe_await(
            self.client.completion(
                **self._completion_kwargs(messages, kwargs.pop("temperature", 0.7), stream=True, **kwargs)
            )
        )
        if hasattr(stream, "__aiter__"):
            async for chunk in stream:
                content = self._content_from_stream_chunk(chunk)
                if content:
                    yield content
            return

        content = self._content_from_response(stream)
        for index in range(0, len(content), 80):
            yield content[index:index + 80]

    async def embed(self, text: str | list[str]) -> list[float] | list[list[float]]:
        inputs = text if isinstance(text, list) else [text]
        payload: dict[str, Any] = {"model": self._model_for_litellm(), "input": inputs}
        if self.profile.api_key:
            payload["api_key"] = self.profile.api_key
        if self.profile.base_url:
            payload["api_base"] = self.profile.base_url
        response = await self._maybe_await(self.client.embedding(**payload))
        data = response["data"] if isinstance(response, dict) else response.data
        embeddings = [item["embedding"] if isinstance(item, dict) else item.embedding for item in data]
        return embeddings if isinstance(text, list) else embeddings[0]

    @staticmethod
    def _content_from_stream_chunk(chunk: Any) -> str:
        if isinstance(chunk, dict):
            choice = chunk.get("choices", [{}])[0]
            delta = choice.get("delta") or {}
            return delta.get("content") or ""
        choice = chunk.choices[0]
        delta = getattr(choice, "delta", None)
        return getattr(delta, "content", "") or ""
