"""
Podcast Domain Models

Core data structures for podcast generation with structured output support.
"""
from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from enum import Enum


class DurationRange(str, Enum):
    """播客时长档位"""
    SHORT = "3-5"       # 3-5分钟
    MEDIUM = "5-10"     # 5-10分钟
    LONG = "10-15"      # 10-15分钟
    EXTENDED = "15-20"  # 15-20分钟
    DEEP = "20-30"      # 20-30分钟
    
    @property
    def min_minutes(self) -> int:
        """最小时长（分钟）"""
        return int(self.value.split("-")[0])
    
    @property
    def max_minutes(self) -> int:
        """最大时长（分钟）"""
        return int(self.value.split("-")[1])
    
    @property
    def target_minutes(self) -> float:
        """目标时长（取中间值）"""
        return (self.min_minutes + self.max_minutes) / 2
    
    @classmethod
    def from_minutes(cls, minutes: int) -> "DurationRange":
        """根据分钟数选择合适的档位"""
        if minutes <= 5:
            return cls.SHORT
        elif minutes <= 10:
            return cls.MEDIUM
        elif minutes <= 15:
            return cls.LONG
        elif minutes <= 20:
            return cls.EXTENDED
        else:
            return cls.DEEP


class DialogueTurn(BaseModel):
    """
    单轮对话模型 - 用于结构化输出
    
    这是播客脚本的基本单元，每个对话轮次包含说话人和内容。
    """
    speaker: Literal["主持人", "嘉宾"] = Field(
        ..., 
        description="说话人角色"
    )
    text: str = Field(
        ..., 
        max_length=200,
        description="对话内容，应该自然流畅，不超过200字"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "speaker": "主持人",
                "text": "大家好，欢迎收听今天的节目！今天我们邀请到了一位重量级嘉宾。"
            }
        }


class PodcastScript(BaseModel):
    """
    完整播客脚本模型 - 用于结构化输出
    
    包含播客的完整对话内容和元信息。
    """
    title: str = Field(..., description="播客标题")
    host_name: str = Field(..., description="主持人名称")
    guest_name: str = Field(..., description="嘉宾名称")
    guest_intro: str = Field(..., description="嘉宾简介")
    dialogues: List[DialogueTurn] = Field(
        ..., 
        min_length=10,
        description="对话轮次列表，至少10轮"
    )
    estimated_duration_minutes: float = Field(
        default=0.0, 
        description="预估时长（分钟）"
    )
    coverage_notes: List[str] = Field(default_factory=list, description="覆盖与扩写说明")
    
    @property
    def dialogue_count(self) -> int:
        """对话轮次数"""
        return len(self.dialogues)
    
    @property
    def total_chars(self) -> int:
        """总字符数"""
        return sum(len(d.text) for d in self.dialogues)
    
    def estimate_duration(self, chars_per_minute: int = 200) -> float:
        """
        估算播客时长
        
        Args:
            chars_per_minute: 每分钟字符数（中文语速约200字/分钟）
            
        Returns:
            估算时长（分钟）
        """
        return self.total_chars / chars_per_minute
    
    def to_transcript(self) -> str:
        """
        转换为纯文本脚本
        
        Returns:
            格式化的对话脚本
        """
        lines = [f"# {self.title}\n"]
        lines.append(f"主持人：{self.host_name}")
        lines.append(f"嘉宾：{self.guest_name} - {self.guest_intro}\n")
        lines.append("---\n")
        
        for d in self.dialogues:
            lines.append(f"[{d.speaker}] {d.text}")
        
        return "\n".join(lines)
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "AI技术前沿探讨",
                "host_name": "小明",
                "guest_name": "张教授",
                "guest_intro": "清华大学人工智能研究院教授",
                "dialogues": [
                    {"speaker": "主持人", "text": "欢迎张教授！"},
                    {"speaker": "嘉宾", "text": "谢谢邀请！"}
                ],
                "estimated_duration_minutes": 5.0
            }
        }


class PodcastExtension(BaseModel):
    """
    播客扩展对话模型 - 用于迭代扩展
    
    当需要延长播客时长时，生成额外的对话内容。
    """
    dialogues: List[DialogueTurn] = Field(
        ...,
        min_length=5,
        description="扩展对话，至少5轮"
    )
    transition_note: Optional[str] = Field(
        None,
        description="过渡说明，描述如何与前文衔接"
    )
