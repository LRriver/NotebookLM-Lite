"""
TTS Provider Interface

Abstract interface for Text-to-Speech providers.
Supports OpenAI TTS, Dashscope CosyVoice, and other TTS services.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from enum import Enum


class VoiceGender(str, Enum):
    """音色性别"""
    MALE = "male"
    FEMALE = "female"
    NEUTRAL = "neutral"


class TTSProviderInterface(ABC):
    """TTS 提供商抽象接口"""
    
    @abstractmethod
    async def synthesize(
        self, 
        text: str, 
        voice: str,
        speed: float = 1.0,
        **kwargs
    ) -> bytes:
        """
        合成语音
        
        Args:
            text: 要转换的文本
            voice: 音色标识符
            speed: 语速，1.0为正常速度
            
        Returns:
            音频数据（bytes）
        """
        pass
    
    @abstractmethod
    async def synthesize_dialogue(
        self, 
        dialogues: List[Dict[str, str]],
        voice_mapping: Dict[str, str],
        **kwargs
    ) -> bytes:
        """
        合成对话（多角色）
        
        Args:
            dialogues: 对话列表，每个元素包含 speaker 和 text
            voice_mapping: 角色到音色的映射 {"主持人": "voice_id_1", "嘉宾": "voice_id_2"}
            
        Returns:
            合并后的音频数据
        """
        pass
    
    @abstractmethod
    def get_available_voices(self) -> List[Dict[str, Any]]:
        """
        获取可用音色列表
        
        Returns:
            音色列表，每个元素包含 id, name, gender, language 等信息
        """
        pass
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """提供商名称"""
        pass
    
    @property
    @abstractmethod
    def supported_languages(self) -> List[str]:
        """支持的语言列表"""
        pass
