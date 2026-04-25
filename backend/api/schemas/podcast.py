"""
Podcast API Schemas
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from ...domain.podcast import DurationRange


class PodcastGenerateRequest(BaseModel):
    """播客生成请求"""
    # 来源
    document_ids: List[str] = Field(default_factory=list, description="文档ID列表")
    source_ids: List[str] = Field(default_factory=list, description="知识库 source ID 列表")
    source_text: Optional[str] = Field(None, description="直接提供的源文本")
    
    # 生成选项
    duration_range: DurationRange = Field(
        default=DurationRange.SHORT, 
        description="时长范围"
    )
    prompt_type: str = Field(default="default", description="提示类型")
    
    # 音色配置
    host_voice: str = Field(default="alloy", description="主持人音色")
    guest_voice: str = Field(default="nova", description="嘉宾音色")
    
    # LLM 配置
    llm_provider: str = Field(default="litellm")
    llm_api_key: str = Field(default="")
    llm_base_url: Optional[str] = None
    llm_model: Optional[str] = None
    
    # TTS 配置
    tts_provider: str = Field(default="openai")
    tts_api_key: Optional[str] = None
    tts_base_url: Optional[str] = Field(None, description="TTS API 基础 URL（用于 OpenAI 兼容接口）")
    tts_model: Optional[str] = Field(None, description="TTS 模型名称")


class PodcastGenerateResponse(BaseModel):
    """播客生成响应"""
    audio_url: Optional[str] = Field(None, description="音频下载URL")
    audio_status: Dict = Field(default_factory=dict, description="音频生成状态")
    audio_filename: Optional[str] = None
    transcript_url: Optional[str] = None
    transcript_filename: Optional[str] = None
    transcript: str = Field(..., description="对话文本")
    duration_minutes: float = Field(..., description="估算时长（分钟）")
    dialogue_count: int = Field(..., description="对话轮数")


class PodcastScriptRequest(BaseModel):
    """仅生成脚本请求"""
    document_ids: List[str] = Field(default_factory=list)
    source_ids: List[str] = Field(default_factory=list)
    source_text: Optional[str] = None
    duration_range: DurationRange = DurationRange.SHORT
    prompt_type: str = "default"
    
    llm_provider: str = "litellm"
    llm_api_key: str = ""
    llm_base_url: Optional[str] = None
    llm_model: Optional[str] = None


class PodcastScriptResponse(BaseModel):
    """脚本响应"""
    title: str
    host_name: str
    guest_name: str
    dialogues: List[Dict[str, str]]
    duration_minutes: float
    transcript: str
    coverage_notes: List[str] = Field(default_factory=list)
