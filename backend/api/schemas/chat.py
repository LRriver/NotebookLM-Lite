"""
Chat API Schemas
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class ChatRequest(BaseModel):
    """聊天请求"""
    query: str = Field(..., description="用户问题")
    source_ids: List[str] = Field(default_factory=list, description="选中的知识库 source ID 列表")
    document_ids: List[str] = Field(default_factory=list, description="关联的文档ID列表")
    history: List[Dict[str, str]] = Field(default_factory=list, description="对话历史")
    
    # LLM 配置
    llm_provider: str = Field(default="litellm", description="LLM提供商")
    llm_api_key: str = Field(default="", description="API密钥")
    llm_base_url: Optional[str] = Field(None, description="API基础URL")
    llm_model: Optional[str] = Field(None, description="模型名称")


class ChatSource(BaseModel):
    """引用来源"""
    content: str = Field(..., description="引用内容片段")
    score: float = Field(..., description="相关度分数")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChatCitation(BaseModel):
    source_id: str
    source_title: str = ""
    chunk_id: str
    score: float
    excerpt: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    """聊天响应"""
    answer: str = Field(..., description="回答内容")
    sources: List[ChatSource] = Field(default_factory=list, description="引用来源")
    citations: List[ChatCitation] = Field(default_factory=list, description="引用来源")


class SaveAnswerAsSourceRequest(BaseModel):
    title: str = "Saved answer"
    answer: str
    source_ids: List[str] = Field(default_factory=list)
