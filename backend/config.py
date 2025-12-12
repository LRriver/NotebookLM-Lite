"""
Application Configuration

Centralized configuration management using Pydantic Settings.
Supports environment variables and .env files.
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional, Literal
from functools import lru_cache


class Settings(BaseSettings):
    """应用配置"""
    
    # 应用设置
    app_name: str = "NotebookLM-Lite"
    app_version: str = "2.0.0"
    debug: bool = False
    
    # 服务器设置
    host: str = "0.0.0.0"
    port: int = 8000
    
    # 向量数据库设置
    vector_store_type: Literal["chroma", "faiss"] = "chroma"
    chroma_persist_dir: str = "./data/chroma"
    
    # 嵌入模型设置
    embedding_model: str = "all-MiniLM-L6-v2"
    
    # 文件上传设置
    upload_dir: str = "./uploads"
    output_dir: str = "./output"
    max_upload_size_mb: int = 50
    
    # 文档处理设置
    chunk_size: int = 1000
    chunk_overlap: int = 200
    
    # 默认 LLM 设置
    default_llm_provider: Literal["openai", "google"] = "openai"
    default_llm_model: str = "gpt-4o"
    
    # 默认 TTS 设置
    default_tts_provider: Literal["openai", "dashscope"] = "openai"
    
    # 播客设置
    chars_per_minute: int = 200  # 中文语速
    max_podcast_iterations: int = 5  # 最大迭代次数
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """获取应用配置（单例）"""
    return Settings()
