"""
Dashscope TTS Provider Implementation

Uses Alibaba's Dashscope CosyVoice for Chinese TTS.
"""
from typing import List, Dict, Any
from io import BytesIO
from pydub import AudioSegment
from ...core.interfaces.tts_provider import TTSProviderInterface


class DashscopeTTSProvider(TTSProviderInterface):
    """Dashscope CosyVoice TTS 实现"""
    
    AVAILABLE_VOICES = [
        {"id": "loongstella", "name": "Stella", "gender": "female", "language": "zh"},
        {"id": "longshu", "name": "Longshu", "gender": "male", "language": "zh"},
        {"id": "longxiaochun", "name": "Xiaochun", "gender": "female", "language": "zh"},
        {"id": "longxiaoxia", "name": "Xiaoxia", "gender": "female", "language": "zh"},
        {"id": "longyue", "name": "Longyue", "gender": "male", "language": "zh"},
    ]
    
    def __init__(self, api_key: str, **kwargs):
        """
        初始化 Dashscope TTS 提供商
        
        Args:
            api_key: Dashscope API 密钥
        """
        import dashscope
        dashscope.api_key = api_key
        self.api_key = api_key
    
    @property
    def provider_name(self) -> str:
        return "dashscope"
    
    @property
    def supported_languages(self) -> List[str]:
        return ["zh", "en"]
    
    def get_available_voices(self) -> List[Dict[str, Any]]:
        return self.AVAILABLE_VOICES.copy()
    
    async def synthesize(
        self, 
        text: str, 
        voice: str = "loongstella",
        speed: float = 1.0,
        **kwargs
    ) -> bytes:
        """合成语音"""
        from dashscope.audio.tts_v2 import SpeechSynthesizer
        
        synthesizer = SpeechSynthesizer(
            model="cosyvoice-v1",
            voice=voice,
            callback=None
        )
        
        audio_data = synthesizer.call(text)
        return audio_data
    
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
            dialogues: 对话列表
            voice_mapping: 角色到音色的映射
            silence_duration_ms: 对话间静音时长
        """
        from dashscope.audio.tts_v2 import SpeechSynthesizer
        
        if not dialogues:
            raise ValueError("No dialogues to synthesize")
        
        combined_audio = AudioSegment.silent(duration=0)
        
        for dialogue in dialogues:
            speaker = dialogue.get("speaker", "")
            text = dialogue.get("text", "")
            
            if not text:
                continue
            
            # 获取对应音色
            voice = voice_mapping.get(speaker, "loongstella")
            
            # 合成
            synthesizer = SpeechSynthesizer(
                model="cosyvoice-v1",
                voice=voice,
                callback=None
            )
            audio_data = synthesizer.call(text)
            
            # 保存临时文件并读取
            temp_file = BytesIO(audio_data)
            segment = AudioSegment.from_file(temp_file)
            
            # 添加静音间隔
            if len(combined_audio) > 0:
                combined_audio += AudioSegment.silent(duration=silence_duration_ms)
            
            combined_audio += segment
        
        # 导出为 MP3
        output = BytesIO()
        combined_audio.export(output, format="mp3")
        return output.getvalue()
