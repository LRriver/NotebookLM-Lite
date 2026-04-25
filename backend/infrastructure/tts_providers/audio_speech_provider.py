"""OpenAI-compatible speech provider for configured audio_model profiles."""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

import requests

from ...config import ModelProfile


class RequestsStreamingClient:
    async def post_stream(
        self,
        url: str,
        headers: dict[str, str],
        json_payload: dict[str, Any],
        output_path: str | Path,
    ) -> dict[str, Any]:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with requests.post(url, headers=headers, json=json_payload, stream=True, timeout=120) as response:
            response.raise_for_status()
            total = 0
            with path.open("wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        total += len(chunk)
                        f.write(chunk)
        return {"status_code": response.status_code, "bytes": total}


class AudioSpeechProvider:
    def __init__(self, profile: ModelProfile, http_client: Any | None = None) -> None:
        self.profile = profile
        self.http_client = http_client or RequestsStreamingClient()

    @property
    def configured(self) -> bool:
        return bool(self.profile.model and self.profile.api_key and self.profile.base_url)

    async def synthesize(self, transcript: str, output_path: str | Path) -> dict[str, Any]:
        if not self.configured:
            return {"status": "skipped", "path": None, "error": "audio_model is not configured"}

        base_url = self.profile.base_url.rstrip("/")
        url = f"{base_url}/audio/speech"
        voice = self.profile.voice or (
            f"{self.profile.model}:alex" if "/" in self.profile.model else "alloy"
        )
        payload = {
            "model": self.profile.model,
            "input": transcript,
            "voice": voice,
            "response_format": self.profile.response_format or "mp3",
            "stream": self.profile.stream,
        }
        headers = {
            "Authorization": f"Bearer {self.profile.api_key}",
            "Content-Type": "application/json",
        }

        try:
            result = self.http_client.post_stream(url, headers, payload, output_path)
            if inspect.isawaitable(result):
                result = await result
            return {
                "status": "succeeded",
                "path": str(output_path),
                "bytes": result.get("bytes"),
                "response": result,
            }
        except Exception as exc:
            return {"status": "failed", "path": None, "error": str(exc)}
