"""Chunking service with optional Chonkie integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class TextChunk:
    text: str
    start_index: int | None = None
    end_index: int | None = None
    token_count: int | None = None
    metadata: dict[str, Any] | None = None


class ChunkingService:
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        provider: str = "chonkie",
        tokenizer: str = "character",
    ) -> None:
        self.chunk_size = max(1, chunk_size)
        self.chunk_overlap = max(0, min(chunk_overlap, self.chunk_size - 1))
        self.provider = provider
        self.tokenizer = tokenizer

    def chunk(self, text: str) -> list[TextChunk]:
        if not text:
            return []
        if self.provider == "chonkie":
            chonkie_chunks = self._chunk_with_chonkie(text)
            if chonkie_chunks:
                return chonkie_chunks
        return self._chunk_simple(text)

    def _chunk_with_chonkie(self, text: str) -> list[TextChunk]:
        try:
            from chonkie import TokenChunker
        except Exception:
            return []

        chunker = TokenChunker(
            tokenizer=self.tokenizer,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )
        chunks = chunker.chunk(text)
        return [
            TextChunk(
                text=getattr(chunk, "text", str(chunk)).strip(),
                start_index=getattr(chunk, "start_index", None),
                end_index=getattr(chunk, "end_index", None),
                token_count=getattr(chunk, "token_count", None),
                metadata=getattr(chunk, "metadata", None) or {},
            )
            for chunk in chunks
            if getattr(chunk, "text", str(chunk)).strip()
        ]

    def _chunk_simple(self, text: str) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        start = 0
        while start < len(text):
            end = min(len(text), start + self.chunk_size)
            content = text[start:end].strip()
            if content:
                chunks.append(TextChunk(text=content, start_index=start, end_index=end))
            if end == len(text):
                break
            start = max(end - self.chunk_overlap, start + 1)
        return chunks
