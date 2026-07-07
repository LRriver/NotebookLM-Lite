"""OpenAI-compatible raw multimodal image generation/edit provider."""

from __future__ import annotations

import asyncio
import base64
import inspect
import re
from dataclasses import dataclass
from typing import Any

import requests

from ...config import ModelProfile


@dataclass(frozen=True)
class ImageGenerationResult:
    base64_data: str
    mime_type: str = "image/png"


class RequestsJsonClient:
    async def post_json(
        self,
        url: str,
        headers: dict[str, str],
        json_payload: dict[str, Any],
        timeout: int,
    ) -> dict[str, Any]:
        def post() -> dict[str, Any]:
            response = requests.post(url, headers=headers, json=json_payload, timeout=timeout)
            response.raise_for_status()
            return response.json()

        return await asyncio.to_thread(post)


class RawMultimodalImageProvider:
    def __init__(
        self,
        profile: ModelProfile,
        http_client: Any | None = None,
        image_fetcher: Any | None = None,
    ) -> None:
        self.profile = profile
        self.http_client = http_client or RequestsJsonClient()
        self.image_fetcher = image_fetcher

    async def generate_image(
        self,
        prompt: str,
        aspect_ratio: str = "16:9",
        quality: str = "2K",
    ) -> ImageGenerationResult:
        self._ensure_configured()
        content = (
            f"{prompt}\n\n"
            f"输出画幅: {aspect_ratio}，质量: {quality}。"
            "请直接生成一张可用于 PPT 的图片，优先返回图片链接或 base64。"
        )
        payload = self._payload(content)
        return await self._normalize(
            await self.http_client.post_json(
                self._chat_url(),
                self._headers(),
                payload,
                180,
            )
        )

    async def edit_image(
        self,
        image_base64: str,
        instruction: str,
        aspect_ratio: str = "16:9",
        quality: str = "2K",
    ) -> ImageGenerationResult:
        self._ensure_configured()
        content = [
            {
                "type": "text",
                "text": (
                    f"{instruction}\n\n"
                    f"输出画幅: {aspect_ratio}，质量: {quality}。"
                    "请返回修改后的图片，优先返回图片链接或 base64。"
                ),
            },
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{image_base64}"},
            },
        ]
        return await self._normalize(
            await self.http_client.post_json(
                self._chat_url(),
                self._headers(),
                self._payload(content),
                180,
            )
        )

    def _ensure_configured(self) -> None:
        if not self.profile.model or not self.profile.base_url or not self.profile.api_key:
            raise ValueError("image model is not configured")
        if self.profile.adapter and self.profile.adapter not in {"raw_chat_multimodal", "openai_chat"}:
            raise ValueError(f"unsupported image model adapter: {self.profile.adapter}")

    def _payload(self, content: Any) -> dict[str, Any]:
        return {
            "model": self.profile.model,
            "messages": [{"role": "user", "content": content}],
            "max_tokens": 2000,
        }

    def _chat_url(self) -> str:
        return f"{self.profile.base_url.rstrip('/')}/chat/completions"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.profile.api_key}",
            "Content-Type": "application/json",
        }

    async def _normalize(self, payload: Any) -> ImageGenerationResult:
        candidate = self._extract_candidate(payload)
        if not candidate:
            raise ValueError("model response did not contain an image")
        text = str(candidate).strip()
        data_url = re.match(r"^data:(image/[^;]+);base64,(.+)$", text, re.DOTALL)
        if data_url:
            data = data_url.group(2).strip()
            base64.b64decode(data, validate=True)
            return ImageGenerationResult(base64_data=data, mime_type=data_url.group(1))
        if text.startswith("http://") or text.startswith("https://"):
            if self.image_fetcher is None:
                raise ValueError("URL image responses require a safe image_fetcher")
            if inspect.iscoroutinefunction(self.image_fetcher):
                image_bytes = await self.image_fetcher(text)
            else:
                image_bytes = await asyncio.to_thread(self.image_fetcher, text)
            return ImageGenerationResult(base64_data=base64.b64encode(image_bytes).decode())
        base64.b64decode(text, validate=True)
        return ImageGenerationResult(base64_data=text)

    def _extract_candidate(self, payload: Any) -> Any:
        if isinstance(payload, str):
            markdown = re.search(r"!\[[^\]]*]\((https?://[^)]+)\)", payload)
            return markdown.group(1) if markdown else payload
        if isinstance(payload, list):
            for item in payload:
                candidate = self._extract_candidate(item)
                if candidate:
                    return candidate
            return None
        if not isinstance(payload, dict):
            return None
        if payload.get("b64_json"):
            return payload["b64_json"]
        if payload.get("image_base64"):
            return payload["image_base64"]
        if payload.get("url"):
            return payload["url"]
        image_url = payload.get("image_url")
        if isinstance(image_url, dict) and image_url.get("url"):
            return image_url["url"]
        if isinstance(payload.get("data"), list) and payload["data"]:
            return self._extract_candidate(payload["data"][0])
        if isinstance(payload.get("choices"), list) and payload["choices"]:
            message = payload["choices"][0].get("message", {})
            return self._extract_candidate(message.get("content"))
        return None
