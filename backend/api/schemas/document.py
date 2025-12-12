"""
Document API Schemas
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class DocumentUploadResponse(BaseModel):
    """文档上传响应"""
    id: str = Field(..., description="文档ID")
    filename: str = Field(..., description="文件名")
    doc_type: str = Field(..., description="文档类型")
    chunk_count: int = Field(..., description="分块数量")
    char_count: int = Field(..., description="字符数")
    message: str = Field(default="上传成功")


class DocumentInfo(BaseModel):
    """文档信息"""
    id: str
    filename: str
    doc_type: str
    chunk_count: int
    created_at: Optional[datetime] = None


class DocumentListResponse(BaseModel):
    """文档列表响应"""
    documents: List[DocumentInfo]
    total: int


class DocumentDetailResponse(BaseModel):
    """文档详情响应"""
    id: str
    filename: str
    doc_type: str
    full_text: str
    chunk_count: int
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentDeleteResponse(BaseModel):
    """文档删除响应"""
    success: bool
    message: str
