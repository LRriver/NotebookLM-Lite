"""
OpenAI LLM Provider Implementation

Supports OpenAI API and compatible providers (DeepSeek, Moonshot, etc.)
"""
from typing import Type, TypeVar, List, Optional
import json
from pydantic import BaseModel
from ...core.interfaces.llm_provider import LLMProviderInterface

T = TypeVar('T', bound=BaseModel)


class OpenAILLMProvider(LLMProviderInterface):
    """OpenAI 及兼容接口实现"""
    
    def __init__(
        self, 
        api_key: str, 
        base_url: Optional[str] = None,
        model: str = "gpt-4o"
    ):
        """
        初始化 OpenAI 提供商
        
        Args:
            api_key: API 密钥
            base_url: API 基础 URL（用于兼容接口）
            model: 模型名称
        """
        import openai
        
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        self._model_name = model
        self._base_url = base_url
    
    @property
    def model_name(self) -> str:
        return self._model_name
    
    @property
    def provider_name(self) -> str:
        if self._base_url:
            return f"openai-compatible ({self._base_url})"
        return "openai"
    
    async def generate(
        self, 
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> str:
        """普通文本生成"""
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        response = self.client.chat.completions.create(
            model=self._model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
        
        return response.choices[0].message.content
    
    async def generate_structured(
        self, 
        prompt: str, 
        response_model: Type[T],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        **kwargs
    ) -> T:
        """结构化输出生成"""
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        try:
            # 尝试使用 beta.chat.completions.parse（需要较新的 OpenAI SDK）
            response = self.client.beta.chat.completions.parse(
                model=self._model_name,
                messages=messages,
                response_format=response_model,
                temperature=temperature,
                **kwargs
            )
            return response.choices[0].message.parsed
        except AttributeError:
            # 回退到 JSON 模式
            schema_hint = f"\n\n请严格按照以下 JSON Schema 格式输出：\n{json.dumps(response_model.model_json_schema(), ensure_ascii=False, indent=2)}"
            messages[-1]["content"] += schema_hint
            
            response = self.client.chat.completions.create(
                model=self._model_name,
                messages=messages,
                temperature=temperature,
                response_format={"type": "json_object"},
                **kwargs
            )
            
            content = response.choices[0].message.content
            return response_model.model_validate_json(content)
    
    async def generate_with_context(
        self,
        query: str,
        context: List[str],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """带上下文的生成（用于RAG）"""
        # 构建上下文增强的提示
        context_text = "\n\n---\n\n".join(context)
        
        rag_prompt = f"""基于以下参考资料回答问题。如果资料中没有相关信息，请如实说明。

【参考资料】
{context_text}

【问题】
{query}

【回答】"""
        
        default_system = "你是一个知识渊博的助手，擅长基于给定资料准确回答问题。"
        
        return await self.generate(
            prompt=rag_prompt,
            system_prompt=system_prompt or default_system,
            **kwargs
        )
