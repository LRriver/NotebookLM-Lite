"""
Document Domain Models

Core data structures for document processing and storage.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class DocumentType(str, Enum):
    """文档类型"""
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MARKDOWN = "md"
    HTML = "html"


class DocumentChunk(BaseModel):
    """文档块模型"""
    id: str = Field(..., description="块唯一标识")
    doc_id: str = Field(..., description="所属文档ID")
    content: str = Field(..., description="块文本内容")
    chunk_index: int = Field(..., description="块在文档中的序号")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    embedding: Optional[List[float]] = Field(None, description="向量嵌入")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "doc123_chunk_0",
                "doc_id": "doc123",
                "content": "这是文档的第一段内容...",
                "chunk_index": 0,
                "metadata": {"page": 1, "source": "intro"}
            }
        }


class ProcessedDocument(BaseModel):
    """处理后的文档模型"""
    id: str = Field(..., description="文档唯一标识")
    filename: str = Field(..., description="原始文件名")
    doc_type: DocumentType = Field(..., description="文档类型")
    full_text: str = Field(..., description="完整文本内容")
    chunks: List[DocumentChunk] = Field(default_factory=list, description="分块列表")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="文档元数据")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    
    @property
    def chunk_count(self) -> int:
        """块数量"""
        return len(self.chunks)
    
    @property
    def char_count(self) -> int:
        """总字符数"""
        return len(self.full_text)
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "doc123",
                "filename": "research_paper.pdf",
                "doc_type": "pdf",
                "full_text": "完整文档内容...",
                "chunks": [],
                "metadata": {"author": "张三", "pages": 10}
            }
        }
