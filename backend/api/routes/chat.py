"""
Chat Routes

Handles RAG-based Q&A with documents.
"""
from fastapi import APIRouter, Depends, HTTPException

from ..schemas.chat import ChatRequest, ChatResponse, ChatSource
from ...dependencies import get_vector_store, get_llm_provider
from ...core.services.rag_service import RAGService
from ...core.interfaces.vector_store import VectorStoreInterface

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("/", response_model=ChatResponse)
async def chat_with_documents(
    request: ChatRequest,
    vector_store: VectorStoreInterface = Depends(get_vector_store)
):
    """基于文档的问答"""
    try:
        # 获取 LLM 提供商
        llm = get_llm_provider(
            provider=request.llm_provider,
            api_key=request.llm_api_key,
            base_url=request.llm_base_url,
            model=request.llm_model
        )
        
        # 创建 RAG 服务
        rag_service = RAGService(
            vector_store=vector_store,
            llm_provider=llm
        )
        
        # 执行查询
        if request.history:
            result = await rag_service.multi_turn_query(
                question=request.query,
                history=request.history,
                doc_ids=request.document_ids if request.document_ids else None
            )
        else:
            result = await rag_service.query(
                question=request.query,
                doc_ids=request.document_ids if request.document_ids else None
            )
        
        # 格式化响应
        sources = [
            ChatSource(
                content=s.get("content", ""),
                score=s.get("score", 0),
                metadata=s.get("metadata", {})
            )
            for s in result.get("sources", [])
        ]
        
        return ChatResponse(
            answer=result["answer"],
            sources=sources
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
