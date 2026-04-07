"""OpenAI-compatible rerank provider."""

from __future__ import annotations

from typing import Any

import requests

from ...config import ModelProfile


class RerankProvider:
    def __init__(self, profile: ModelProfile) -> None:
        self.profile = profile

    @property
    def configured(self) -> bool:
        return bool(self.profile.model and self.profile.api_key and self.profile.base_url)

    async def rerank(self, query: str, results: list[dict[str, Any]], top_k: int = 5) -> list[dict[str, Any]]:
        if not self.configured:
            return results[:top_k]
        documents = [item["chunk"].content for item in results]
        response = requests.post(
            f"{self.profile.base_url.rstrip('/')}/rerank",
            headers={"Authorization": f"Bearer {self.profile.api_key}", "Content-Type": "application/json"},
            json={"model": self.profile.model, "query": query, "documents": documents, "top_n": top_k},
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        reranked = []
        for item in payload.get("results", []):
            index = item.get("index")
            if index is None or index >= len(results):
                continue
            original = dict(results[index])
            original["score"] = float(item.get("relevance_score", original.get("score", 0)))
            reranked.append(original)
        return reranked or results[:top_k]
