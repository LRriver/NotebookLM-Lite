# API Schemas
from .document import (
    DocumentUploadResponse,
    DocumentListResponse,
    DocumentDetailResponse
)
from .chat import ChatRequest, ChatResponse
from .podcast import PodcastGenerateRequest, PodcastGenerateResponse

__all__ = [
    "DocumentUploadResponse",
    "DocumentListResponse", 
    "DocumentDetailResponse",
    "ChatRequest",
    "ChatResponse",
    "PodcastGenerateRequest",
    "PodcastGenerateResponse",
]
