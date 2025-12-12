"""
Dependency Injection Container

Factory methods for creating service instances with proper abstraction.
Enables easy testing and swapping of implementations.
"""
from typing import Optional
from functools import lru_cache

from .config import Settings, get_settings
from .core.interfaces.vector_store import VectorStoreInterface
from .core.interfaces.llm_provider import LLMProviderInterface
from .core.interfaces.tts_provider import TTSProviderInterface
from .core.interfaces.document_parser import DocumentParserInterface


class DependencyContainer:
    """依赖注入容器"""
    
    _vector_store: Optional[VectorStoreInterface] = None
    
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
            # 预留 FAISS 扩展
            # elif settings.vector_store_type == "faiss":
            #     from .infrastructure.vector_stores.faiss_store import FAISSVectorStore
            #     cls._vector_store = FAISSVectorStore(...)
            else:
                raise ValueError(f"Unknown vector store type: {settings.vector_store_type}")
        
        return cls._vector_store
    
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
            base_url: 可选的 API 基础 URL（用于兼容接口）
            model: 模型名称
            
        Returns:
            LLM 提供商实例
        """
        if provider == "openai":
            from .infrastructure.llm_providers.openai_provider import OpenAILLMProvider
            return OpenAILLMProvider(
                api_key=api_key,
                base_url=base_url,
                model=model or "gpt-4o"
            )
        elif provider == "google":
            from .infrastructure.llm_providers.google_provider import GoogleLLMProvider
            return GoogleLLMProvider(
                api_key=api_key,
                model=model or "gemini-pro"
            )
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")
    
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
