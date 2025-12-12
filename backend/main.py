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
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .api.routes import documents_router, chat_router, podcast_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    settings = get_settings()
    
    # 确保目录存在
    os.makedirs(settings.upload_dir, exist_ok=True)
    os.makedirs(settings.output_dir, exist_ok=True)
    os.makedirs(settings.chroma_persist_dir, exist_ok=True)
    
    yield


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
app.include_router(chat_router, prefix="/api")
app.include_router(podcast_router, prefix="/api")


# 健康检查
@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": settings.app_version}


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
