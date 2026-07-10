"""
Document Routes

Handles document upload, retrieval, and deletion.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
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
from ...dependencies import get_source_service
from ...core.services.source_service import SourceService

router = APIRouter(prefix="/documents", tags=["Documents"])


def _doc_type(filename: str | None) -> str:
    return os.path.splitext(filename or "")[1].lstrip(".").lower() or "txt"


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    enable_chunking: bool = True,
    settings: Settings = Depends(get_settings),
    source_service: SourceService = Depends(get_source_service)
):
    """上传并处理文档"""
    # 保存文件
    os.makedirs(settings.upload_dir, exist_ok=True)
    file_id = str(uuid.uuid4())
    filename = file.filename or "upload"
    file_path = os.path.join(settings.upload_dir, f"{file_id}_{filename}")
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        source = await source_service.create_file_source(
            file_path=file_path,
            filename=filename,
            mime_type=file.content_type,
            metadata={"enable_chunking": enable_chunking},
        )

        if source.status.value == "error":
            raise HTTPException(status_code=400, detail=source.error)
        
        return DocumentUploadResponse(
            id=source.id,
            filename=source.filename or source.title,
            doc_type=_doc_type(source.filename),
            chunk_count=source.chunk_count,
            char_count=source.char_count
        )
        
    except HTTPException:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise
    except Exception as e:
        # 清理文件
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=DocumentListResponse)
async def list_documents(source_service: SourceService = Depends(get_source_service)):
    """获取文档列表"""
    sources = await source_service.list_sources()
    documents = [
        DocumentInfo(
            id=source.id,
            filename=source.filename or source.title,
            doc_type=_doc_type(source.filename),
            chunk_count=source.chunk_count,
            created_at=source.created_at
        )
        for source in sources
        if source.kind.value == "file"
    ]
    return DocumentListResponse(documents=documents, total=len(documents))


@router.get("/{doc_id}/text")
async def get_document_text(
    doc_id: str,
    source_service: SourceService = Depends(get_source_service)
):
    """获取文档文本"""
    source = await source_service.get_source(doc_id)
    if not source:
        raise HTTPException(status_code=404, detail="文档不存在")
    
    return {"id": doc_id, "text": source.text}


@router.delete("/{doc_id}", response_model=DocumentDeleteResponse)
async def delete_document(
    doc_id: str,
    source_service: SourceService = Depends(get_source_service)
):
    """删除文档"""
    if not await source_service.get_source(doc_id):
        raise HTTPException(status_code=404, detail="文档不存在")
    
    success = await source_service.delete_source(doc_id)
    
    if success:
        return DocumentDeleteResponse(success=True, message="删除成功")
    
    return DocumentDeleteResponse(success=False, message="删除失败")
