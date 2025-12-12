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
    llm_provider: str = Field(default="openai")
    llm_api_key: str = Field(...)
    llm_base_url: Optional[str] = None
    llm_model: Optional[str] = None
    
    # TTS 配置
    tts_provider: str = Field(default="openai")
    tts_api_key: Optional[str] = None


class PodcastGenerateResponse(BaseModel):
    """播客生成响应"""
    audio_url: str = Field(..., description="音频下载URL")
    transcript: str = Field(..., description="对话文本")
    duration_minutes: float = Field(..., description="估算时长（分钟）")
    dialogue_count: int = Field(..., description="对话轮数")


class PodcastScriptRequest(BaseModel):
    """仅生成脚本请求"""
    document_ids: List[str] = Field(default_factory=list)
    source_text: Optional[str] = None
    duration_range: DurationRange = DurationRange.SHORT
    prompt_type: str = "default"
    
    llm_provider: str = "openai"
    llm_api_key: str
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
