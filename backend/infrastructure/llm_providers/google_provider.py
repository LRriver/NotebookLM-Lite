"""
Google GenAI LLM Provider Implementation

Supports Google Gemini models via the google-genai SDK.
Supports custom base URL for proxy services.
"""
from typing import Type, TypeVar, List, Optional
import json
from pydantic import BaseModel
from ...core.interfaces.llm_provider import LLMProviderInterface

T = TypeVar('T', bound=BaseModel)

# Default Google API endpoint
DEFAULT_GOOGLE_BASE_URL = "https://generativelanguage.googleapis.com"


class GoogleLLMProvider(LLMProviderInterface):
    """Google GenAI (Gemini) 实现 - 支持自定义 Base URL"""
    
    def __init__(
        self, 
        api_key: str,
        model: str = "gemini-pro",
        base_url: Optional[str] = None
    ):
        """
        初始化 Google GenAI 提供商
        
        Args:
            api_key: API 密钥
            model: 模型名称
            base_url: 可选的 API 基础 URL（用于代理服务）
        """
        from google import genai
        
        # 使用新的 genai.Client 方式，支持自定义 base URL
        http_options = {}
        if base_url:
            http_options['baseUrl'] = base_url
        
        self._client = genai.Client(
            api_key=api_key,
            http_options=http_options if http_options else None
        )
        self._model_name = model
    
    @property
    def model_name(self) -> str:
        return self._model_name
    
    @property
    def provider_name(self) -> str:
        return "google"
    
    async def generate(
        self, 
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> str:
        """普通文本生成"""
        from google.genai import types
        
        # 构建完整提示
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        
        # 配置生成参数
        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        
        response = self._client.models.generate_content(
            model=self._model_name,
            contents=full_prompt,
            config=config
        )
        
        return response.text
    
    async def generate_structured(
        self, 
        prompt: str, 
        response_model: Type[T],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        **kwargs
    ) -> T:
        """结构化输出生成"""
        from google.genai import types
        
        # Google Gemini 需要在提示中明确要求 JSON 格式
        schema = response_model.model_json_schema()
        schema_str = json.dumps(schema, ensure_ascii=False, indent=2)
        
        structured_prompt = f"""{prompt}

请严格按照以下 JSON Schema 格式输出，只输出 JSON，不要包含其他内容：
{schema_str}"""
        
        full_prompt = structured_prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{structured_prompt}"
        
        config = types.GenerateContentConfig(
            temperature=temperature,
            response_mime_type="application/json",
        )
        
        response = self._client.models.generate_content(
            model=self._model_name,
            contents=full_prompt,
            config=config
        )
        
        # 解析 JSON 响应
        try:
            return response_model.model_validate_json(response.text)
        except Exception:
            # 尝试清理响应后再解析
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            return response_model.model_validate_json(text.strip())
    
    async def generate_with_context(
        self,
        query: str,
        context: List[str],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """带上下文的生成（用于RAG）"""
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
