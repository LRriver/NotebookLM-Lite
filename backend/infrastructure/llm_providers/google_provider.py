"""
Google GenAI LLM Provider Implementation

Supports Google Gemini models via the google-generativeai SDK.
"""
from typing import Type, TypeVar, List, Optional
import json
from pydantic import BaseModel
from ...core.interfaces.llm_provider import LLMProviderInterface

T = TypeVar('T', bound=BaseModel)


class GoogleLLMProvider(LLMProviderInterface):
    """Google GenAI (Gemini) 实现"""
    
    def __init__(
        self, 
        api_key: str,
        model: str = "gemini-pro"
    ):
        """
        初始化 Google GenAI 提供商
        
        Args:
            api_key: API 密钥
            model: 模型名称
        """
        import google.generativeai as genai
        
        genai.configure(api_key=api_key)
        self._genai = genai
        self._model = genai.GenerativeModel(model)
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
        # 构建完整提示
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        
        # 配置生成参数
        generation_config = self._genai.types.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        
        response = await self._model.generate_content_async(
            full_prompt,
            generation_config=generation_config
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
        # Google Gemini 需要在提示中明确要求 JSON 格式
        schema = response_model.model_json_schema()
        schema_str = json.dumps(schema, ensure_ascii=False, indent=2)
        
        structured_prompt = f"""{prompt}

请严格按照以下 JSON Schema 格式输出，只输出 JSON，不要包含其他内容：
{schema_str}"""
        
        full_prompt = structured_prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{structured_prompt}"
        
        generation_config = self._genai.types.GenerationConfig(
            temperature=temperature,
            response_mime_type="application/json",
        )
        
        response = await self._model.generate_content_async(
            full_prompt,
            generation_config=generation_config
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
