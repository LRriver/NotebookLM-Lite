"""In-memory repository used by tests and lightweight local wiring."""

from __future__ import annotations

from ...core.interfaces.knowledge_repository import KnowledgeRepositoryInterface
from ...domain.source import Artifact, Job, KnowledgeChunk, KnowledgeSource


class InMemoryKnowledgeRepository(KnowledgeRepositoryInterface):
    def __init__(self) -> None:
        self.sources: dict[str, KnowledgeSource] = {}
        self.chunks: dict[str, list[KnowledgeChunk]] = {}
        self.artifacts: dict[str, Artifact] = {}
        self.jobs: dict[str, Job] = {}

    async def save_source(self, source: KnowledgeSource) -> KnowledgeSource:
        self.sources[source.id] = source
        return source

    async def get_source(self, source_id: str) -> KnowledgeSource | None:
        return self.sources.get(source_id)

    async def list_sources(self) -> list[KnowledgeSource]:
        return list(self.sources.values())

    async def delete_source(self, source_id: str) -> bool:
        self.sources.pop(source_id, None)
        self.chunks.pop(source_id, None)
        return True

    async def save_chunks(self, source_id: str, chunks: list[KnowledgeChunk]) -> None:
        self.chunks[source_id] = chunks

    async def get_chunks(self, source_id: str) -> list[KnowledgeChunk]:
        return self.chunks.get(source_id, [])

    async def search_chunks(
        self,
        query: str,
        source_ids: list[str] | None = None,
        top_k: int = 5,
        query_embedding: list[float] | None = None,
        rerank_provider: object | None = None,
    ) -> list[dict]:
        allowed = set(source_ids or self.chunks.keys())
        results = []
        query_l = query.lower()
        for source_id, chunks in self.chunks.items():
            if source_id not in allowed:
                continue
            for chunk in chunks:
                score = chunk.content.lower().count(query_l)
                if query_l in chunk.content.lower() or not results:
                    results.append({"chunk": chunk, "score": float(score)})
        results = sorted(results, key=lambda item: item["score"], reverse=True)[:top_k]
        if rerank_provider and results:
            return await rerank_provider.rerank(query, results, top_k=top_k)
        return results

    async def save_artifact(self, artifact: Artifact) -> Artifact:
        self.artifacts[artifact.id] = artifact
        return artifact

    async def get_artifact(self, artifact_id: str) -> Artifact | None:
        return self.artifacts.get(artifact_id)

    async def list_artifacts(self) -> list[Artifact]:
        return list(self.artifacts.values())

    async def save_job(self, job: Job) -> Job:
        self.jobs[job.id] = job
        return job

    async def get_job(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)
