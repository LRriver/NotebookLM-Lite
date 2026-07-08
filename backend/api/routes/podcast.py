"""
Podcast Routes

Handles podcast generation with controllable duration.
"""
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
import os

from ..schemas.podcast import (
    PodcastGenerateRequest,
    PodcastGenerateResponse,
    PodcastScriptRequest,
    PodcastScriptResponse
)
from ...config import get_settings, Settings
from ...dependencies import (
    get_audio_speech_provider,
    get_knowledge_repository,
    get_llm_provider,
    get_source_service,
    get_vector_store,
)
from ...core.services.podcast_service import PodcastService
from ...core.interfaces.vector_store import VectorStoreInterface
from ...core.services.source_service import SourceService
from ...core.interfaces.knowledge_repository import KnowledgeRepositoryInterface
from ...domain.source import Artifact, ArtifactType, JobStatus

router = APIRouter(prefix="/podcast", tags=["Podcast"])


def get_podcast_llm_factory() -> Callable:
    return get_llm_provider


@router.post("/generate", response_model=PodcastGenerateResponse)
async def generate_podcast(
    request: PodcastGenerateRequest,
    settings: Settings = Depends(get_settings),
    vector_store: VectorStoreInterface = Depends(get_vector_store),
    source_service: SourceService = Depends(get_source_service),
    repository: KnowledgeRepositoryInterface = Depends(get_knowledge_repository),
    llm_factory: Callable = Depends(get_podcast_llm_factory),
    tts = Depends(get_audio_speech_provider),
):
    """生成播客（脚本 + 音频）"""
    try:
        # 获取 LLM 提供商
        llm = llm_factory(
            provider=request.llm_provider,
            api_key=request.llm_api_key,
            base_url=request.llm_base_url,
            model=request.llm_model
        )
        
        # 创建播客服务
        podcast_service = PodcastService(
            llm_provider=llm,
            tts_provider=tts,
            vector_store=vector_store,
            output_dir=settings.output_dir
        )
        
        # 准备音色映射
        voice_mapping = {
            "主持人": request.host_voice,
            "嘉宾": request.guest_voice
        }
        
        # 生成播客
        if request.source_text:
            result = await podcast_service.generate_from_text(
                source_text=request.source_text,
                duration_range=request.duration_range,
                prompt_type=request.prompt_type,
                voice_mapping=voice_mapping
            )
        elif request.source_ids:
            texts = [await source_service.get_source_text(source_id) for source_id in request.source_ids]
            result = await podcast_service.generate_from_text(
                source_text="\n\n---\n\n".join(texts),
                duration_range=request.duration_range,
                prompt_type=request.prompt_type,
                voice_mapping=voice_mapping
            )
        elif request.document_ids:
            result = await podcast_service.generate_from_documents(
                doc_ids=request.document_ids,
                duration_range=request.duration_range,
                prompt_type=request.prompt_type,
                voice_mapping=voice_mapping
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="请提供 source_text 或 document_ids"
            )
        
        audio_url = f"/api/podcast/download/{result['audio_filename']}" if result.get("audio_filename") else None
        transcript_url = f"/api/podcast/download/{result['transcript_filename']}"
        script = result["script"]
        turns = [{"speaker": turn.speaker, "text": turn.text} for turn in script.dialogues]
        speakers = list(dict.fromkeys([script.host_name, script.guest_name]))
        artifact = Artifact(
            artifact_type=ArtifactType.PODCAST_SCRIPT,
            title=getattr(script, "title", None) or "Podcast Script",
            source_ids=request.source_ids or request.document_ids,
            markdown=result["transcript"],
            payload={
                "title": getattr(script, "title", "Podcast Script"),
                "speakers": speakers,
                "turns": turns,
                "estimated_duration_minutes": result["duration_minutes"],
                "transcript": result["transcript"],
                "duration_minutes": result["duration_minutes"],
                "dialogue_count": result["dialogue_count"],
                "audio_url": audio_url,
                "audio_status": result.get("audio_status", {}),
                "audio_filename": result.get("audio_filename"),
                "transcript_url": transcript_url,
                "transcript_filename": result.get("transcript_filename"),
            },
            file_refs=[
                {
                    "format": "markdown",
                    "mime_type": "text/markdown",
                    "name": result.get("transcript_filename"),
                    "url": transcript_url,
                }
            ],
            status=JobStatus.SUCCEEDED,
        )
        if audio_url:
            artifact.file_refs.append(
                {
                    "format": "mp3",
                    "mime_type": "audio/mpeg",
                    "name": result.get("audio_filename"),
                    "url": audio_url,
                }
            )
        artifact = await repository.save_artifact(artifact)

        return PodcastGenerateResponse(
            artifact_id=artifact.id,
            title=artifact.title,
            speakers=speakers,
            turns=turns,
            audio_url=audio_url,
            audio_status=result.get("audio_status", {}),
            audio_filename=result.get("audio_filename"),
            transcript_url=transcript_url,
            transcript_filename=result.get("transcript_filename"),
            transcript=result["transcript"],
            duration_minutes=result["duration_minutes"],
            dialogue_count=result["dialogue_count"]
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/script", response_model=PodcastScriptResponse)
async def generate_script_only(
    request: PodcastScriptRequest,
    vector_store: VectorStoreInterface = Depends(get_vector_store),
    source_service: SourceService = Depends(get_source_service),
    llm_factory: Callable = Depends(get_podcast_llm_factory),
):
    """仅生成播客脚本（不合成音频）"""
    try:
        llm = llm_factory(
            provider=request.llm_provider,
            api_key=request.llm_api_key,
            base_url=request.llm_base_url,
            model=request.llm_model
        )
        
        podcast_service = PodcastService(
            llm_provider=llm,
            tts_provider=None,  # 不需要 TTS
            vector_store=vector_store
        )
        
        # 获取源文本
        if request.source_text:
            source_text = request.source_text
        elif request.source_ids:
            texts = [await source_service.get_source_text(source_id) for source_id in request.source_ids]
            source_text = "\n\n---\n\n".join(texts)
        elif request.document_ids:
            # 从文档获取文本
            all_text = []
            for doc_id in request.document_ids:
                chunks = await vector_store.get_document_chunks(doc_id)
                chunks.sort(key=lambda x: x.get("metadata", {}).get("chunk_index", 0))
                text = "\n\n".join([c.get("content", "") for c in chunks])
                all_text.append(text)
            source_text = "\n\n---\n\n".join(all_text)
        else:
            raise HTTPException(status_code=400, detail="请提供文本或文档")
        
        # 生成脚本
        script = await podcast_service.generate_script_only(
            source_text=source_text,
            duration_range=request.duration_range,
            prompt_type=request.prompt_type
        )
        
        return PodcastScriptResponse(
            title=script.title,
            host_name=script.host_name,
            guest_name=script.guest_name,
            dialogues=[{"speaker": d.speaker, "text": d.text} for d in script.dialogues],
            duration_minutes=script.estimated_duration_minutes,
            transcript=script.to_transcript(),
            coverage_notes=script.coverage_notes,
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/{filename}")
async def download_audio(
    filename: str,
    settings: Settings = Depends(get_settings)
):
    """下载生成的音频文件"""
    file_path = os.path.join(settings.output_dir, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    
    media_type = "audio/mpeg" if filename.endswith(".mp3") else "text/markdown"
    return FileResponse(file_path, media_type=media_type, filename=filename)
