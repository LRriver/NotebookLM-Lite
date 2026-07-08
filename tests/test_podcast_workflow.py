from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes.podcast import get_podcast_llm_factory, router as podcast_router
from backend.core.services.podcast_service import PodcastService
from backend.core.workflows.podcast_workflow import PodcastWorkflow
from backend.domain.podcast import DialogueTurn, DurationRange, PodcastExtension, PodcastScript
from backend.config import Settings
from backend.dependencies import get_audio_speech_provider, get_source_service, get_vector_store
from backend.infrastructure.repositories.memory_repository import InMemoryKnowledgeRepository


class PodcastLLM:
    def __init__(self, turn_text: str = "这是一段用于估算时长的播客对话内容。" * 4) -> None:
        self.turn_text = turn_text
        self.calls = []

    async def generate_structured(self, prompt, response_model, temperature=0.7, **kwargs):
        self.calls.append(response_model.__name__)
        if response_model is PodcastExtension:
            return PodcastExtension(
                dialogues=[
                    DialogueTurn(speaker="主持人", text=self.turn_text),
                    DialogueTurn(speaker="嘉宾", text=self.turn_text),
                    DialogueTurn(speaker="主持人", text=self.turn_text),
                    DialogueTurn(speaker="嘉宾", text=self.turn_text),
                    DialogueTurn(speaker="主持人", text=self.turn_text),
                ],
                transition_note="continue",
            )
        return PodcastScript(
            title="Podcast",
            host_name="主持人",
            guest_name="嘉宾",
            guest_intro="专家",
            dialogues=[
                DialogueTurn(speaker="主持人", text=self.turn_text),
                DialogueTurn(speaker="嘉宾", text=self.turn_text),
                DialogueTurn(speaker="主持人", text=self.turn_text),
                DialogueTurn(speaker="嘉宾", text=self.turn_text),
                DialogueTurn(speaker="主持人", text=self.turn_text),
                DialogueTurn(speaker="嘉宾", text=self.turn_text),
                DialogueTurn(speaker="主持人", text=self.turn_text),
                DialogueTurn(speaker="嘉宾", text=self.turn_text),
                DialogueTurn(speaker="主持人", text=self.turn_text),
                DialogueTurn(speaker="嘉宾", text=self.turn_text),
            ],
        )


class OversizedPodcastLLM:
    def __init__(self) -> None:
        self.calls = []

    async def generate_structured(self, prompt, response_model, temperature=0.7, **kwargs):
        self.calls.append((response_model.__name__, prompt))
        long_text = "这是明显超出短播客目标时长的详细解释。" * 8
        short_text = "压缩后的精简对话。" * 3
        text = short_text if len(self.calls) > 1 else long_text
        return PodcastScript(
            title="Podcast",
            host_name="主持人",
            guest_name="嘉宾",
            guest_intro="专家",
            dialogues=[
                DialogueTurn(speaker="主持人", text=text),
                DialogueTurn(speaker="嘉宾", text=text),
                DialogueTurn(speaker="主持人", text=text),
                DialogueTurn(speaker="嘉宾", text=text),
                DialogueTurn(speaker="主持人", text=text),
                DialogueTurn(speaker="嘉宾", text=text),
                DialogueTurn(speaker="主持人", text=text),
                DialogueTurn(speaker="嘉宾", text=text),
                DialogueTurn(speaker="主持人", text=text),
                DialogueTurn(speaker="嘉宾", text=text),
            ],
        )


class FakeAudio:
    async def synthesize(self, transcript: str, output_path: str | Path):
        Path(output_path).write_bytes(b"mp3")
        return {"status": "succeeded", "path": str(output_path), "bytes": 3}


class BrokenAudio:
    async def synthesize(self, transcript: str, output_path: str | Path):
        raise RuntimeError("tts failed")


class FakeSourceService:
    async def get_source_text(self, source_id: str) -> str:
        return f"{source_id} source material for podcast."


class EmptyVectorStore:
    pass


def test_duration_range_supports_thirty_minutes():
    assert DurationRange.from_minutes(30) == DurationRange.DEEP
    assert DurationRange.DEEP.max_minutes == 30


@pytest.mark.asyncio
async def test_podcast_expansion_can_target_20_to_30_minutes():
    workflow = PodcastWorkflow(PodcastLLM(turn_text="扩写内容" * 20), max_iterations=8)
    script = await workflow.generate("source", duration_range=DurationRange.DEEP)

    assert script.estimated_duration_minutes >= DurationRange.DEEP.min_minutes
    assert "target range 20-30" in script.coverage_notes[-1]
    assert "PodcastExtension" in workflow.llm.calls


@pytest.mark.asyncio
async def test_podcast_generation_condenses_scripts_that_exceed_duration_range():
    llm = OversizedPodcastLLM()
    workflow = PodcastWorkflow(llm)

    script = await workflow.generate("source", duration_range=DurationRange.SHORT)

    assert script.estimated_duration_minutes <= DurationRange.SHORT.max_minutes
    assert len([name for name, _ in llm.calls if name == "PodcastScript"]) == 2
    assert any("压缩" in note or "condensed" in note for note in script.coverage_notes)


@pytest.mark.asyncio
async def test_podcast_script_succeeds_without_tts(tmp_path):
    service = PodcastService(PodcastLLM(), tts_provider=None, output_dir=str(tmp_path))
    result = await service.generate_from_text("source", duration_range=DurationRange.SHORT)

    assert result["audio_status"]["status"] == "skipped"
    assert result["audio_filename"] is None
    assert Path(result["transcript_path"]).exists()
    assert result["transcript"].startswith("# Podcast")


@pytest.mark.asyncio
async def test_podcast_audio_success_and_failure_preserve_script(tmp_path):
    ok = PodcastService(PodcastLLM(), tts_provider=FakeAudio(), output_dir=str(tmp_path / "ok"))
    ok_result = await ok.generate_from_text("source", duration_range=DurationRange.SHORT)

    broken = PodcastService(PodcastLLM(), tts_provider=BrokenAudio(), output_dir=str(tmp_path / "broken"))
    broken_result = await broken.generate_from_text("source", duration_range=DurationRange.SHORT)

    assert ok_result["audio_status"]["status"] == "succeeded"
    assert Path(ok_result["audio_path"]).read_bytes() == b"mp3"
    assert broken_result["audio_status"]["status"] == "failed"
    assert "tts failed" in broken_result["audio_status"]["error"]
    assert broken_result["transcript"].startswith("# Podcast")


def test_podcast_api_persists_generated_script_as_artifact(tmp_path):
    repo = InMemoryKnowledgeRepository()
    settings = Settings(output_dir=str(tmp_path / "output"))

    app = FastAPI()
    app.include_router(podcast_router, prefix="/api")
    app.dependency_overrides[get_vector_store] = lambda: EmptyVectorStore()
    app.dependency_overrides[get_source_service] = lambda: FakeSourceService()
    app.dependency_overrides[get_audio_speech_provider] = lambda: FakeAudio()
    app.dependency_overrides[get_podcast_llm_factory] = lambda: (lambda **kwargs: PodcastLLM())

    # Override by function object used in the route imports.
    from backend.config import get_settings
    from backend.dependencies import get_knowledge_repository

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_knowledge_repository] = lambda: repo

    client = TestClient(app)

    response = client.post(
        "/api/podcast/generate",
        json={"source_ids": ["src-1"], "duration_range": "3-5"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["artifact_id"]
    assert payload["title"] == "Podcast"
    assert payload["speakers"] == ["主持人", "嘉宾"]
    assert payload["turns"][0] == {"speaker": "主持人", "text": PodcastLLM().turn_text}
    artifact = repo.artifacts[payload["artifact_id"]]
    assert artifact.artifact_type.value == "podcast_script"
    assert artifact.source_ids == ["src-1"]
    assert artifact.payload["speakers"] == ["主持人", "嘉宾"]
    assert artifact.payload["turns"][0] == {"speaker": "主持人", "text": PodcastLLM().turn_text}
    assert artifact.payload["estimated_duration_minutes"] == payload["duration_minutes"]
    assert artifact.payload["audio_url"] == payload["audio_url"]
    assert artifact.payload["transcript_url"] == payload["transcript_url"]
    assert artifact.markdown.startswith("# Podcast")
