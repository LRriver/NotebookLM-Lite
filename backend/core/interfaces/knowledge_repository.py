"""Repository interface for persisted knowledge-base entities."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from ...domain.source import Artifact, Job, KnowledgeChunk, KnowledgeSource, Note


class KnowledgeRepositoryInterface(ABC):
    @abstractmethod
    async def save_source(self, source: KnowledgeSource) -> KnowledgeSource:
        pass

    @abstractmethod
    async def get_source(self, source_id: str) -> Optional[KnowledgeSource]:
        pass

    @abstractmethod
    async def list_sources(self) -> list[KnowledgeSource]:
        pass

    @abstractmethod
    async def delete_source(self, source_id: str) -> bool:
        pass

    @abstractmethod
    async def save_chunks(self, source_id: str, chunks: list[KnowledgeChunk]) -> None:
        pass

    @abstractmethod
    async def get_chunks(self, source_id: str) -> list[KnowledgeChunk]:
        pass

    @abstractmethod
    async def search_chunks(
        self,
        query: str,
        source_ids: list[str] | None = None,
        top_k: int = 5,
        query_embedding: list[float] | None = None,
        rerank_provider: object | None = None,
    ) -> list[dict]:
        pass

    @abstractmethod
    async def save_artifact(self, artifact: Artifact) -> Artifact:
        pass

    @abstractmethod
    async def get_artifact(self, artifact_id: str) -> Optional[Artifact]:
        pass

    @abstractmethod
    async def list_artifacts(self) -> list[Artifact]:
        pass

    @abstractmethod
    async def save_note(self, note: Note) -> Note:
        pass

    @abstractmethod
    async def get_note(self, note_id: str) -> Optional[Note]:
        pass

    @abstractmethod
    async def list_notes(self, query: str | None = None) -> list[Note]:
        pass

    @abstractmethod
    async def delete_note(self, note_id: str) -> bool:
        pass

    @abstractmethod
    async def save_job(self, job: Job) -> Job:
        pass

    @abstractmethod
    async def get_job(self, job_id: str) -> Optional[Job]:
        pass
