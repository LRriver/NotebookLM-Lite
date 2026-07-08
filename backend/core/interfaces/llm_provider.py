"""
LLM Provider Interface

Abstract interface for Language Model providers.
Supports OpenAI, Google GenAI (Gemini), and OpenAI-compatible APIs.
"""
from abc import ABC, abstractmethod
from typing import Type, TypeVar, List, Optional
from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)


class LLMProviderInterface(ABC):
    """LLM 提供商抽象接口"""
    
    @abstractmethod
    async def generate(
        self, 
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> str:
        """
        普通文本生成
        
        Args:
            prompt: 用户提示词
            system_prompt: 可选的系统提示词
            temperature: 生成温度，控制随机性
            max_tokens: 最大输出token数
            
        Returns:
            生成的文本内容
        """
        pass
    
    @abstractmethod
    async def generate_structured(
        self, 
        prompt: str, 
        response_model: Type[T],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        **kwargs
    ) -> T:
        """
        结构化输出生成
        
        Args:
            prompt: 用户提示词
            response_model: Pydantic 模型类，定义输出结构
            system_prompt: 可选的系统提示词
            temperature: 生成温度
            
        Returns:
            符合 response_model 结构的对象
        """
        pass
    
    @abstractmethod
    async def generate_with_context(
        self,
        query: str,
        context: List[str],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        带上下文的生成（用于RAG）
        
        Args:
            query: 用户查询
            context: 相关上下文列表
            system_prompt: 可选的系统提示词
            
        Returns:
            基于上下文的回答
        """
        pass
    
    @property
    @abstractmethod
    def model_name(self) -> str:
        """当前使用的模型名称"""
        pass
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """提供商名称"""
        pass
