"""
Chat Routes

Handles RAG-based Q&A with documents.
"""
import json
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from ..schemas.chat import ChatCitation, ChatRequest, ChatResponse, ChatSource, SaveAnswerAsSourceRequest
from ...dependencies import get_source_service, get_vector_store, get_llm_provider
from ...core.services.rag_service import RAGService
from ...core.interfaces.vector_store import VectorStoreInterface
from ...core.services.source_service import SourceService

router = APIRouter(prefix="/chat", tags=["Chat"])


def get_chat_llm_factory() -> Callable:
    return get_llm_provider


@router.post("/", response_model=ChatResponse)
async def chat_with_documents(
    request: ChatRequest,
    vector_store: VectorStoreInterface = Depends(get_vector_store),
    llm_factory: Callable = Depends(get_chat_llm_factory),
):
    """基于文档的问答"""
    try:
        selected_source_ids = request.source_ids or request.document_ids
        if not selected_source_ids:
            raise HTTPException(status_code=400, detail="source_ids is required")

        # 获取 LLM 提供商
        llm = llm_factory(
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
                source_ids=selected_source_ids
            )
        else:
            result = await rag_service.query(
                question=request.query,
                source_ids=selected_source_ids
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
        citations = [
            ChatCitation(
                source_id=s.get("source_id", ""),
                source_title=s.get("source_title", ""),
                chunk_id=s.get("chunk_id", ""),
                score=s.get("score", 0),
                excerpt=s.get("excerpt", ""),
                metadata=s.get("metadata", {}),
            )
            for s in result.get("citations", [])
        ]
        
        return ChatResponse(
            answer=result["answer"],
            sources=sources,
            citations=citations,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def stream_chat_with_documents(
    request: ChatRequest,
    vector_store: VectorStoreInterface = Depends(get_vector_store),
    llm_factory: Callable = Depends(get_chat_llm_factory),
):
    selected_source_ids = request.source_ids or request.document_ids
    if not selected_source_ids:
        raise HTTPException(status_code=400, detail="source_ids is required")

    llm = llm_factory(
        provider=request.llm_provider,
        api_key=request.llm_api_key,
        base_url=request.llm_base_url,
        model=request.llm_model,
    )
    rag_service = RAGService(vector_store=vector_store, llm_provider=llm)

    async def events():
        retrieval_query = None
        if request.history:
            recent = request.history[-4:]
            history_text = "\n".join([
                f"{'用户' if h['role'] == 'user' else '助手'}: {h['content']}"
                for h in recent
            ])
            try:
                retrieval_query = await llm.generate(
                    prompt=(
                        "Rewrite the current question as a standalone retrieval query. "
                        "Return only the query.\n\n"
                        f"History:\n{history_text}\n\nCurrent question: {request.query}"
                    ),
                    temperature=0,
                    max_tokens=256,
                )
            except Exception:
                retrieval_query = request.query

        try:
            async for item in rag_service.stream_query(
                question=request.query,
                source_ids=selected_source_ids,
                retrieval_query=retrieval_query,
            ):
                event = item.pop("event")
                yield f"event: {event}\n"
                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
        except Exception as exc:
            yield "event: error\n"
            yield f"data: {json.dumps({'message': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@router.post("/save-answer")
async def save_answer_as_source(
    request: SaveAnswerAsSourceRequest,
    source_service: SourceService = Depends(get_source_service),
):
    metadata = {"source_ids": request.source_ids, "origin": "chat_answer"}
    source = await source_service.create_text_source(
        title=request.title,
        text=request.answer,
        metadata=metadata,
    )
    return {
        "id": source.id,
        "title": source.title,
        "status": source.status.value,
        "chunk_count": source.chunk_count,
        "char_count": source.char_count,
    }
