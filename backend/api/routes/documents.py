"""
Document Routes

Handles document upload, retrieval, and deletion.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from typing import List
import os
import shutil
import uuid

from ..schemas.document import (
    DocumentUploadResponse,
    DocumentListResponse,
    DocumentInfo,
    DocumentDeleteResponse
)
from ...config import get_settings, Settings
from ...dependencies import get_vector_store
from ...core.services.document_service import DocumentService
from ...core.interfaces.vector_store import VectorStoreInterface

router = APIRouter(prefix="/documents", tags=["Documents"])

# 存储已处理的文档信息
_documents_cache = {}


def get_document_service(
    vector_store: VectorStoreInterface = Depends(get_vector_store),
    settings: Settings = Depends(get_settings)
) -> DocumentService:
    return DocumentService(
        vector_store=vector_store,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap
    )


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    enable_chunking: bool = True,
    settings: Settings = Depends(get_settings),
    doc_service: DocumentService = Depends(get_document_service)
):
    """上传并处理文档"""
    # 检查文件类型
    from ...infrastructure.parsers.parser_factory import ParserFactory
    ext = os.path.splitext(file.filename)[1]
    if not ParserFactory.is_supported(ext):
        supported = ", ".join(ParserFactory.supported_extensions())
        raise HTTPException(
            status_code=400, 
            detail=f"不支持的文件类型。支持: {supported}"
        )
    
    # 保存文件
    os.makedirs(settings.upload_dir, exist_ok=True)
    file_id = str(uuid.uuid4())
    file_path = os.path.join(settings.upload_dir, f"{file_id}_{file.filename}")
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 处理文档
        document = await doc_service.process_document(
            file_path=file_path,
            filename=file.filename,
            enable_chunking=enable_chunking
        )
        
        # 缓存文档信息
        _documents_cache[document.id] = {
            "filename": document.filename,
            "doc_type": document.doc_type.value,
            "chunk_count": document.chunk_count,
            "char_count": document.char_count,
            "full_text": document.full_text,
            "created_at": document.created_at
        }
        
        return DocumentUploadResponse(
            id=document.id,
            filename=document.filename,
            doc_type=document.doc_type.value,
            chunk_count=document.chunk_count,
            char_count=document.char_count
        )
        
    except Exception as e:
        # 清理文件
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=DocumentListResponse)
async def list_documents():
    """获取文档列表"""
    documents = [
        DocumentInfo(
            id=doc_id,
            filename=info["filename"],
            doc_type=info["doc_type"],
            chunk_count=info["chunk_count"],
            created_at=info.get("created_at")
        )
        for doc_id, info in _documents_cache.items()
    ]
    return DocumentListResponse(documents=documents, total=len(documents))


@router.get("/{doc_id}/text")
async def get_document_text(
    doc_id: str,
    doc_service: DocumentService = Depends(get_document_service)
):
    """获取文档文本"""
    if doc_id not in _documents_cache:
        raise HTTPException(status_code=404, detail="文档不存在")
    
    text = await doc_service.get_document_text(doc_id)
    return {"id": doc_id, "text": text}


@router.delete("/{doc_id}", response_model=DocumentDeleteResponse)
async def delete_document(
    doc_id: str,
    doc_service: DocumentService = Depends(get_document_service)
):
    """删除文档"""
    if doc_id not in _documents_cache:
        raise HTTPException(status_code=404, detail="文档不存在")
    
    success = await doc_service.delete_document(doc_id)
    
    if success:
        del _documents_cache[doc_id]
        return DocumentDeleteResponse(success=True, message="删除成功")
    
    return DocumentDeleteResponse(success=False, message="删除失败")
