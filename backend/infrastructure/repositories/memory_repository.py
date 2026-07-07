"""In-memory repository used by tests and lightweight local wiring."""

from __future__ import annotations

from ...core.interfaces.knowledge_repository import KnowledgeRepositoryInterface
from ...domain.slide_deck import SlideAsset, SlideDeckExport, SlideDeckJob, SlideDeckProject
from ...domain.source import Artifact, Job, KnowledgeChunk, KnowledgeSource, Note


class InMemoryKnowledgeRepository(KnowledgeRepositoryInterface):
    def __init__(self) -> None:
        self.sources: dict[str, KnowledgeSource] = {}
        self.chunks: dict[str, list[KnowledgeChunk]] = {}
        self.artifacts: dict[str, Artifact] = {}
        self.jobs: dict[str, Job] = {}
        self.notes: dict[str, Note] = {}
        self.slide_decks: dict[str, SlideDeckProject] = {}
        self.slide_assets: dict[str, SlideAsset] = {}
        self.slide_exports: dict[str, SlideDeckExport] = {}
        self.slide_deck_jobs: dict[str, SlideDeckJob] = {}

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

    async def save_note(self, note: Note) -> Note:
        self.notes[note.id] = note
        return note

    async def get_note(self, note_id: str) -> Note | None:
        return self.notes.get(note_id)

    async def list_notes(self, query: str | None = None) -> list[Note]:
        if not query:
            return list(self.notes.values())
        query_l = query.lower()
        return [
            note
            for note in self.notes.values()
            if query_l in note.title.lower() or query_l in note.body.lower()
        ]

    async def delete_note(self, note_id: str) -> bool:
        self.notes.pop(note_id, None)
        return True

    async def save_job(self, job: Job) -> Job:
        self.jobs[job.id] = job
        return job

    async def get_job(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    async def save_slide_deck(self, deck: SlideDeckProject) -> SlideDeckProject:
        self.slide_decks[deck.id] = deck
        return deck

    async def get_slide_deck(self, deck_id: str) -> SlideDeckProject | None:
        return self.slide_decks.get(deck_id)

    async def list_slide_decks(self) -> list[SlideDeckProject]:
        return list(self.slide_decks.values())

    async def save_slide_asset(self, asset: SlideAsset) -> SlideAsset:
        self.slide_assets[asset.id] = asset
        return asset

    async def get_slide_asset(self, asset_id: str) -> SlideAsset | None:
        return self.slide_assets.get(asset_id)

    async def save_slide_export(self, export: SlideDeckExport) -> SlideDeckExport:
        self.slide_exports[export.id] = export
        return export

    async def get_slide_export(self, export_id: str) -> SlideDeckExport | None:
        return self.slide_exports.get(export_id)

    async def list_slide_exports(self, deck_id: str) -> list[SlideDeckExport]:
        return [export for export in self.slide_exports.values() if export.deck_id == deck_id]

    async def save_slide_deck_job(self, job: SlideDeckJob) -> SlideDeckJob:
        self.slide_deck_jobs[job.id] = job
        return job

    async def get_slide_deck_job(self, job_id: str) -> SlideDeckJob | None:
        return self.slide_deck_jobs.get(job_id)

    async def list_slide_deck_jobs(self, deck_id: str) -> list[SlideDeckJob]:
        return [job for job in self.slide_deck_jobs.values() if job.deck_id == deck_id]
