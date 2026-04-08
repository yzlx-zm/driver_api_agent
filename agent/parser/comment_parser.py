"""注释解析器 - 改进版 v2

支持Doxygen风格和章节分隔符格式注释的正确提取和关联
"""

import re
from typing import Dict, List, Optional, Tuple
from .base import BaseParser
from ..models.ir import Comment, SourceLocation


class CommentParser(BaseParser):
    """注释解析器，支持多种风格"""

    # Doxygen命令模式
    DOXYGEN_PATTERNS = {
        'brief': r'@brief\s+(.+?)(?=@|\*/|\n\s*\n|$)',
        'param': r'@param(?:\[(?:in|out|in,out)\])?\s+(\w+)\s+(.+?)(?=@|\*/|\n\s*\n|$)',
        'return': r'@returns?\s+(.+?)(?=@|\*/|\n\s*\n|$)',
        'note': r'@note\s+(.+?)(?=@|\*/|\n\s*\n|$)',
        'see': r'@see\s+(.+?)(?=@|\*/|\n\s*\n|$)',
        'deprecated': r'@deprecated\s*(.+?)(?=@|\*/|\n\s*\n)?$)',
        'attention': r'@attention\s+(.+?)(?=@|\*/|\n\s*\n)',
        'warning': r'@warning\s+(.+?)(?=@|\*/|\n\s*\n)',
    }

    def __init__(self):
        super().__init__()
        # 注释缓存: {结束行号: 解析后的注释信息}
        self._comment_cache: Dict[int, Dict] = {}
        # 原始内容引用（用于计算行号）
        self._content_ref: str = ""

    def parse(self, content: str, file_path: str) -> List[Comment]:
        """
        解析所有注释

        Args:
            content: 源码内容
            file_path: 文件路径

        Returns:
            注释列表
        """
        comments = []
        self._comment_cache = {}
        self._content_ref = content

        # 解析块注释 /* ... */
        block_comments = self._extract_block_comments(content, file_path)
        comments.extend(block_comments)

        # 解析行注释 /// ... 或 // ...
        line_comments = self._extract_line_comments(content, file_path)
        comments.extend(line_comments)

        return comments

    def _extract_block_comments(self, content: str, file_path: str) -> List[Comment]:
        """提取块注释 /* ... */ 和 /** ... */"""
        comments = []
        # 匹配 /* ... */ 注释块
        pattern = r'/\*(.*?)\*/'

        for match in re.finditer(pattern, content, re.DOTALL):
            comment_text = match.group(1).strip()
            start_pos = match.start()
            end_pos = match.end()

            # 计算注释块的起始行号和结束行号
            start_line = content[:start_pos].count('\n') + 1
            end_line = content[:end_pos].count('\n') + 1

            # 判断注释风格和内容
            style, parsed_text = self._classify_block_comment(comment_text)

            # 跳过纯分隔符注释（如 /*************/）
            if not parsed_text.strip():
                continue

            comment = Comment(
                content=parsed_text,
                style=style,
                location=SourceLocation(file=file_path, line=start_line)
            )

            # 如果是Doxygen风格，解析详细信息
            if style == 'doxygen':
                parsed = self._parse_doxygen(parsed_text)
                comment.brief = parsed.get('brief', '')
                comment.params = parsed.get('params', {})
                comment.returns = parsed.get('return', '')
                comment.notes = parsed.get('notes', [])

            comments.append(comment)

            # 缓存：用注释结束行号作为key
            # 注意：章节分隔符（separator/section 风格）不缓存，
            # 避免被 attach_comments_to_* 错误关联为函数/结构体描述
            if style not in ('separator', 'section'):
                self._comment_cache[end_line] = {
                    'text': parsed_text,
                    'parsed': parsed if style == 'doxygen' else {},
                    'style': style,
                    'start_line': start_line,
                    'end_line': end_line,
                    'brief': comment.brief,
                    'params': comment.params,
                    'returns': comment.returns,
                }

        return comments

    def _classify_block_comment(self, comment_text: str) -> Tuple[str, str]:
        """
        分类块注释并提取有效内容

        Returns:
            (风格, 有效文本)
        """
        lines = comment_text.split('\n')

        # 检查是否是章节分隔符（如 /****************...*** /)
        # 这类注释通常有多行星号，只有一行有效内容
        non_empty_lines = [l.strip() for l in lines if l.strip()]

        # 过滤掉只有星号的行
        content_lines = []
        for line in non_empty_lines:
            # 移除前导和尾随的星号（块注释内部）
            cleaned = line.strip('* ')
            if cleaned:
                content_lines.append(cleaned)

        if not content_lines:
            return ('separator', '')

        # 检查是否是Doxygen风格
        full_text = ' '.join(content_lines)
        if full_text.startswith('*') or '@' in full_text:
            # Doxygen风格
            # 清理前导星号
            cleaned_text = '\n'.join(content_lines)
            return ('doxygen', cleaned_text)

        # 检查是否像章节标题（单行，简短）
        if len(content_lines) == 1 and len(content_lines[0]) < 50:
            return ('section', content_lines[0])

        # 普通块注释
        return ('block', '\n'.join(content_lines))

    def _extract_line_comments(self, content: str, file_path: str) -> List[Comment]:
        """提取行注释 /// ... 或 // ..."""
        comments = []
        lines = content.split('\n')

        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # 检查 /// 风格（Doxygen）
            if stripped.startswith('///'):
                comment_lines = [stripped[3:].strip()]
                start_line = i + 1
                style = 'doxygen'

                # 合并连续的 ///
                while i + 1 < len(lines) and lines[i + 1].strip().startswith('///'):
                    i += 1
                    comment_lines.append(lines[i].strip()[3:].strip())

                comment_text = '\n'.join(comment_lines)
                comment = Comment(
                    content=comment_text,
                    style=style,
                    location=SourceLocation(file=file_path, line=start_line)
                )

                if style == 'doxygen':
                    parsed = self._parse_doxygen(comment_text)
                    comment.brief = parsed.get('brief', '')
                    comment.params = parsed.get('params', {})

                comments.append(comment)

                # 缓存
                self._comment_cache[i + 1] = {
                    'text': comment_text,
                    'parsed': parsed if style == 'doxygen' else {},
                    'style': style,
                    'start_line': start_line,
                    'end_line': i + 1,
                    'brief': comment.brief,
                    'params': comment.params,
                }

            # 普通 // 注释（非Doxygen）
            elif stripped.startswith('//') and not stripped.startswith('///'):
                comment_text = stripped[2:].strip()

                # 跳过章节分隔符（如 // ===== xxx =====）
                if re.match(r'^[=\-*#]{3,}', comment_text) or re.match(r'.*[=\-*#]{3,}$', comment_text):
                    i += 1
                    continue

                comment = Comment(
                    content=comment_text,
                    style='line',
                    location=SourceLocation(file=file_path, line=i + 1)
                )

                comments.append(comment)

                # 缓存
                self._comment_cache[i + 1] = {
                    'text': comment_text,
                    'parsed': {},
                    'style': 'line',
                    'start_line': i + 1,
                    'end_line': i + 1,
                    'brief': '',
                }

            i += 1

        return comments

    def _parse_doxygen(self, comment_text: str) -> Dict:
        """
        解析Doxygen注释

        Args:
            comment_text: 注释文本

        Returns:
            解析后的信息字典
        """
        result = {
            'brief': '',
            'params': {},
            'return': '',
            'notes': [],
            'see': [],
            'deprecated': False,
        }

        # 清理注释内容
        clean_text = comment_text

        # 解析@brief 或 第一段无标签文本作为brief
        match = re.search(r'@brief\s+(.+?)(?=@|\n\s*@|\Z)', clean_text, re.DOTALL)
        if match:
            result['brief'] = match.group(1).strip()
        else:
            # 如果没有@brief，取第一段非标签文本作为brief
            first_para_match = re.search(r'^([^@\n][^\n]*?)(?=\n\s*@|\n\s*\n|\Z)', clean_text, re.DOTALL)
            if first_para_match:
                result['brief'] = first_para_match.group(1).strip()

        # 解析@param
        for match in re.finditer(r'@param(?:\[(?:in|out|in,out)\])?\s+(\w+)\s+(.+?)(?=\n\s*@|\Z)', clean_text, re.DOTALL):
            param_name = match.group(1)
            param_desc = match.group(2).strip()
            result['params'][param_name] = param_desc

        # 解析@return / @returns
        match = re.search(r'@returns?\s+(.+?)(?=\n\s*@|\Z)', clean_text, re.DOTALL)
        if match:
            result['return'] = match.group(1).strip()

        # 解析@note
        for match in re.finditer(r'@note\s+(.+?)(?=\n\s*@|\Z)', clean_text, re.DOTALL):
            result['notes'].append(match.group(1).strip())

        # 解析@see
        for match in re.finditer(r'@see\s+(.+?)(?=\n\s*@|\Z)', clean_text, re.DOTALL):
            result['see'].append(match.group(1).strip())

        # 检测@deprecated
        if '@deprecated' in clean_text:
            result['deprecated'] = True

        return result

    def get_comment_before_line(self, target_line: int, max_lines_before: int = 5) -> Optional[Dict]:
        """
        获取目标行之前最近的注释，并从缓存中移除（防止重复关联）

        Args:
            target_line: 目标行号（1-based）
            max_lines_before: 向前查找的最大行数

        Returns:
            解析后的注释信息，或None
        """
        # 从目标行前一行开始，向前查找最近的注释
        for line_offset in range(1, max_lines_before + 1):
            check_line = target_line - line_offset
            if check_line in self._comment_cache:
                comment_info = self._comment_cache[check_line]
                # 确保注释是紧邻的（中间没有太多空行）
                if target_line - comment_info['end_line'] <= max_lines_before:
                    # 从缓存移除，防止同一条注释被多个元素重复关联
                    del self._comment_cache[check_line]
                    return comment_info

        return None

    def attach_comments_to_functions(self, functions: List, content: str = None) -> None:
        """
        将注释附加到函数上

        Args:
            functions: 函数列表
            content: 源码内容（用于重新计算行号）
        """
        for func in functions:
            func_line = func.location.line

            # 查找函数前的注释
            comment_info = self.get_comment_before_line(func_line)
            if comment_info:
                parsed = comment_info.get('parsed', {})

                # 设置函数描述
                brief = parsed.get('brief', '')
                if brief:
                    func.brief = brief
                    func.description = brief
                    func.details = brief
                elif comment_info.get('text'):
                    # 如果没有解析出brief，使用原始文本
                    text = comment_info.get('text', '')
                    if len(text) < 100:  # 短文本直接作为描述
                        func.brief = text
                        func.description = text

                # 设置返回值描述
                return_desc = parsed.get('return', '')
                if return_desc:
                    func.return_desc = return_desc

                # 设置注意事项
                notes = parsed.get('notes', [])
                if notes:
                    func.notes = notes

                # 设置相关函数
                see_also = parsed.get('see', [])
                if see_also:
                    func.see_also = see_also

                # 附加参数描述
                params_desc = parsed.get('params', {})
                for param in func.params:
                    if param.name in params_desc:
                        param.description = params_desc[param.name]

                # 检测deprecated
                if parsed.get('deprecated', False):
                    func.is_deprecated = True

    def attach_comments_to_structs(self, structs: List) -> None:
        """
        将注释附加到结构体上

        Args:
            structs: 结构体列表
        """
        for struct in structs:
            struct_line = struct.location.line

            comment_info = self.get_comment_before_line(struct_line)
            if comment_info:
                brief = comment_info.get('brief', '')
                text = comment_info.get('text', '')

                if brief:
                    struct.description = brief
                elif text and len(text) < 100:
                    struct.description = text

    def attach_comments_to_enums(self, enums: List) -> None:
        """
        将注释附加到枚举上

        Args:
            enums: 枚举列表
        """
        for enum in enums:
            enum_line = enum.location.line

            comment_info = self.get_comment_before_line(enum_line)
            if comment_info:
                brief = comment_info.get('brief', '')
                text = comment_info.get('text', '')

                if brief:
                    enum.description = brief
                elif text and len(text) < 100:
                    enum.description = text

    def attach_comments_to_macros(self, macros: List) -> None:
        """
        将注释附加到宏定义上

        Args:
            macros: 宏定义列表
        """
        for macro in macros:
            macro_line = macro.location.line

            comment_info = self.get_comment_before_line(macro_line)
            if comment_info:
                brief = comment_info.get('brief', '')
                text = comment_info.get('text', '')

                if brief:
                    macro.description = brief
                elif text and len(text) < 100:
                    macro.description = text
