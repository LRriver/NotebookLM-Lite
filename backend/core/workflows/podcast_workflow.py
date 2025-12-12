"""
Podcast Generation Workflow

Iterative podcast generation with controllable duration.
Supports extending dialogue to reach target duration.
"""
from typing import List, Optional
from ..interfaces.llm_provider import LLMProviderInterface
from ...domain.podcast import (
    DurationRange, 
    DialogueTurn, 
    PodcastScript, 
    PodcastExtension
)


# 播客生成 Prompt 模板
INITIAL_PROMPT_TEMPLATE = """您是一位世界级的播客制作人,负责将提供的输入文本转换为引人入胜、内容丰富的播客脚本。

【输入材料】
{source_text}

【播客要求】
- 目标时长：约 {target_minutes} 分钟
- 对话轮次：约 {target_turns} 轮
- 风格：{style_description}

【格式要求】
1. 主持人开场介绍自己和嘉宾
2. 每轮对话不超过150字
3. 使用自然口语，适当使用语气词
4. 最后自然结束对话

请生成完整的播客脚本。"""

EXTENSION_PROMPT_TEMPLATE = """您是一位播客制作人，需要扩展已有的播客对话。

【原始材料摘要】
{source_summary}

【已生成对话概要】
{existing_summary}

【最后几轮对话】
{last_dialogues}

【扩展要求】
- 新增约 {additional_minutes} 分钟内容（约 {additional_turns} 轮对话）
- 继续讨论尚未充分探讨的主题
- 可以引入新的角度或深入讨论
- 保持与前文的连贯性
- 不要重复已讨论的内容

请生成扩展对话，从紧接着上文的地方继续。"""


# 风格描述
STYLE_DESCRIPTIONS = {
    "default": "采访式对话，主持人提问，嘉宾回答",
    "discussion": "热烈讨论，双方都积极参与",
    "teaching": "教学式，老师讲解，学生提问",
    "argument": "辩论式，双方持不同观点",
    "interview": "正式面试风格",
}


class PodcastWorkflow:
    """
    迭代式播客生成工作流
    
    支持可控时长的播客生成，通过迭代扩展对话达到目标时长。
    """
    
    CHARS_PER_MINUTE = 200  # 中文语速约每分钟200字
    CHARS_PER_TURN = 80     # 平均每轮对话80字
    
    def __init__(
        self, 
        llm_provider: LLMProviderInterface,
        max_iterations: int = 5
    ):
        """
        初始化工作流
        
        Args:
            llm_provider: LLM 提供商实例
            max_iterations: 最大迭代次数
        """
        self.llm = llm_provider
        self.max_iterations = max_iterations
    
    def estimate_duration(self, dialogues: List[DialogueTurn]) -> float:
        """
        估算对话时长（分钟）
        
        Args:
            dialogues: 对话列表
            
        Returns:
            估算时长（分钟）
        """
        total_chars = sum(len(d.text) for d in dialogues)
        return total_chars / self.CHARS_PER_MINUTE
    
    def _calculate_target_turns(self, minutes: float) -> int:
        """计算目标对话轮次"""
        return int(minutes * self.CHARS_PER_MINUTE / self.CHARS_PER_TURN)
    
    async def generate(
        self, 
        source_text: str,
        duration_range: DurationRange = DurationRange.SHORT,
        prompt_type: str = "default"
    ) -> PodcastScript:
        """
        生成播客脚本
        
        Args:
            source_text: 源文本材料
            duration_range: 目标时长范围
            prompt_type: 提示类型/风格
            
        Returns:
            完整的播客脚本
        """
        target_minutes = duration_range.target_minutes
        style_desc = STYLE_DESCRIPTIONS.get(prompt_type, STYLE_DESCRIPTIONS["default"])
        
        # 1. 生成初始脚本
        initial_prompt = INITIAL_PROMPT_TEMPLATE.format(
            source_text=source_text[:8000],  # 限制长度
            target_minutes=target_minutes,
            target_turns=self._calculate_target_turns(target_minutes),
            style_description=style_desc
        )
        
        script = await self.llm.generate_structured(
            prompt=initial_prompt,
            response_model=PodcastScript,
            temperature=0.8
        )
        
        current_duration = self.estimate_duration(script.dialogues)
        
        # 2. 如果未达到最小时长，迭代扩展
        iteration = 0
        while current_duration < duration_range.min_minutes and iteration < self.max_iterations:
            additional_minutes = duration_range.min_minutes - current_duration
            
            extension = await self._generate_extension(
                source_text=source_text,
                existing_dialogues=script.dialogues,
                additional_minutes=additional_minutes
            )
            
            if extension and extension.dialogues:
                script.dialogues.extend(extension.dialogues)
                current_duration = self.estimate_duration(script.dialogues)
            else:
                break
            
            iteration += 1
        
        # 更新估算时长
        script.estimated_duration_minutes = current_duration
        
        return script
    
    async def _generate_extension(
        self,
        source_text: str,
        existing_dialogues: List[DialogueTurn],
        additional_minutes: float
    ) -> Optional[PodcastExtension]:
        """
        生成扩展对话
        
        Args:
            source_text: 源文本
            existing_dialogues: 已有对话
            additional_minutes: 需要增加的时长
            
        Returns:
            扩展对话
        """
        if additional_minutes <= 0:
            return None
        
        # 准备摘要
        source_summary = source_text[:2000] + "..." if len(source_text) > 2000 else source_text
        
        existing_summary = f"已生成 {len(existing_dialogues)} 轮对话，约 {self.estimate_duration(existing_dialogues):.1f} 分钟"
        
        # 最后5轮对话
        last_dialogues = "\n".join([
            f"[{d.speaker}] {d.text}" 
            for d in existing_dialogues[-5:]
        ])
        
        extension_prompt = EXTENSION_PROMPT_TEMPLATE.format(
            source_summary=source_summary,
            existing_summary=existing_summary,
            last_dialogues=last_dialogues,
            additional_minutes=additional_minutes,
            additional_turns=self._calculate_target_turns(additional_minutes)
        )
        
        try:
            extension = await self.llm.generate_structured(
                prompt=extension_prompt,
                response_model=PodcastExtension,
                temperature=0.8
            )
            return extension
        except Exception:
            return None
    
    async def generate_with_callback(
        self,
        source_text: str,
        duration_range: DurationRange,
        prompt_type: str = "default",
        on_progress: callable = None
    ) -> PodcastScript:
        """
        带进度回调的播客生成
        
        Args:
            source_text: 源文本
            duration_range: 时长范围
            prompt_type: 提示类型
            on_progress: 进度回调函数 (current_duration, target_duration, iteration)
            
        Returns:
            播客脚本
        """
        target_minutes = duration_range.target_minutes
        style_desc = STYLE_DESCRIPTIONS.get(prompt_type, STYLE_DESCRIPTIONS["default"])
        
        # 初始生成
        initial_prompt = INITIAL_PROMPT_TEMPLATE.format(
            source_text=source_text[:8000],
            target_minutes=target_minutes,
            target_turns=self._calculate_target_turns(target_minutes),
            style_description=style_desc
        )
        
        script = await self.llm.generate_structured(
            prompt=initial_prompt,
            response_model=PodcastScript,
            temperature=0.8
        )
        
        current_duration = self.estimate_duration(script.dialogues)
        
        if on_progress:
            on_progress(current_duration, duration_range.min_minutes, 0)
        
        # 迭代扩展
        iteration = 0
        while current_duration < duration_range.min_minutes and iteration < self.max_iterations:
            additional_minutes = duration_range.min_minutes - current_duration
            
            extension = await self._generate_extension(
                source_text=source_text,
                existing_dialogues=script.dialogues,
                additional_minutes=additional_minutes
            )
            
            if extension and extension.dialogues:
                script.dialogues.extend(extension.dialogues)
                current_duration = self.estimate_duration(script.dialogues)
            else:
                break
            
            iteration += 1
            
            if on_progress:
                on_progress(current_duration, duration_range.min_minutes, iteration)
        
        script.estimated_duration_minutes = current_duration
        return script
