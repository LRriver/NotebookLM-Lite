"""
PDF Parser Implementation

Uses pypdf for PDF text extraction.
"""
from typing import List, Dict, Any
from ...core.interfaces.document_parser import DocumentParserInterface


class PDFParser(DocumentParserInterface):
    """PDF 文档解析器"""
    
    @property
    def supported_extensions(self) -> List[str]:
        return ["pdf"]
    
    def parse(self, file_path: str) -> str:
        """
        解析 PDF 文档，返回纯文本
        
        Args:
            file_path: PDF 文件路径
            
        Returns:
            提取的纯文本内容
        """
        try:
            from pypdf import PdfReader
            
            with open(file_path, "rb") as f:
                reader = PdfReader(f)
                text_parts = []
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                return "\n\n".join(text_parts)
        except Exception as e:
            raise RuntimeError(f"PDF parsing failed: {str(e)}")
    
    def parse_with_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        解析 PDF 文档，返回文本和元数据
        
        Args:
            file_path: PDF 文件路径
            
        Returns:
            包含 content 和 metadata 的字典
        """
        try:
            from pypdf import PdfReader
            
            with open(file_path, "rb") as f:
                reader = PdfReader(f)
                
                # 提取文本
                text_parts = []
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                
                # 提取元数据
                metadata = {}
                if reader.metadata:
                    metadata = {
                        "title": reader.metadata.get("/Title", ""),
                        "author": reader.metadata.get("/Author", ""),
                        "subject": reader.metadata.get("/Subject", ""),
                        "creator": reader.metadata.get("/Creator", ""),
                    }
                metadata["page_count"] = len(reader.pages)
                
                return {
                    "content": "\n\n".join(text_parts),
                    "metadata": metadata
                }
        except Exception as e:
            raise RuntimeError(f"PDF parsing failed: {str(e)}")
