"""
OpenAI TTS Provider Implementation

Uses OpenAI's Text-to-Speech API for audio synthesis.
"""
from typing import List, Dict, Any
from io import BytesIO
from pydub import AudioSegment
from ...core.interfaces.tts_provider import TTSProviderInterface


class OpenAITTSProvider(TTSProviderInterface):
    """OpenAI TTS 实现"""
    
    AVAILABLE_VOICES = [
        {"id": "alloy", "name": "Alloy", "gender": "neutral", "language": "en"},
        {"id": "echo", "name": "Echo", "gender": "male", "language": "en"},
        {"id": "fable", "name": "Fable", "gender": "neutral", "language": "en"},
        {"id": "onyx", "name": "Onyx", "gender": "male", "language": "en"},
        {"id": "nova", "name": "Nova", "gender": "female", "language": "en"},
        {"id": "shimmer", "name": "Shimmer", "gender": "female", "language": "en"},
    ]
    
    def __init__(
        self, 
        api_key: str,
        model: str = "tts-1",
        base_url: str = None
    ):
        """
        初始化 OpenAI TTS 提供商
        
        Args:
            api_key: API 密钥
            model: TTS 模型（tts-1 或 tts-1-hd）
            base_url: 可选的 API 基础 URL
        """
        import openai
        
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        self.model = model
    
    @property
    def provider_name(self) -> str:
        return "openai"
    
    @property
    def supported_languages(self) -> List[str]:
        return ["en", "zh", "ja", "ko", "de", "fr", "es", "it", "pt", "ru"]
    
    def get_available_voices(self) -> List[Dict[str, Any]]:
        return self.AVAILABLE_VOICES.copy()
    
    async def synthesize(
        self, 
        text: str, 
        voice: str = "alloy",
        speed: float = 1.0,
        **kwargs
    ) -> bytes:
        """合成语音"""
        response = self.client.audio.speech.create(
            model=self.model,
            voice=voice,
            input=text,
            speed=speed,
            response_format="mp3"
        )
        
        return response.content
    
    async def synthesize_dialogue(
        self, 
        dialogues: List[Dict[str, str]],
        voice_mapping: Dict[str, str],
        silence_duration_ms: int = 500,
        **kwargs
    ) -> bytes:
        """
        合成对话（多角色）
        
        Args:
            dialogues: 对话列表，每个元素包含 speaker 和 text
            voice_mapping: 角色到音色的映射
            silence_duration_ms: 对话间静音时长（毫秒）
        """
        if not dialogues:
            raise ValueError("No dialogues to synthesize")
        
        combined_audio = AudioSegment.silent(duration=0)
        
        for dialogue in dialogues:
            speaker = dialogue.get("speaker", "")
            text = dialogue.get("text", "")
            
            if not text:
                continue
            
            # 获取对应音色
            voice = voice_mapping.get(speaker, "alloy")
            
            # 合成单句
            audio_data = await self.synthesize(text, voice)
            
            # 转换为 AudioSegment
            segment = AudioSegment.from_mp3(BytesIO(audio_data))
            
            # 添加静音间隔
            if len(combined_audio) > 0:
                combined_audio += AudioSegment.silent(duration=silence_duration_ms)
            
            combined_audio += segment
        
        # 导出为 MP3
        output = BytesIO()
        combined_audio.export(output, format="mp3")
        return output.getvalue()
