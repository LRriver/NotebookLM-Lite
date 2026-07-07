"""OpenAI-compatible raw multimodal image generation/edit provider."""

from __future__ import annotations

import asyncio
import base64
import ipaddress
import inspect
import re
import socket
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import requests

from ...config import ModelProfile

MAX_GENERATED_IMAGE_BYTES = 15 * 1024 * 1024


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

    async def get_bytes(self, url: str, timeout: int) -> bytes:
        def get() -> bytes:
            _ensure_public_image_url(url)
            response = requests.get(url, timeout=timeout, allow_redirects=False, stream=True)
            if 300 <= response.status_code < 400:
                raise ValueError("redirecting generated image URLs are not supported")
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if content_type and not content_type.startswith("image/") and content_type != "application/octet-stream":
                raise ValueError("generated image URL did not return an image")

            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                total += len(chunk)
                if total > MAX_GENERATED_IMAGE_BYTES:
                    raise ValueError("generated image is too large")
                chunks.append(chunk)
            content = b"".join(chunks)
            if not _looks_like_raster_image(content):
                raise ValueError("generated image URL did not return an image")
            return content

        return await asyncio.to_thread(get)


def _looks_like_raster_image(content: bytes) -> bool:
    return (
        content.startswith(b"\x89PNG\r\n\x1a\n")
        or content.startswith(b"\xff\xd8\xff")
        or content.startswith(b"GIF87a")
        or content.startswith(b"GIF89a")
        or content.startswith(b"RIFF") and content[8:12] == b"WEBP"
    )


def _ensure_public_image_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("generated image URL must be http(s)")
    host = parsed.hostname.strip().lower()
    if host in {"localhost", "localhost.localdomain"}:
        raise ValueError("generated image URL host is not allowed")

    def reject_private(address: str) -> None:
        ip = ipaddress.ip_address(address)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise ValueError("generated image URL host is not allowed")

    try:
        reject_private(host)
        return
    except ValueError as exc:
        if "does not appear to be an IPv4 or IPv6 address" not in str(exc):
            raise

    try:
        for result in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM):
            reject_private(result[4][0])
    except socket.gaierror as exc:
        raise ValueError("generated image URL host could not be resolved") from exc


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
        if self.profile.adapter in {"openai_image", "openai_images", "siliconflow_image"}:
            return await self._normalize(
                await self.http_client.post_json(
                    self._images_url(),
                    self._headers(),
                    self._images_payload(content, aspect_ratio),
                    180,
                ),
                allow_http_client_fetch=True,
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
        if self.profile.adapter in {"openai_image", "openai_images", "siliconflow_image"}:
            raise ValueError(f"image adapter {self.profile.adapter} does not support image editing")
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
        if self.profile.adapter and self.profile.adapter not in {
            "raw_chat_multimodal",
            "openai_chat",
            "openai_image",
            "openai_images",
            "siliconflow_image",
        }:
            raise ValueError(f"unsupported image model adapter: {self.profile.adapter}")

    def _payload(self, content: Any) -> dict[str, Any]:
        return {
            "model": self.profile.model,
            "messages": [{"role": "user", "content": content}],
            "max_tokens": 2000,
        }

    def _chat_url(self) -> str:
        return f"{self.profile.base_url.rstrip('/')}/chat/completions"

    def _images_url(self) -> str:
        return f"{self.profile.base_url.rstrip('/')}/images/generations"

    def _images_payload(self, prompt: str, aspect_ratio: str) -> dict[str, Any]:
        payload = {
            "model": self.profile.model,
            "prompt": prompt,
        }
        if self.profile.adapter == "siliconflow_image":
            payload["image_size"] = self._image_size(aspect_ratio)
        else:
            payload["size"] = self._image_size(aspect_ratio)
        return payload

    @staticmethod
    def _image_size(aspect_ratio: str) -> str:
        normalized = aspect_ratio.strip()
        if normalized == "4:3":
            return "1024x768"
        if normalized == "1:1":
            return "1024x1024"
        return "1024x576"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.profile.api_key}",
            "Content-Type": "application/json",
        }

    async def _normalize(self, payload: Any, allow_http_client_fetch: bool = False) -> ImageGenerationResult:
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
                if not allow_http_client_fetch or not hasattr(self.http_client, "get_bytes"):
                    raise ValueError("URL image responses require a safe image_fetcher")
                image_bytes = await self.http_client.get_bytes(text, 180)
            elif inspect.iscoroutinefunction(self.image_fetcher):
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
        if isinstance(payload.get("images"), list) and payload["images"]:
            return self._extract_candidate(payload["images"][0])
        image_url = payload.get("image_url")
        if isinstance(image_url, dict) and image_url.get("url"):
            return image_url["url"]
        if isinstance(payload.get("data"), list) and payload["data"]:
            return self._extract_candidate(payload["data"][0])
        if isinstance(payload.get("choices"), list) and payload["choices"]:
            message = payload["choices"][0].get("message", {})
            return self._extract_candidate(message.get("content"))
        return None
