"""Studio artifact generation and persistence."""

from __future__ import annotations

import json
from html import escape
from typing import Any

from ...core.interfaces.knowledge_repository import KnowledgeRepositoryInterface
from ...domain.artifact_schemas import ARTIFACT_RESPONSE_MODELS, artifact_payload_to_markdown
from ...domain.source import Artifact, ArtifactType, Job, JobStatus, utc_now

PLACEHOLDER_ARTIFACTS = {
    "video_overview": {
        "title": "Video Overview",
        "official_capability": "NotebookLM Video Overviews",
        "message": "Video Overview generation is not implemented yet. This placeholder reserves the Studio boundary for narrated slide/video generation.",
    },
}


class ArtifactService:
    def __init__(self, repository: KnowledgeRepositoryInterface, llm_provider: Any) -> None:
        self.repository = repository
        self.llm = llm_provider

    async def generate_artifact(
        self,
        artifact_type: str,
        source_ids: list[str],
        instruction: str = "",
    ) -> Artifact:
        if artifact_type not in ARTIFACT_RESPONSE_MODELS:
            raise ValueError(f"Unsupported artifact type: {artifact_type}")
        if not source_ids:
            raise ValueError("source_ids is required")

        job = Job(job_type=f"studio:{artifact_type}", status=JobStatus.RUNNING, source_ids=source_ids)
        await self.repository.save_job(job)
        try:
            if artifact_type in PLACEHOLDER_ARTIFACTS:
                payload = {"adapter_status": "placeholder", **PLACEHOLDER_ARTIFACTS[artifact_type]}
                markdown = artifact_payload_to_markdown(artifact_type, payload)
                artifact = Artifact(
                    artifact_type=ArtifactType(artifact_type),
                    title=payload["title"],
                    source_ids=source_ids,
                    payload=payload,
                    markdown=markdown,
                    status=JobStatus.SUCCEEDED,
                )
                await self.repository.save_artifact(artifact)
                job.status = JobStatus.SUCCEEDED
                job.result_ref = artifact.id
                job.updated_at = utc_now()
                await self.repository.save_job(job)
                return artifact

            context = await self._context_for_sources(source_ids)
            prompt = self._prompt(artifact_type, context, instruction)
            model = ARTIFACT_RESPONSE_MODELS[artifact_type]
            parsed = await self.llm.generate_structured(prompt, model, temperature=0.2)
            payload = parsed.model_dump()
            file_refs: list[dict[str, Any]] = []
            if artifact_type == "infographic":
                payload["svg"] = self._infographic_svg(payload)
                file_refs.append({"format": "svg", "mime_type": "image/svg+xml", "name": f"{payload.get('title', 'infographic')}.svg"})
            markdown = artifact_payload_to_markdown(artifact_type, payload)
            artifact = Artifact(
                artifact_type=ArtifactType(artifact_type),
                title=payload.get("title", artifact_type),
                source_ids=source_ids,
                payload=payload,
                markdown=markdown,
                file_refs=file_refs,
                status=JobStatus.SUCCEEDED,
            )
            await self.repository.save_artifact(artifact)
            job.status = JobStatus.SUCCEEDED
            job.result_ref = artifact.id
            job.updated_at = utc_now()
            await self.repository.save_job(job)
            return artifact
        except Exception as exc:
            job.status = JobStatus.FAILED
            job.error = str(exc)
            job.updated_at = utc_now()
            await self.repository.save_job(job)
            raise

    async def list_artifacts(self) -> list[Artifact]:
        return await self.repository.list_artifacts()

    async def get_artifact(self, artifact_id: str) -> Artifact | None:
        return await self.repository.get_artifact(artifact_id)

    async def create_research_placeholder(self, query: str, source_ids: list[str]) -> Job:
        job = Job(
            job_type="deep_research",
            status=JobStatus.PENDING,
            source_ids=source_ids,
            request={"query": query},
        )
        return await self.repository.save_job(job)

    async def _context_for_sources(self, source_ids: list[str]) -> str:
        parts = []
        for source_id in source_ids:
            source = await self.repository.get_source(source_id)
            if source:
                parts.append(f"## {source.title}\n\n{source.text[:6000]}")
        if not parts:
            raise ValueError("No selected source content found")
        return "\n\n---\n\n".join(parts)

    @staticmethod
    def _prompt(artifact_type: str, context: str, instruction: str) -> str:
        labels = {
            "mind_map": "mind map / 思维图谱",
            "faq": "FAQ",
            "flashcards": "flashcards and quiz",
            "quiz": "flashcards and quiz",
            "report": "report",
            "study_guide": "study guide",
            "data_table": "data table",
            "podcast_script": "podcast script",
            "ppt_outline": "PPT outline placeholder",
            "infographic": "infographic / 信息图 brief",
        }
        return (
            f"Generate a {labels.get(artifact_type, artifact_type)} from the selected sources. "
            f"Instruction: {instruction or 'Use the source material faithfully.'}\n\n"
            f"Sources:\n{context}"
        )

    @staticmethod
    def artifact_as_json(artifact: Artifact) -> str:
        return json.dumps(artifact.payload, ensure_ascii=False, indent=2)

    @staticmethod
    def _infographic_svg(payload: dict[str, Any]) -> str:
        title = escape(str(payload.get("title", "Infographic")))
        subtitle = escape(str(payload.get("subtitle", "")))
        footer = escape(str(payload.get("footer", "")))
        sections = payload.get("sections") if isinstance(payload.get("sections"), list) else []
        palette = ["#0f766e", "#2563eb", "#f97316", "#7c3aed", "#dc2626", "#0891b2"]
        width = 960
        card_width = 420
        card_height = 130
        gap = 24
        top = 162
        rows = max(1, (len(sections) + 1) // 2)
        height = max(540, top + rows * (card_height + gap) + 72)
        cards = []
        for index, section in enumerate(sections[:8]):
            x = 56 + (index % 2) * (card_width + gap)
            y = top + (index // 2) * (card_height + gap)
            color = palette[index % len(palette)]
            heading = escape(str(section.get("heading", "")))
            stat = escape(str(section.get("stat", "")))
            body = escape(str(section.get("body", "")))
            cards.append(
                f"""
                <g>
                  <rect x="{x}" y="{y}" width="{card_width}" height="{card_height}" rx="14" fill="#ffffff" stroke="#fed7aa"/>
                  <circle cx="{x + 34}" cy="{y + 34}" r="16" fill="{color}" opacity="0.92"/>
                  <text x="{x + 62}" y="{y + 38}" font-size="22" font-weight="800" fill="#1f2937">{heading}</text>
                  <text x="{x + 24}" y="{y + 76}" font-size="18" font-weight="800" fill="{color}">{stat}</text>
                  <foreignObject x="{x + 24}" y="{y + 88}" width="{card_width - 48}" height="52">
                    <div xmlns="http://www.w3.org/1999/xhtml" style="font: 15px system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color: #475569; line-height: 1.35;">{body}</div>
                  </foreignObject>
                </g>
                """
            )
        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{title}">
  <rect width="{width}" height="{height}" fill="#fff7ed"/>
  <circle cx="835" cy="92" r="86" fill="#ccfbf1" opacity="0.85"/>
  <circle cx="104" cy="474" r="118" fill="#dbeafe" opacity="0.72"/>
  <text x="56" y="76" font-family="Inter, system-ui, sans-serif" font-size="44" font-weight="900" fill="#111827">{title}</text>
  <text x="58" y="116" font-family="Inter, system-ui, sans-serif" font-size="19" font-weight="600" fill="#64748b">{subtitle}</text>
  {"".join(cards)}
  <text x="56" y="{height - 34}" font-family="Inter, system-ui, sans-serif" font-size="14" font-weight="700" fill="#78716c">{footer}</text>
</svg>"""
