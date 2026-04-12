"""Source ingestion, parsing, chunking, and persistence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...core.interfaces.knowledge_repository import KnowledgeRepositoryInterface
from ...domain.source import KnowledgeChunk, KnowledgeSource, SourceKind, SourceStatus, utc_now
from ...infrastructure.parsers.docling_parser import DoclingParser
from .chunking_service import ChunkingService


class SourceService:
    def __init__(
        self,
        repository: KnowledgeRepositoryInterface,
        parser: Any | None = None,
        embedding_provider: Any | None = None,
        chunking_service: ChunkingService | None = None,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> None:
        self.repository = repository
        self.parser = parser or DoclingParser()
        self.embedding_provider = embedding_provider
        self.chunk_size = max(1, chunk_size)
        self.chunk_overlap = max(0, min(chunk_overlap, self.chunk_size - 1))
        self.chunking_service = chunking_service or ChunkingService(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )

    async def create_text_source(self, title: str, text: str, metadata: dict[str, Any] | None = None) -> KnowledgeSource:
        source = KnowledgeSource(
            kind=SourceKind.TEXT,
            title=title.strip() or "Pasted text",
            metadata=metadata or {},
        )
        await self.repository.save_source(source)
        try:
            parsed = await self.parser.parse_text(text, title=source.title)
            return await self._finish_source(source, parsed["content"], parsed.get("metadata", {}))
        except Exception as exc:
            return await self._fail_source(source, exc)

    async def create_file_source(
        self,
        file_path: str | Path,
        filename: str,
        mime_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgeSource:
        source = KnowledgeSource(
            kind=SourceKind.FILE,
            title=filename,
            filename=filename,
            mime_type=mime_type,
            file_path=str(file_path),
            metadata=metadata or {},
        )
        await self.repository.save_source(source)
        try:
            parsed = await self.parser.parse_file(file_path, filename=filename)
            parser_metadata = parsed.get("metadata", {})
            return await self._finish_source(source, parsed["content"], parser_metadata)
        except Exception as exc:
            return await self._fail_source(source, exc)

    async def list_sources(self) -> list[KnowledgeSource]:
        return await self.repository.list_sources()

    async def get_source(self, source_id: str) -> KnowledgeSource | None:
        return await self.repository.get_source(source_id)

    async def get_source_text(self, source_id: str) -> str:
        source = await self.repository.get_source(source_id)
        if not source:
            return ""
        return source.text

    async def delete_source(self, source_id: str) -> bool:
        return await self.repository.delete_source(source_id)

    async def _finish_source(
        self,
        source: KnowledgeSource,
        text: str,
        parser_metadata: dict[str, Any],
    ) -> KnowledgeSource:
        source.text = text
        source.char_count = len(text)
        source.metadata = {**source.metadata, **parser_metadata}
        chunks = self._chunk_source(source)
        if self.embedding_provider and chunks:
            embeddings = await self.embedding_provider.embed([chunk.content for chunk in chunks])
            for chunk, embedding in zip(chunks, embeddings):
                chunk.embedding = embedding
        source.chunk_count = len(chunks)
        source.status = SourceStatus.READY
        source.updated_at = utc_now()
        await self.repository.save_source(source)
        await self.repository.save_chunks(source.id, chunks)
        return source

    async def _fail_source(self, source: KnowledgeSource, exc: Exception) -> KnowledgeSource:
        source.status = SourceStatus.ERROR
        source.error = str(exc)
        source.updated_at = utc_now()
        await self.repository.save_source(source)
        return source

    def _chunk_source(self, source: KnowledgeSource) -> list[KnowledgeChunk]:
        text = source.text
        if not text:
            return []

        chunks: list[KnowledgeChunk] = []
        for index, chunk in enumerate(self.chunking_service.chunk(text)):
            chunks.append(
                KnowledgeChunk(
                    id=f"{source.id}_chunk_{index}",
                    source_id=source.id,
                    content=chunk.text,
                    chunk_index=index,
                    start_offset=chunk.start_index,
                    end_offset=chunk.end_index,
                    metadata={
                        "source_id": source.id,
                        "source_title": source.title,
                        "filename": source.filename,
                        "chunk_index": index,
                        "start_offset": chunk.start_index,
                        "end_offset": chunk.end_index,
                        "token_count": chunk.token_count,
                        "chunker": self.chunking_service.provider,
                        "parser": source.metadata.get("parser"),
                        "mime_type": source.mime_type or source.metadata.get("mime_type"),
                        **(chunk.metadata or {}),
                    },
                )
            )
        return chunks
