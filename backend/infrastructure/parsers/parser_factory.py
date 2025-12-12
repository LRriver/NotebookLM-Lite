"""
Parser Factory

Factory for creating appropriate document parsers based on file type.
"""
from typing import Dict, Type
from ...core.interfaces.document_parser import DocumentParserInterface, DocumentType
from .pdf_parser import PDFParser
from .docx_parser import DocxParser
from .text_parser import TextParser
from .html_parser import HTMLParser


class ParserFactory:
    """文档解析器工厂"""
    
    _parsers: Dict[str, Type[DocumentParserInterface]] = {
        "pdf": PDFParser,
        "docx": DocxParser,
        "doc": DocxParser,
        "txt": TextParser,
        "md": TextParser,
        "markdown": TextParser,
        "text": TextParser,
        "html": HTMLParser,
        "htm": HTMLParser,
    }
    
    @classmethod
    def get_parser(cls, file_extension: str) -> DocumentParserInterface:
        """
        根据文件扩展名获取解析器
        
        Args:
            file_extension: 文件扩展名（可带或不带点号）
            
        Returns:
            对应的解析器实例
            
        Raises:
            ValueError: 不支持的文件类型
        """
        ext = file_extension.lstrip('.').lower()
        
        if ext not in cls._parsers:
            supported = ", ".join(sorted(set(cls._parsers.keys())))
            raise ValueError(
                f"Unsupported file type: {ext}. Supported types: {supported}"
            )
        
        return cls._parsers[ext]()
    
    @classmethod
    def get_parser_for_file(cls, file_path: str) -> DocumentParserInterface:
        """
        根据文件路径获取解析器
        
        Args:
            file_path: 文件路径
            
        Returns:
            对应的解析器实例
        """
        import os
        ext = os.path.splitext(file_path)[1]
        return cls.get_parser(ext)
    
    @classmethod
    def is_supported(cls, file_extension: str) -> bool:
        """
        检查是否支持该文件类型
        
        Args:
            file_extension: 文件扩展名
            
        Returns:
            是否支持
        """
        ext = file_extension.lstrip('.').lower()
        return ext in cls._parsers
    
    @classmethod
    def supported_extensions(cls) -> list:
        """获取所有支持的扩展名"""
        return sorted(set(cls._parsers.keys()))
    
    @classmethod
    def register_parser(
        cls, 
        extension: str, 
        parser_class: Type[DocumentParserInterface]
    ) -> None:
        """
        注册新的解析器
        
        Args:
            extension: 文件扩展名
            parser_class: 解析器类
        """
        cls._parsers[extension.lower()] = parser_class
