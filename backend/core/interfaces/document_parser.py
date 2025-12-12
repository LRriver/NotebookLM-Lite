"""
Document Parser Interface

Abstract interface for document parsing.
Supports PDF, DOCX, TXT, Markdown, HTML formats.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from enum import Enum


class DocumentType(str, Enum):
    """文档类型"""
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MARKDOWN = "md"
    HTML = "html"
    UNKNOWN = "unknown"


class DocumentParserInterface(ABC):
    """文档解析器抽象接口"""
    
    @abstractmethod
    def parse(self, file_path: str) -> str:
        """
        解析文档，返回纯文本
        
        Args:
            file_path: 文件路径
            
        Returns:
            提取的纯文本内容
        """
        pass
    
    @abstractmethod
    def parse_with_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        解析文档，返回文本和元数据
        
        Args:
            file_path: 文件路径
            
        Returns:
            包含 content, metadata 的字典
        """
        pass
    
    @property
    @abstractmethod
    def supported_extensions(self) -> List[str]:
        """支持的文件扩展名列表（不含点号）"""
        pass
    
    def supports(self, file_extension: str) -> bool:
        """
        检查是否支持该文件类型
        
        Args:
            file_extension: 文件扩展名（可带或不带点号）
            
        Returns:
            是否支持
        """
        ext = file_extension.lstrip('.').lower()
        return ext in self.supported_extensions
    
    @staticmethod
    def detect_type(file_path: str) -> DocumentType:
        """
        检测文档类型
        
        Args:
            file_path: 文件路径
            
        Returns:
            文档类型枚举
        """
        import os
        ext = os.path.splitext(file_path)[1].lstrip('.').lower()
        try:
            return DocumentType(ext)
        except ValueError:
            return DocumentType.UNKNOWN
