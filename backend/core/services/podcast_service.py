"""
Podcast Service

Orchestrates podcast generation including script generation and audio synthesis.
"""
from typing import Optional, Dict, Any
import os
import uuid

from ..interfaces.llm_provider import LLMProviderInterface
from ..interfaces.tts_provider import TTSProviderInterface
from ..interfaces.vector_store import VectorStoreInterface
from ..workflows.podcast_workflow import PodcastWorkflow
from ...domain.podcast import DurationRange, PodcastScript


class PodcastService:
    """播客生成服务"""
    
    # 默认音色映射
    DEFAULT_VOICE_MAPPING = {
        "主持人": "alloy",
        "嘉宾": "nova"
    }
    
    def __init__(
        self,
        llm_provider: LLMProviderInterface,
        tts_provider: Optional[TTSProviderInterface],
        vector_store: Optional[VectorStoreInterface] = None,
        output_dir: str = "./output"
    ):
        """
        初始化播客服务
        
        Args:
            llm_provider: LLM 提供商
            tts_provider: TTS 提供商
            vector_store: 可选的向量存储（用于从文档获取文本）
            output_dir: 音频输出目录
        """
        self.llm = llm_provider
        self.tts = tts_provider
        self.vector_store = vector_store
        self.output_dir = output_dir
        
        os.makedirs(output_dir, exist_ok=True)
        
        # 初始化工作流
        self.workflow = PodcastWorkflow(llm_provider)
    
    async def generate_from_text(
        self,
        source_text: str,
        duration_range: DurationRange = DurationRange.SHORT,
        prompt_type: str = "default",
        voice_mapping: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        从文本生成播客
        
        Args:
            source_text: 源文本
            duration_range: 时长范围
            prompt_type: 提示类型
            voice_mapping: 音色映射
            
        Returns:
            包含 audio_path, transcript, script 的字典
        """
        # 1. 生成脚本
        script = await self.workflow.generate(
            source_text=source_text,
            duration_range=duration_range,
            prompt_type=prompt_type
        )
        
        transcript = script.to_transcript()
        filename = f"{uuid.uuid4()}.mp3"
        audio_path = os.path.join(self.output_dir, filename)
        transcript_filename = f"{uuid.uuid4()}.md"
        transcript_path = os.path.join(self.output_dir, transcript_filename)
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write(transcript)
        audio_status = {"status": "skipped", "error": "TTS provider is not configured"}

        if self.tts:
            try:
                if hasattr(self.tts, "synthesize"):
                    audio_status = await self.tts.synthesize(transcript, audio_path)
                else:
                    voices = voice_mapping or self.DEFAULT_VOICE_MAPPING
                    dialogues = [{"speaker": d.speaker, "text": d.text} for d in script.dialogues]
                    audio_data = await self.tts.synthesize_dialogue(
                        dialogues=dialogues,
                        voice_mapping=voices
                    )
                    with open(audio_path, "wb") as f:
                        f.write(audio_data)
                    audio_status = {"status": "succeeded", "path": audio_path}
            except Exception as exc:
                audio_status = {"status": "failed", "error": str(exc)}
        
        return {
            "audio_path": audio_path if audio_status.get("status") == "succeeded" else None,
            "audio_filename": filename if audio_status.get("status") == "succeeded" else None,
            "audio_status": audio_status,
            "transcript": transcript,
            "transcript_path": transcript_path,
            "transcript_filename": transcript_filename,
            "script": script,
            "duration_minutes": script.estimated_duration_minutes,
            "dialogue_count": script.dialogue_count
        }
    
    async def generate_from_documents(
        self,
        doc_ids: list,
        duration_range: DurationRange = DurationRange.SHORT,
        prompt_type: str = "default",
        voice_mapping: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        从已上传的文档生成播客
        
        Args:
            doc_ids: 文档 ID 列表
            duration_range: 时长范围
            prompt_type: 提示类型
            voice_mapping: 音色映射
            
        Returns:
            生成结果
        """
        if not self.vector_store:
            raise ValueError("Vector store not configured for document retrieval")
        
        # 获取所有文档的文本
        all_text = []
        for doc_id in doc_ids:
            chunks = await self.vector_store.get_document_chunks(doc_id)
            chunks.sort(key=lambda x: x.get("metadata", {}).get("chunk_index", 0))
            text = "\n\n".join([c.get("content", "") for c in chunks])
            all_text.append(text)
        
        combined_text = "\n\n---\n\n".join(all_text)
        
        return await self.generate_from_text(
            source_text=combined_text,
            duration_range=duration_range,
            prompt_type=prompt_type,
            voice_mapping=voice_mapping
        )
    
    async def generate_script_only(
        self,
        source_text: str,
        duration_range: DurationRange = DurationRange.SHORT,
        prompt_type: str = "default"
    ) -> PodcastScript:
        """
        仅生成脚本（不合成音频）
        
        Args:
            source_text: 源文本
            duration_range: 时长范围
            prompt_type: 提示类型
            
        Returns:
            播客脚本
        """
        return await self.workflow.generate(
            source_text=source_text,
            duration_range=duration_range,
            prompt_type=prompt_type
        )
