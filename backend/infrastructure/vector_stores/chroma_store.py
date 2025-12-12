"""
ChromaDB Vector Store Implementation

Implements VectorStoreInterface using ChromaDB for persistent vector storage.
"""
from typing import List, Optional, Dict, Any
from ...core.interfaces.vector_store import VectorStoreInterface


class ChromaVectorStore(VectorStoreInterface):
    """ChromaDB 向量存储实现"""
    
    def __init__(
        self, 
        persist_dir: str = "./data/chroma",
        collection_name: str = "documents",
        embedding_model: str = "all-MiniLM-L6-v2"
    ):
        """
        初始化 ChromaDB 存储
        
        Args:
            persist_dir: 持久化目录
            collection_name: 集合名称
            embedding_model: 嵌入模型名称
        """
        import chromadb
        from chromadb.config import Settings
        
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        self.embedding_model_name = embedding_model
        
        # 初始化 ChromaDB 客户端
        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # 获取或创建集合
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        
        # 延迟加载嵌入模型
        self._encoder = None
    
    @property
    def encoder(self):
        """延迟加载嵌入模型"""
        if self._encoder is None:
            from sentence_transformers import SentenceTransformer
            self._encoder = SentenceTransformer(self.embedding_model_name)
        return self._encoder
    
    async def add_chunks(
        self, 
        doc_id: str, 
        chunks: List[Dict[str, Any]],
        embeddings: Optional[List[List[float]]] = None
    ) -> None:
        """添加文档块到向量存储"""
        if not chunks:
            return
        
        # 提取内容
        contents = [c.get("content", "") for c in chunks]
        
        # 生成或使用提供的嵌入
        if embeddings is None:
            embeddings = self.encoder.encode(contents).tolist()
        
        # 准备 ID 和元数据
        ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
        metadatas = []
        for i, chunk in enumerate(chunks):
            meta = chunk.get("metadata", {}).copy()
            meta["doc_id"] = doc_id
            meta["chunk_index"] = i
            metadatas.append(meta)
        
        # 添加到集合
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=contents,
            metadatas=metadatas
        )
    
    async def search(
        self, 
        query: str, 
        top_k: int = 5, 
        doc_ids: Optional[List[str]] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """语义搜索相关文档块"""
        # 生成查询向量
        query_embedding = self.encoder.encode([query]).tolist()
        
        # 构建过滤条件
        where = None
        if doc_ids:
            where = {"doc_id": {"$in": doc_ids}}
        
        # 执行查询
        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"]
        )
        
        # 格式化结果
        output = []
        if results["ids"] and results["ids"][0]:
            for i, id_ in enumerate(results["ids"][0]):
                output.append({
                    "id": id_,
                    "content": results["documents"][0][i] if results["documents"] else "",
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "score": 1 - results["distances"][0][i] if results["distances"] else 0
                })
        
        return output
    
    async def delete_document(self, doc_id: str) -> bool:
        """删除文档的所有向量"""
        try:
            # 获取该文档的所有块 ID
            results = self.collection.get(
                where={"doc_id": doc_id},
                include=[]
            )
            
            if results["ids"]:
                self.collection.delete(ids=results["ids"])
            
            return True
        except Exception:
            return False
    
    async def get_document_chunks(self, doc_id: str) -> List[Dict[str, Any]]:
        """获取文档的所有块"""
        results = self.collection.get(
            where={"doc_id": doc_id},
            include=["documents", "metadatas"]
        )
        
        output = []
        if results["ids"]:
            for i, id_ in enumerate(results["ids"]):
                output.append({
                    "id": id_,
                    "content": results["documents"][i] if results["documents"] else "",
                    "metadata": results["metadatas"][i] if results["metadatas"] else {}
                })
        
        # 按 chunk_index 排序
        output.sort(key=lambda x: x.get("metadata", {}).get("chunk_index", 0))
        return output
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取向量存储统计信息"""
        count = self.collection.count()
        
        # 获取唯一文档数
        all_data = self.collection.get(include=["metadatas"])
        doc_ids = set()
        if all_data["metadatas"]:
            for meta in all_data["metadatas"]:
                if meta and "doc_id" in meta:
                    doc_ids.add(meta["doc_id"])
        
        return {
            "total_chunks": count,
            "total_documents": len(doc_ids),
            "collection_name": self.collection_name,
            "persist_dir": self.persist_dir
        }
