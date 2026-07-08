"""
Dependency Injection Container

Factory methods for creating service instances with proper abstraction.
Enables easy testing and swapping of implementations.
"""
from typing import Any, Optional

from .config import ModelProfile, Settings, get_settings
from .core.interfaces.vector_store import VectorStoreInterface
from .core.interfaces.knowledge_repository import KnowledgeRepositoryInterface
from .core.interfaces.llm_provider import LLMProviderInterface
from .core.interfaces.tts_provider import TTSProviderInterface
from .core.interfaces.document_parser import DocumentParserInterface


class DependencyContainer:
    """依赖注入容器"""
    
    _vector_store: Optional[VectorStoreInterface] = None
    _knowledge_repository: Optional[KnowledgeRepositoryInterface] = None
    _slide_deck_service: Optional[Any] = None

    @classmethod
    def reset_runtime_caches(cls) -> None:
        """Drop cached services that depend on model settings."""

        cls._vector_store = None
        cls._slide_deck_service = None
    
    @classmethod
    def get_vector_store(
        cls, 
        settings: Optional[Settings] = None,
        force_new: bool = False
    ) -> VectorStoreInterface:
        """
        获取向量存储实例（单例模式）
        
        Args:
            settings: 配置对象，默认使用全局配置
            force_new: 是否强制创建新实例
            
        Returns:
            向量存储实例
        """
        if cls._vector_store is None or force_new:
            settings = settings or get_settings()
            
            if settings.vector_store_type == "chroma":
                from .infrastructure.vector_stores.chroma_store import ChromaVectorStore
                cls._vector_store = ChromaVectorStore(
                    persist_dir=settings.chroma_persist_dir,
                    embedding_model=settings.embedding_model
                )
            elif settings.vector_store_type == "seekdb":
                from .infrastructure.vector_stores.seekdb_vector_store import SeekDBVectorStore
                embedding_provider = (
                    cls.get_embedding_provider(settings=settings)
                    if settings.api.models.embedding_model.model and settings.api.models.embedding_model.api_key
                    else None
                )
                rerank_provider = (
                    cls.get_rerank_provider(settings=settings)
                    if settings.api.models.rerank_model.model and settings.api.models.rerank_model.api_key
                    else None
                )
                cls._vector_store = SeekDBVectorStore(
                    repository=cls.get_knowledge_repository(settings=settings),
                    embedding_provider=embedding_provider,
                    rerank_provider=rerank_provider,
                )
            # 预留 FAISS 扩展
            # elif settings.vector_store_type == "faiss":
            #     from .infrastructure.vector_stores.faiss_store import FAISSVectorStore
            #     cls._vector_store = FAISSVectorStore(...)
            else:
                raise ValueError(f"Unknown vector store type: {settings.vector_store_type}")
        
        return cls._vector_store

    @classmethod
    def get_knowledge_repository(
        cls,
        settings: Optional[Settings] = None,
        force_new: bool = False,
    ) -> KnowledgeRepositoryInterface:
        if cls._knowledge_repository is None or force_new:
            settings = settings or get_settings()
            from .infrastructure.repositories.seekdb_repository import SeekDBRepository
            cls._knowledge_repository = SeekDBRepository(settings.seekdb_path)
        return cls._knowledge_repository

    @classmethod
    def get_source_service(cls, settings: Optional[Settings] = None):
        from .core.services.chunking_service import ChunkingService
        from .core.services.source_service import SourceService
        from .infrastructure.parsers.docling_parser import DoclingParser

        settings = settings or get_settings()
        return SourceService(
            repository=cls.get_knowledge_repository(settings=settings),
            parser=DoclingParser(),
            embedding_provider=(
                cls.get_embedding_provider(settings=settings)
                if settings.api.models.embedding_model.model and settings.api.models.embedding_model.api_key
                else None
            ),
            chunking_service=ChunkingService(
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap,
                provider=settings.chunking.provider,
                tokenizer=settings.chunking.tokenizer,
            ),
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )

    @classmethod
    def get_slide_deck_service(cls, settings: Optional[Settings] = None, force_new: bool = False):
        if cls._slide_deck_service is None or force_new:
            from .core.services.slide_deck_planning_service import SlideDeckPlanningService
            from .core.services.slide_deck_service import SlideDeckService
            from .infrastructure.image_providers.raw_multimodal_provider import RawMultimodalImageProvider
            from .infrastructure.llm_providers.litellm_provider import LiteLLMProvider
            from .infrastructure.slide_deck_files import SlideDeckFileStore

            settings = settings or get_settings()
            cls._slide_deck_service = SlideDeckService(
                repository=cls.get_knowledge_repository(settings=settings),
                planning_service=SlideDeckPlanningService(LiteLLMProvider(profile=settings.api.models.text_model)),
                image_provider=RawMultimodalImageProvider(settings.api.models.image_model),
                edit_provider=RawMultimodalImageProvider(settings.api.models.edit_model),
                file_store=SlideDeckFileStore(settings.output_dir),
            )
        return cls._slide_deck_service

    @staticmethod
    def _map_litellm_profile(
        provider: str,
        api_key: str,
        base_url: Optional[str],
        model: Optional[str],
        settings: Optional[Settings] = None,
    ) -> ModelProfile:
        if settings and provider in {"litellm", "default"} and not api_key:
            profile = settings.api.models.text_model.model_copy(deep=True)
            if model:
                profile.model = model
            if base_url:
                profile.base_url = base_url
            return profile

        model_name = model or (settings.default_llm_model if settings else "gpt-4o")
        if provider in {"anthropic", "claude"} and not model_name.startswith("anthropic/"):
            model_name = f"anthropic/{model_name}"
        elif provider in {"google", "gemini", "genai"} and not model_name.startswith("gemini/"):
            model_name = f"gemini/{model_name}"
        elif provider in {"openai", "openai-compatible"} and "/" not in model_name:
            model_name = f"openai/{model_name}"

        return ModelProfile(
            model=model_name,
            api_key=api_key,
            base_url=base_url or "",
            adapter=f"{provider}_chat",
            thinking=settings.api.models.text_model.thinking if settings else None,
        )
    
    @staticmethod
    def get_llm_provider(
        provider: str,
        api_key: str,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ) -> LLMProviderInterface:
        """
        获取 LLM 提供商实例
        
        Args:
            provider: 提供商类型 ("openai" | "google")
            api_key: API 密钥
            base_url: 可选的 API 基础 URL（用于兼容接口/代理）
            model: 模型名称
            
        Returns:
            LLM 提供商实例
        """
        settings = get_settings()
        from .infrastructure.llm_providers.litellm_provider import LiteLLMProvider

        return LiteLLMProvider(
            profile=DependencyContainer._map_litellm_profile(
                provider=provider,
                api_key=api_key,
                base_url=base_url,
                model=model,
                settings=settings,
            )
        )

    @staticmethod
    def get_embedding_provider(settings: Optional[Settings] = None):
        from .infrastructure.llm_providers.litellm_provider import LiteLLMProvider

        settings = settings or get_settings()
        profile = settings.api.models.embedding_model
        if not profile.model:
            profile.model = settings.embedding_model
        return LiteLLMProvider(profile=profile)

    @staticmethod
    def get_rerank_provider(settings: Optional[Settings] = None):
        from .infrastructure.llm_providers.rerank_provider import RerankProvider

        settings = settings or get_settings()
        return RerankProvider(settings.api.models.rerank_model)
    
    @staticmethod
    def get_tts_provider(
        provider: str,
        api_key: str,
        **kwargs
    ) -> TTSProviderInterface:
        """
        获取 TTS 提供商实例
        
        Args:
            provider: 提供商类型 ("openai" | "dashscope")
            api_key: API 密钥
            
        Returns:
            TTS 提供商实例
        """
        if provider == "openai":
            from .infrastructure.tts_providers.openai_tts import OpenAITTSProvider
            return OpenAITTSProvider(api_key=api_key, **kwargs)
        elif provider == "dashscope":
            from .infrastructure.tts_providers.dashscope_tts import DashscopeTTSProvider
            return DashscopeTTSProvider(api_key=api_key, **kwargs)
        else:
            raise ValueError(f"Unknown TTS provider: {provider}")

    @staticmethod
    def get_audio_speech_provider(settings: Optional[Settings] = None):
        from .infrastructure.tts_providers.audio_speech_provider import AudioSpeechProvider

        settings = settings or get_settings()
        return AudioSpeechProvider(settings.api.models.audio_model)
    
    @staticmethod
    def get_document_parser(file_extension: str) -> DocumentParserInterface:
        """
        获取文档解析器
        
        Args:
            file_extension: 文件扩展名
            
        Returns:
            对应的文档解析器
        """
        from .infrastructure.parsers.parser_factory import ParserFactory
        return ParserFactory.get_parser(file_extension)


# 便捷函数
def get_vector_store() -> VectorStoreInterface:
    """获取向量存储（FastAPI 依赖注入用）"""
    return DependencyContainer.get_vector_store()


def get_knowledge_repository() -> KnowledgeRepositoryInterface:
    """获取知识库 repository（FastAPI 依赖注入用）"""
    return DependencyContainer.get_knowledge_repository()


def get_source_service():
    """获取 source service（FastAPI 依赖注入用）"""
    return DependencyContainer.get_source_service()


def get_slide_deck_service():
    """获取 slide deck service（FastAPI 依赖注入用）"""
    return DependencyContainer.get_slide_deck_service()


def get_embedding_provider():
    """获取 embedding provider（FastAPI 依赖注入用）"""
    return DependencyContainer.get_embedding_provider()


def get_rerank_provider():
    """获取 rerank provider（FastAPI 依赖注入用）"""
    return DependencyContainer.get_rerank_provider()


def get_audio_speech_provider():
    """获取 OpenAI-compatible speech provider（FastAPI 依赖注入用）"""
    return DependencyContainer.get_audio_speech_provider()


def get_llm_provider(
    provider: str, 
    api_key: str, 
    base_url: Optional[str] = None,
    model: Optional[str] = None
) -> LLMProviderInterface:
    """获取 LLM 提供商"""
    return DependencyContainer.get_llm_provider(provider, api_key, base_url, model)


def get_tts_provider(provider: str, api_key: str, **kwargs) -> TTSProviderInterface:
    """获取 TTS 提供商"""
    return DependencyContainer.get_tts_provider(provider, api_key, **kwargs)


def get_document_parser(file_extension: str) -> DocumentParserInterface:
    """获取文档解析器"""
    return DependencyContainer.get_document_parser(file_extension)
