"""解析器基类"""

import re
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple, Optional


class BaseParser(ABC):
    """解析器基类"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._comment_cache: Dict[str, Dict[int, str]] = {}

    @abstractmethod
    def parse(self, content: str, file_path: str) -> List[Any]:
        """
        解析内容

        Args:
            content: 源码内容
            file_path: 文件路径

        Returns:
            解析结果列表
        """
        pass

    def remove_comments(self, content: str) -> str:
        """
        移除注释（保留换行符以便计算行号）

        Args:
            content: 源码内容

        Returns:
            移除注释后的内容
        """
        result = []
        i = 0
        length = len(content)

        while i < length:
            # 检查 /* */ 注释
            if i < length - 1 and content[i:i+2] == '/*':
                end = content.find('*/', i + 2)
                if end != -1:
                    # 保留换行符
                    comment_content = content[i:end+2]
                    newlines = comment_content.count('\n')
                    result.append(' ' * (end - i + 2 - newlines) + '\n' * newlines)
                    i = end + 2
                    continue

            # 检查 // 注释
            if i < length - 1 and content[i:i+2] == '//':
                end = content.find('\n', i)
                if end != -1:
                    result.append('\n')
                    i = end + 1
                    continue
                else:
                    break

            result.append(content[i])
            i += 1

        return ''.join(result)

    def extract_block_comments(self, content: str) -> Dict[int, Tuple[str, str]]:
        """
        提取块注释

        Returns:
            {结束行号: (注释内容, 注释类型)}
        """
        comments = {}
        pattern = r'/\*\*?(.*?)\*/'

        for match in re.finditer(pattern, content, re.DOTALL):
            # 计算注释结束的行号
            end_pos = match.end()
            end_line = content[:end_pos].count('\n') + 1

            comment_text = match.group(1).strip()

            # 判断注释类型
            if comment_text.startswith('*'):
                style = 'doxygen'
                comment_text = comment_text[1:].strip()
            else:
                style = 'block'

            comments[end_line] = (comment_text, style)

        return comments

    def extract_line_comments(self, content: str) -> Dict[int, Tuple[str, str]]:
        """
        提取行注释

        Returns:
            {行号: (注释内容, 注释类型)}
        """
        comments = {}
        lines = content.split('\n')

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('///'):
                comments[i] = (stripped[3:].strip(), 'doxygen')
            elif stripped.startswith('//'):
                comments[i] = (stripped[2:].strip(), 'line')

        return comments

    def get_line_number(self, content: str, pos: int) -> int:
        """根据字符位置获取行号（1-based）"""
        return content[:pos].count('\n') + 1

    def get_column_number(self, content: str, pos: int) -> int:
        """根据字符位置获取列号（1-based）"""
        last_newline = content.rfind('\n', 0, pos)
        if last_newline == -1:
            return pos + 1
        return pos - last_newline

    def find_matching_brace(self, content: str, start: int, open_char: str = '(', close_char: str = ')') -> int:
        """
        查找匹配的括号位置

        Args:
            content: 内容
            start: 开始位置（open_char的位置）
            open_char: 开括号字符
            close_char: 闭括号字符

        Returns:
            匹配的闭括号位置，未找到返回-1
        """
        if start >= len(content) or content[start] != open_char:
            return -1

        depth = 1
        i = start + 1

        while i < len(content) and depth > 0:
            if content[i] == open_char:
                depth += 1
            elif content[i] == close_char:
                depth -= 1
            i += 1

        return i - 1 if depth == 0 else -1

    def preprocess_for_parsing(self, content: str) -> str:
        """
        预处理：移除条件编译块内容（简化处理）

        Args:
            content: 源码内容

        Returns:
            预处理后的内容
        """
        # MVP阶段：简单移除注释即可
        return self.remove_comments(content)
