"""
Text Parser Implementation

Handles plain text and Markdown files.
"""
from typing import List, Dict, Any
import os
from ...core.interfaces.document_parser import DocumentParserInterface


class TextParser(DocumentParserInterface):
    """纯文本/Markdown 解析器"""
    
    @property
    def supported_extensions(self) -> List[str]:
        return ["txt", "md", "markdown", "text"]
    
    def parse(self, file_path: str) -> str:
        """
        解析文本文件，返回内容
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件内容
        """
        try:
            # 尝试多种编码
            encodings = ["utf-8", "gbk", "gb2312", "latin-1"]
            
            for encoding in encodings:
                try:
                    with open(file_path, "r", encoding=encoding) as f:
                        return f.read()
                except UnicodeDecodeError:
                    continue
            
            # 如果所有编码都失败，使用 errors='ignore'
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
                
        except Exception as e:
            raise RuntimeError(f"Text parsing failed: {str(e)}")
    
    def parse_with_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        解析文本文件，返回内容和元数据
        
        Args:
            file_path: 文件路径
            
        Returns:
            包含 content 和 metadata 的字典
        """
        content = self.parse(file_path)
        
        # 获取文件统计信息
        stat = os.stat(file_path)
        
        metadata = {
            "file_size": stat.st_size,
            "line_count": content.count("\n") + 1,
            "char_count": len(content),
            "word_count": len(content.split()),
        }
        
        return {
            "content": content,
            "metadata": metadata
        }
