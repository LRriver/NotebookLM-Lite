"""
RAG Service

Retrieval-Augmented Generation for document Q&A.
"""
from typing import AsyncIterator, List, Optional, Dict, Any

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
        source_ids: Optional[List[str]] = None,
        top_k: Optional[int] = None,
        include_sources: bool = True,
        retrieval_query: Optional[str] = None,
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
        search_query = retrieval_query or question
        results = await self._retrieve_results(
            question=question,
            doc_ids=doc_ids,
            source_ids=source_ids,
            top_k=k,
            retrieval_query=search_query,
        )
        
        if not results:
            return {
                "answer": "抱歉，在已上传的文档中没有找到相关信息。请确保已上传相关文档。",
                "sources": [],
                "citations": [],
            }
        
        # 2. 构建上下文
        context = [self._format_context_item(r) for r in results]
        
        # 3. 使用 LLM 生成回答
        answer = await self.llm.generate_with_context(
            query=question,
            context=context
        )
        
        response = {"answer": answer}
        
        if include_sources:
            sources, citations = self._sources_and_citations(results)
            response["sources"] = sources
            response["citations"] = citations
        
        return response

    async def stream_query(
        self,
        question: str,
        doc_ids: Optional[List[str]] = None,
        source_ids: Optional[List[str]] = None,
        top_k: Optional[int] = None,
        retrieval_query: Optional[str] = None,
    ) -> AsyncIterator[dict[str, Any]]:
        results = await self._retrieve_results(
            question=question,
            doc_ids=doc_ids,
            source_ids=source_ids,
            top_k=top_k or self.top_k,
            retrieval_query=retrieval_query or question,
        )
        if not results and retrieval_query and retrieval_query != question:
            results = await self._retrieve_results(
                question=question,
                doc_ids=doc_ids,
                source_ids=source_ids,
                top_k=top_k or self.top_k,
                retrieval_query=question,
            )
        if not results:
            answer = "抱歉，在已上传的文档中没有找到相关信息。请确保已上传相关文档。"
            yield {"event": "delta", "content": answer}
            yield {"event": "final", "answer": answer, "sources": [], "citations": []}
            return

        context = [self._format_context_item(r) for r in results]
        answer_parts: list[str] = []
        stream_method = getattr(self.llm, "stream_generate_with_context", None)
        if stream_method is not None:
            async for token in stream_method(query=question, context=context):
                if not token:
                    continue
                answer_parts.append(token)
                yield {"event": "delta", "content": token}
        else:
            answer = await self.llm.generate_with_context(query=question, context=context)
            for token in self._chunk_answer(answer):
                answer_parts.append(token)
                yield {"event": "delta", "content": token}

        sources, citations = self._sources_and_citations(results)
        yield {"event": "final", "answer": "".join(answer_parts), "sources": sources, "citations": citations}

    async def _retrieve_results(
        self,
        question: str,
        doc_ids: Optional[List[str]],
        source_ids: Optional[List[str]],
        top_k: int,
        retrieval_query: str,
    ) -> list[dict[str, Any]]:
        selected_ids = source_ids if source_ids is not None else doc_ids
        if selected_ids and self._looks_like_source_overview_question(question, len(selected_ids)):
            return await self._overview_results(selected_ids, top_k)

        results = await self.vector_store.search(
            query=retrieval_query,
            top_k=top_k,
            doc_ids=selected_ids,
        )
        if selected_ids and len(selected_ids) > 1:
            results = await self._balance_results_across_sources(
                results=results,
                query=retrieval_query,
                source_ids=selected_ids,
            )
        return results

    @staticmethod
    def _sources_and_citations(results: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        sources = []
        citations = []
        for r in results:
            metadata = r.get("metadata", {})
            excerpt = r.get("content", "")
            sources.append({
                "content": excerpt[:200] + ("..." if len(excerpt) > 200 else ""),
                "score": r.get("score", 0),
                "metadata": metadata
            })
            citations.append({
                "source_id": metadata.get("source_id", metadata.get("doc_id", "")),
                "source_title": metadata.get("source_title") or metadata.get("filename") or "",
                "chunk_id": r.get("id", ""),
                "score": r.get("score", 0),
                "excerpt": excerpt[:300],
                "metadata": metadata,
            })
        return sources, citations

    @staticmethod
    def _chunk_answer(answer: str, size: int = 80) -> list[str]:
        return [answer[index:index + size] for index in range(0, len(answer), size)] or [""]

    async def _overview_results(self, source_ids: list[str], top_k: int) -> list[dict[str, Any]]:
        chunks_by_source: list[list[dict[str, Any]]] = []
        for source_id in source_ids:
            chunks = await self.vector_store.get_document_chunks(source_id)
            if chunks:
                chunks_by_source.append(chunks)

        target_count = max(top_k, len(chunks_by_source))
        results: list[dict[str, Any]] = []
        chunk_index = 0
        while len(results) < target_count:
            added = False
            for chunks in chunks_by_source:
                if chunk_index < len(chunks):
                    results.append(chunks[chunk_index])
                    added = True
                    if len(results) >= target_count:
                        break
            if not added:
                break
            chunk_index += 1
        return results

    async def _balance_results_across_sources(
        self,
        results: list[dict[str, Any]],
        query: str,
        source_ids: list[str],
    ) -> list[dict[str, Any]]:
        present = {
            result.get("metadata", {}).get("source_id") or result.get("metadata", {}).get("doc_id")
            for result in results
        }
        missing = [source_id for source_id in source_ids if source_id not in present]
        if not missing:
            return results

        seen_chunk_ids = {result.get("id") for result in results}
        balanced = list(results)
        for source_id in missing:
            supplemental = await self.vector_store.search(query=query, top_k=1, doc_ids=[source_id])
            for item in supplemental:
                if item.get("id") not in seen_chunk_ids:
                    balanced.append(item)
                    seen_chunk_ids.add(item.get("id"))
                    break
        return balanced

    @staticmethod
    def _looks_like_source_overview_question(question: str, source_count: int = 1) -> bool:
        normalized = question.lower()
        multi_source_terms = (
            "分别",
            "这两个文件",
            "这些文件",
            "这些文档",
            "each file",
            "each document",
            "compare these files",
        )
        source_reference_terms = (
            "这个文件",
            "这份文件",
            "这篇文档",
            "这份文档",
            "这些文件",
            "这些文档",
            "file",
            "document",
        )
        generic_overview_terms = (
            "讲了什么",
            "主要内容",
            "overview",
            "summarize",
            "summary",
        )
        if source_count > 1 and any(term in normalized for term in multi_source_terms):
            return True
        return (
            any(term in normalized for term in source_reference_terms)
            and any(term in normalized for term in generic_overview_terms)
        )

    @staticmethod
    def _format_context_item(result: dict[str, Any]) -> str:
        metadata = result.get("metadata", {})
        title = metadata.get("source_title") or metadata.get("filename") or metadata.get("source_id") or "unknown"
        source_id = metadata.get("source_id") or metadata.get("doc_id") or ""
        chunk_index = metadata.get("chunk_index", "")
        content = result.get("content", "")
        return f"Source: {title}\nSource ID: {source_id}\nChunk: {chunk_index}\nContent:\n{content}"
    
    async def multi_turn_query(
        self,
        question: str,
        history: List[Dict[str, str]],
        doc_ids: Optional[List[str]] = None,
        source_ids: Optional[List[str]] = None,
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
        retrieval_question = question
        if history:
            recent = history[-4:]
            history_text = "\n".join([
                f"{'用户' if h['role'] == 'user' else '助手'}: {h['content']}"
                for h in recent
            ])
            try:
                retrieval_question = await self.llm.generate(
                    prompt=(
                        "Rewrite the current question as a standalone retrieval query. "
                        "Return only the query.\n\n"
                        f"History:\n{history_text}\n\nCurrent question: {question}"
                    ),
                    temperature=0,
                    max_tokens=256,
                )
            except Exception:
                retrieval_question = question

        scoped = await self.query(
            question=question,
            doc_ids=doc_ids,
            source_ids=source_ids,
            include_sources=True,
            retrieval_query=retrieval_question,
        )
        if scoped.get("citations"):
            return scoped

        # Keep retrieval within selected sources, but fall back to the original
        # question if a contextualizer produced terms that miss the index.
        return await self.query(
            question=question,
            doc_ids=doc_ids,
            source_ids=source_ids,
            include_sources=True
        )
