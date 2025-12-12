"""
Document Service

Handles document upload, parsing, chunking, and storage.
"""
from typing import List, Optional, Dict, Any
import os
import uuid
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ..interfaces.vector_store import VectorStoreInterface
from ..interfaces.document_parser import DocumentParserInterface
from ...domain.document import ProcessedDocument, DocumentChunk, DocumentType
from ...infrastructure.parsers.parser_factory import ParserFactory


class DocumentService:
    """文档处理服务"""
    
    def __init__(
        self,
        vector_store: VectorStoreInterface,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ):
        """
        初始化文档服务
        
        Args:
            vector_store: 向量存储实例
            chunk_size: 分块大小
            chunk_overlap: 分块重叠
        """
        self.vector_store = vector_store
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", "。", "！", "？", "；", " ", ""]
        )
    
    async def process_document(
        self,
        file_path: str,
        filename: str,
        enable_chunking: bool = True
    ) -> ProcessedDocument:
        """
        处理文档：解析、分块、存储向量
        
        Args:
            file_path: 文件路径
            filename: 原始文件名
            enable_chunking: 是否启用分块
            
        Returns:
            处理后的文档对象
        """
        # 1. 获取解析器并解析
        parser = ParserFactory.get_parser_for_file(file_path)
        result = parser.parse_with_metadata(file_path)
        
        full_text = result["content"]
        metadata = result.get("metadata", {})
        
        # 2. 检测文档类型
        ext = os.path.splitext(filename)[1].lstrip('.').lower()
        try:
            doc_type = DocumentType(ext)
        except ValueError:
            doc_type = DocumentType.TXT
        
        # 3. 生成文档 ID
        doc_id = str(uuid.uuid4())
        
        # 4. 分块
        chunks = []
        if enable_chunking and full_text:
            text_chunks = self.text_splitter.split_text(full_text)
            
            for i, chunk_text in enumerate(text_chunks):
                chunk = DocumentChunk(
                    id=f"{doc_id}_chunk_{i}",
                    doc_id=doc_id,
                    content=chunk_text,
                    chunk_index=i,
                    metadata={"filename": filename, **metadata}
                )
                chunks.append(chunk)
        
        # 5. 创建文档对象
        document = ProcessedDocument(
            id=doc_id,
            filename=filename,
            doc_type=doc_type,
            full_text=full_text,
            chunks=chunks,
            metadata=metadata
        )
        
        # 6. 存储到向量数据库
        if chunks:
            chunk_dicts = [
                {"content": c.content, "metadata": c.metadata}
                for c in chunks
            ]
            await self.vector_store.add_chunks(doc_id, chunk_dicts)
        
        return document
    
    async def get_document_text(self, doc_id: str) -> str:
        """获取文档完整文本"""
        chunks = await self.vector_store.get_document_chunks(doc_id)
        # 按 chunk_index 排序并合并
        chunks.sort(key=lambda x: x.get("metadata", {}).get("chunk_index", 0))
        return "\n\n".join([c.get("content", "") for c in chunks])
    
    async def delete_document(self, doc_id: str) -> bool:
        """删除文档"""
        return await self.vector_store.delete_document(doc_id)
    
    async def search(
        self,
        query: str,
        doc_ids: Optional[List[str]] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """搜索相关文档块"""
        return await self.vector_store.search(query, top_k, doc_ids)
