"""
RAG Service

Retrieval-Augmented Generation for document Q&A.
"""
from typing import List, Optional, Dict, Any

from ..interfaces.vector_store import VectorStoreInterface
from ..interfaces.llm_provider import LLMProviderInterface


class RAGService:
    """RAG 问答服务"""
    
    def __init__(
        self,
        vector_store: VectorStoreInterface,
        llm_provider: LLMProviderInterface,
        top_k: int = 5
    ):
        """
        初始化 RAG 服务
        
        Args:
            vector_store: 向量存储
            llm_provider: LLM 提供商
            top_k: 检索的文档数量
        """
        self.vector_store = vector_store
        self.llm = llm_provider
        self.top_k = top_k
    
    async def query(
        self,
        question: str,
        doc_ids: Optional[List[str]] = None,
        top_k: Optional[int] = None,
        include_sources: bool = True
    ) -> Dict[str, Any]:
        """
        基于文档的问答
        
        Args:
            question: 用户问题
            doc_ids: 限制搜索的文档 ID 列表
            top_k: 检索数量
            include_sources: 是否返回来源信息
            
        Returns:
            包含 answer 和可选 sources 的字典
        """
        k = top_k or self.top_k
        
        # 1. 检索相关文档块
        results = await self.vector_store.search(
            query=question,
            top_k=k,
            doc_ids=doc_ids
        )
        
        if not results:
            return {
                "answer": "抱歉，在已上传的文档中没有找到相关信息。请确保已上传相关文档。",
                "sources": []
            }
        
        # 2. 构建上下文
        context = [r.get("content", "") for r in results]
        
        # 3. 使用 LLM 生成回答
        answer = await self.llm.generate_with_context(
            query=question,
            context=context
        )
        
        # 4. 准备响应
        response = {"answer": answer}
        
        if include_sources:
            sources = []
            for r in results:
                sources.append({
                    "content": r.get("content", "")[:200] + "...",
                    "score": r.get("score", 0),
                    "metadata": r.get("metadata", {})
                })
            response["sources"] = sources
        
        return response
    
    async def multi_turn_query(
        self,
        question: str,
        history: List[Dict[str, str]],
        doc_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        多轮对话问答
        
        Args:
            question: 当前问题
            history: 对话历史 [{"role": "user/assistant", "content": "..."}]
            doc_ids: 文档 ID 列表
            
        Returns:
            回答和来源
        """
        # 构建包含历史的查询
        context_query = question
        if history:
            recent = history[-4:]  # 最近2轮对话
            history_text = "\n".join([
                f"{'用户' if h['role'] == 'user' else '助手'}: {h['content']}"
                for h in recent
            ])
            context_query = f"对话历史:\n{history_text}\n\n当前问题: {question}"
        
        return await self.query(
            question=context_query,
            doc_ids=doc_ids,
            include_sources=True
        )
