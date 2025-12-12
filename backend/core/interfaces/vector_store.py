"""
Vector Store Interface

Abstract interface for vector database operations.
Supports ChromaDB implementation with extensibility to FAISS, Pinecone, etc.
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any


class VectorStoreInterface(ABC):
    """向量存储抽象接口 - 支持未来扩展到其他数据库"""
    
    @abstractmethod
    async def add_chunks(
        self, 
        doc_id: str, 
        chunks: List[Dict[str, Any]],
        embeddings: Optional[List[List[float]]] = None
    ) -> None:
        """
        添加文档块到向量存储
        
        Args:
            doc_id: 文档唯一标识
            chunks: 文档块列表，每个块包含 content, metadata
            embeddings: 可选的预计算向量，如未提供则自动生成
        """
        pass
    
    @abstractmethod
    async def search(
        self, 
        query: str, 
        top_k: int = 5, 
        doc_ids: Optional[List[str]] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        语义搜索相关文档块
        
        Args:
            query: 查询文本
            top_k: 返回最相关的K个结果
            doc_ids: 可选，限制搜索范围到指定文档
            
        Returns:
            匹配的文档块列表，包含 id, content, metadata, score
        """
        pass
    
    @abstractmethod
    async def delete_document(self, doc_id: str) -> bool:
        """
        删除文档的所有向量
        
        Args:
            doc_id: 文档唯一标识
            
        Returns:
            删除是否成功
        """
        pass
    
    @abstractmethod
    async def get_document_chunks(self, doc_id: str) -> List[Dict[str, Any]]:
        """
        获取文档的所有块
        
        Args:
            doc_id: 文档唯一标识
            
        Returns:
            文档的所有块列表
        """
        pass
    
    @abstractmethod
    async def get_stats(self) -> Dict[str, Any]:
        """
        获取向量存储统计信息
        
        Returns:
            包含文档数量、块数量等统计信息
        """
        pass
