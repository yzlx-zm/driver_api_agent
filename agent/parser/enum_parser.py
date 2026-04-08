"""枚举解析器 - 改进版 v2

支持行尾注释提取
"""

import re
from typing import List, Optional, Dict, Any
from .base import BaseParser
from ..models.ir import Enum, EnumValue, SourceLocation


class EnumParser(BaseParser):
    """枚举类型解析器"""

    # 匹配 typedef enum { ... } name;
    TYPEDEF_ENUM_PATTERN = re.compile(
        r'''(?mxs)
        typedef\s+
        enum
        \s*
        (?:\w+)?  # 可选的enum标签
        \s*
        (?:\:\s*\w+\s*)?  # 可选的底层类型 (C++)
        \s*
        \{
            (?P<values>.*?)
        \}
        \s*
        (?P<name>\w+)
        \s*;
        '''
    )

    # 匹配 enum name { ... };
    NAMED_ENUM_PATTERN = re.compile(
        r'''(?mxs)
        enum
        \s+
        (?P<name>\w+)
        \s*
        (?:\:\s*\w+\s*)?  # 可选的底层类型
        \s*
        \{
            (?P<values>.*?)
        \}
        \s*;
        '''
    )

    def __init__(self):
        super().__init__()

    def parse(self, content: str, file_path: str) -> List[Enum]:
        """
        解析枚举定义

        Args:
            content: 源码内容
            file_path: 文件路径

        Returns:
            枚举列表
        """
        enums = []

        # 解析typedef枚举
        for match in self.TYPEDEF_ENUM_PATTERN.finditer(content):
                name = match.group('name')
                values_str = match.group('values')
                enum_start_pos = match.start()

                values = self._parse_values_with_comments(content, values_str, enum_start_pos, file_path)

                line = self.get_line_number(content, match.start())
                enum = Enum(
                    name=name,
                    values=values,
                    is_typedef=True,
                    typedef_name=name,
                    location=SourceLocation(file=file_path, line=line),
                    header_file=file_path
                )
                enums.append(enum)

        # 解析命名枚举
        for match in self.NAMED_ENUM_PATTERN.finditer(content):
            name = match.group('name')
            values_str = match.group('values')
            enum_start_pos = match.start()

            # 检查是否已经被typedef解析过
            if any(e.name == name or e.typedef_name == name for e in enums):
                continue

            values = self._parse_values_with_comments(content, values_str, enum_start_pos, file_path)

            line = self.get_line_number(content, match.start())

            enum = Enum(
                name=name,
                values=values,
                location=SourceLocation(file=file_path, line=line),
                header_file=file_path
            )
            enums.append(enum)

        return enums

    def _parse_values_with_comments(self, content: str, values_str: str, enum_start_pos: int, file_path: str) -> List[EnumValue]:
        """
        解析枚举值列表，包括行尾注释

        Args:
            content: 完整源码内容
            values_str: 枚举值字符串
            enum_start_pos: 枚举块在源码中的起始位置
            file_path: 文件路径

        Returns:
            枚举值列表
        """
        values = []
        current_value = 0  # 默认从0开始

        # 按行分割
        lines = values_str.split('\n')

        # 计算枚举块开始的行号
        enum_start_line = content[:enum_start_pos].count('\n') + 1

        for line_idx, line in enumerate(lines):
            original_line = line  # 保留原始行用于计算位置
            line = line.strip()

            if not line:
                continue

            # 提取行尾注释 //
            comment = ""
            if '//' in line:
                comment_pos = line.find('//')
                comment = line[comment_pos+2:].strip()
                line = line[:comment_pos].strip()

            # 提取行尾注释 /* ... */（块注释风格的单行注释）
            if '/*' in line and '*/' in line:
                start = line.find('/*')
                end = line.rfind('*/')
                if start < end:
                    comment = line[start+2:end].strip()
                    line = line[:start].strip() + line[end+2:]

            # 移除末尾逗号
            if line.endswith(','):
                line = line[:-1].strip()

            if not line:
                continue

            # 解析枚举项
            if '=' in line:
                parts = line.split('=', 1)
                name = parts[0].strip()
                value_str = parts[1].strip()

                # 解析值
                try:
                    if value_str.startswith('0x') or value_str.startswith('0X'):
                        current_value = int(value_str, 16)
                    elif value_str.startswith('0b') or value_str.startswith('0B'):
                        current_value = int(value_str, 2)
                    elif value_str.startswith('0') and len(value_str) > 1 and value_str[1].isdigit():
                        current_value = int(value_str, 8)
                    else:
                        # 移除可能的类型后缀 (如 U, UL, LL)
                        clean_value = value_str.rstrip('UULLlu')
                        current_value = int(clean_value)
                except ValueError:
                    # 可能是表达式，暂不处理，保持当前值
                    pass
            else:
                name = line

            # 验证名称
            if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', name):
                continue

            # 计算绝对行号（1-based）
            abs_line = enum_start_line + line_idx + 1

            enum_value = EnumValue(
                name=name,
                value=current_value,
                description=comment,  # 使用行尾注释作为描述
                location=SourceLocation(file=file_path, line=abs_line)
            )
            values.append(enum_value)

            # 更新下一个默认值
            current_value += 1

        return values

    def get_line_number(self, content: str, pos: int) -> int:
        """根据位置获取行号（1-based）"""
        return content[:pos].count('\n') + 1
