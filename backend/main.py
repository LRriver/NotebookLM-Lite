"""
NotebookLM-Lite Backend

FastAPI application with modular architecture supporting:
- Multi-format document processing (PDF, DOCX, TXT, MD, HTML)
- RAG-based Q&A with vector search
- Controllable podcast generation with structured output
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .api.routes.chat import router as chat_router
from .api.routes.config import router as config_router
from .api.routes.documents import router as documents_router
from .api.routes.artifacts import router as artifacts_router
from .api.routes.podcast import router as podcast_router
from .api.routes.sources import router as sources_router
from .api.routes.notes import router as notes_router
from .api.routes.slide_decks import router as slide_decks_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    settings = get_settings()
    
    # 确保目录存在
    os.makedirs(settings.upload_dir, exist_ok=True)
    os.makedirs(settings.output_dir, exist_ok=True)
    os.makedirs(settings.chroma_persist_dir, exist_ok=True)

    from .dependencies import DependencyContainer

    if settings.vector_store_type == "seekdb":
        repository = DependencyContainer.get_knowledge_repository(settings=settings)
        initialize_storage = getattr(repository, "initialize_storage", None)
        if callable(initialize_storage):
            await initialize_storage()

    try:
        yield
    finally:
        DependencyContainer.reset_runtime_caches()


# 创建应用
settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="NotebookLM-Lite - 多格式文档处理、RAG问答、播客生成",
    lifespan=lifespan
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(documents_router, prefix="/api")
app.include_router(config_router, prefix="/api")
app.include_router(sources_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(artifacts_router, prefix="/api")
app.include_router(podcast_router, prefix="/api")
app.include_router(notes_router, prefix="/api")
app.include_router(slide_decks_router, prefix="/api")


# 健康检查
@app.get("/health")
async def health_check():
    from .dependencies import get_vector_store

    current_settings = get_settings()
    embedding_profile = current_settings.api.models.embedding_model
    embedding_configured = bool(embedding_profile.model and embedding_profile.api_key)
    try:
        vector_store = get_vector_store()
        stats = await vector_store.get_stats()
        storage = stats.get("storage", {})
        native_available = storage.get("native_available", False)
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "version": current_settings.app_version,
                "storage": {
                    "actual_vector_backend": "unavailable",
                    "native_available": False,
                    "embedding_configured": embedding_configured,
                    "error": str(exc),
                },
            },
        )
    strict_seekdb = (
        current_settings.vector_store_type == "seekdb"
        and not current_settings.seekdb_allow_sqlite_fallback
    )
    healthy = not strict_seekdb or (native_available and embedding_configured)
    payload = {
        "status": "healthy" if healthy else "unhealthy",
        "version": current_settings.app_version,
        "storage": {
            "actual_vector_backend": storage.get("vector_backend", stats.get("backend", "unknown")),
            "native_available": native_available,
            "embedding_configured": embedding_configured,
        },
    }
    return JSONResponse(status_code=200 if healthy else 503, content=payload)


# 向量存储统计
@app.get("/api/stats")
async def get_stats():
    from .dependencies import get_vector_store
    vector_store = get_vector_store()
    return await vector_store.get_stats()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
