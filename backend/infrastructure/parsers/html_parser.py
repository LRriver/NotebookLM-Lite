"""
HTML Parser Implementation

Uses BeautifulSoup for HTML content extraction.
"""
from typing import List, Dict, Any
from ...core.interfaces.document_parser import DocumentParserInterface


class HTMLParser(DocumentParserInterface):
    """HTML 文档解析器"""
    
    @property
    def supported_extensions(self) -> List[str]:
        return ["html", "htm"]
    
    def parse(self, file_path: str) -> str:
        """
        解析 HTML 文档，返回纯文本
        
        Args:
            file_path: HTML 文件路径
            
        Returns:
            提取的纯文本内容
        """
        try:
            from bs4 import BeautifulSoup
            
            with open(file_path, "r", encoding="utf-8") as f:
                soup = BeautifulSoup(f.read(), "html.parser")
            
            # 移除脚本和样式
            for script in soup(["script", "style", "meta", "link"]):
                script.decompose()
            
            # 获取文本
            text = soup.get_text(separator="\n")
            
            # 清理空白行
            lines = [line.strip() for line in text.splitlines()]
            lines = [line for line in lines if line]
            
            return "\n\n".join(lines)
            
        except Exception as e:
            raise RuntimeError(f"HTML parsing failed: {str(e)}")
    
    def parse_with_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        解析 HTML 文档，返回文本和元数据
        
        Args:
            file_path: HTML 文件路径
            
        Returns:
            包含 content 和 metadata 的字典
        """
        try:
            from bs4 import BeautifulSoup
            
            with open(file_path, "r", encoding="utf-8") as f:
                soup = BeautifulSoup(f.read(), "html.parser")
            
            # 提取元数据
            metadata = {}
            
            # 标题
            title_tag = soup.find("title")
            if title_tag:
                metadata["title"] = title_tag.get_text().strip()
            
            # Meta 标签
            for meta in soup.find_all("meta"):
                name = meta.get("name", "").lower()
                content = meta.get("content", "")
                if name in ["description", "author", "keywords"]:
                    metadata[name] = content
            
            # 移除脚本和样式后获取文本
            for script in soup(["script", "style", "meta", "link"]):
                script.decompose()
            
            text = soup.get_text(separator="\n")
            lines = [line.strip() for line in text.splitlines()]
            lines = [line for line in lines if line]
            content = "\n\n".join(lines)
            
            metadata["char_count"] = len(content)
            
            return {
                "content": content,
                "metadata": metadata
            }
            
        except Exception as e:
            raise RuntimeError(f"HTML parsing failed: {str(e)}")
