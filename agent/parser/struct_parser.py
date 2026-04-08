"""结构体解析器"""

import re
from typing import List, Optional, Dict, Any
from .base import BaseParser
from ..models.ir import Struct, StructField, SourceLocation


class StructParser(BaseParser):
    """结构体/联合体解析器"""

    # 用于快速定位 typedef struct/union 开头的正则
    TYPEDEF_START_PATTERN = re.compile(
        r'''(?mx)
        typedef\s+
        (?P<type>struct|union)
        \s*
        (?:\w+\s*)?  # 可选的struct标签
        \{
        '''
    )

    # 用于快速定位命名 struct/union 开头的正则
    NAMED_START_PATTERN = re.compile(
        r'''(?mx)
        (?P<type>struct|union)
        \s+
        (?P<name>\w+)
        \s*
        \{
        '''
    )

    def parse(self, content: str, file_path: str) -> List[Struct]:
        """
        解析结构体定义

        Args:
            content: 源码内容
            file_path: 文件路径

        Returns:
            结构体列表
        """
        structs = []
        clean_content = self.remove_comments(content)

        # 解析typedef结构体（使用花括号计数处理嵌套）
        for match in self.TYPEDEF_START_PATTERN.finditer(clean_content):
            struct_type = match.group('type')
            open_brace_pos = match.end() - 1  # { 的位置

            # 用花括号计数找到匹配的 }
            close_pos = self._find_matching_brace(clean_content, open_brace_pos)
            if close_pos == -1:
                continue

            # 提取 } 后面的名称
            after_brace = clean_content[close_pos + 1:].lstrip()
            name_match = re.match(r'(\w+)\s*;', after_brace)
            if not name_match:
                continue
            name = name_match.group(1)

            # 计算行号范围
            line = self.get_line_number(clean_content, match.start())
            end_line = self.get_line_number(clean_content, close_pos)

            # 从原始内容提取字段文本（保留注释）
            original_fields_str = self._extract_lines_range(content, line, end_line)
            brace_start = original_fields_str.find('{')
            brace_end = original_fields_str.rfind('}')
            if brace_start != -1 and brace_end != -1:
                original_fields_str = original_fields_str[brace_start + 1:brace_end]

            fields = self._parse_fields(original_fields_str, file_path)

            struct = Struct(
                name=name,
                fields=fields,
                is_typedef=True,
                typedef_name=name,
                is_union=(struct_type == 'union'),
                location=SourceLocation(file=file_path, line=line),
                header_file=file_path
            )
            structs.append(struct)

        # 解析命名结构体
        seen_names = {s.name for s in structs}
        seen_names.update(s.typedef_name for s in structs if s.typedef_name)
        for match in self.NAMED_START_PATTERN.finditer(clean_content):
            struct_type = match.group('type')
            name = match.group('name')

            if name in seen_names:
                continue

            open_brace_pos = match.end() - 1
            close_pos = self._find_matching_brace(clean_content, open_brace_pos)
            if close_pos == -1:
                continue

            line = self.get_line_number(clean_content, match.start())
            end_line = self.get_line_number(clean_content, close_pos)

            original_fields_str = self._extract_lines_range(content, line, end_line)
            brace_start = original_fields_str.find('{')
            brace_end = original_fields_str.rfind('}')
            if brace_start != -1 and brace_end != -1:
                original_fields_str = original_fields_str[brace_start + 1:brace_end]

            fields = self._parse_fields(original_fields_str, file_path)

            struct = Struct(
                name=name,
                fields=fields,
                is_union=(struct_type == 'union'),
                location=SourceLocation(file=file_path, line=line),
                header_file=file_path
            )
            structs.append(struct)
            seen_names.add(name)

        return structs

    def _find_matching_brace(self, content: str, start: int) -> int:
        """
        找到与 start 位置的 { 匹配的 } 位置（处理嵌套）

        Args:
            content: 文本内容
            start: { 的位置

        Returns:
            匹配的 } 位置，未找到返回 -1
        """
        if start >= len(content) or content[start] != '{':
            return -1

        depth = 1
        i = start + 1
        while i < len(content) and depth > 0:
            if content[i] == '{':
                depth += 1
            elif content[i] == '}':
                depth -= 1
            i += 1

        return i - 1 if depth == 0 else -1

    def _extract_lines_range(self, content: str, start_line: int, end_line: int) -> str:
        """从原始内容中按行范围提取文本（保留注释）"""
        lines = content.split('\n')
        # start_line 和 end_line 都是 1-based
        selected = lines[start_line - 1:end_line]
        return '\n'.join(selected)

    def _parse_fields(self, fields_str: str, file_path: str) -> List[StructField]:
        """
        解析结构体字段

        Args:
            fields_str: 字段定义字符串（可能包含行尾注释）
            file_path: 文件路径

        Returns:
            字段列表
        """
        fields = []

        # 按行处理，每行独立提取注释
        current_decl = ""
        last_comment = ""  # 保留最后一个有效注释
        brace_depth = 0

        for line in fields_str.split('\n'):
            line = line.strip()
            if not line or line.startswith('//'):
                continue

            # 追踪花括号深度
            brace_depth += line.count('{') - line.count('}')

            # 提取当前行的行尾注释
            line_comment = ""
            code_part = line
            comment_match = re.search(r'//\s*(.+)$', line)
            if comment_match:
                line_comment = comment_match.group(1).strip()
                code_part = line[:comment_match.start()].strip()
            else:
                block_comment_match = re.search(r'/\*\s*(.*?)\s*\*/', line)
                if block_comment_match:
                    line_comment = block_comment_match.group(1).strip()
                    code_part = line[:block_comment_match.start()].strip()

            # 累积代码部分（不含注释），避免内层注释干扰外层解析
            current_decl += " " + code_part

            # 记住最近的注释（可能是外层字段的描述）
            if line_comment:
                last_comment = line_comment

            # 当括号平衡且包含分号时，表示一个完整的字段声明
            if brace_depth <= 0 and ';' in code_part:
                decl = current_decl.strip()
                current_decl = ""
                brace_depth = 0

                if decl:
                    field = self._parse_single_field(decl, file_path)
                    if field:
                        # 如果字段本身没有描述，使用最近的注释
                        if not field.description and last_comment:
                            field.description = last_comment
                        fields.append(field)
                    last_comment = ""

        # 处理剩余内容
        if current_decl.strip():
            decl = current_decl.strip()
            field = self._parse_single_field(decl, file_path)
            if field:
                if not field.description and last_comment:
                    field.description = last_comment
                fields.append(field)

        return fields

    def _parse_single_field(self, decl: str, file_path: str) -> Optional[StructField]:
        """
        解析单个字段声明

        Args:
            decl: 字段声明字符串，如 "uint8_t admin; // 0=普通用户，1=管理员"

        Returns:
            StructField对象或None
        """
        decl = decl.strip()
        if not decl:
            return None

        # 1. 先提取行尾注释（在移除分号之前）
        # 注意：decl 可能是多行累积的（如匿名联合体），注释只取到行尾而非整个字符串尾
        comment = ""
        comment_match = re.search(r'//\s*([^\n]+)', decl)
        if comment_match:
            comment = comment_match.group(1).strip()
            decl = decl[:comment_match.start()].strip()
        else:
            comment_match = re.search(r'/\*\s*(.*?)\s*\*/', decl)
            if comment_match:
                comment = comment_match.group(1).strip()
                decl = decl[:comment_match.start()].strip()

        # 2. 移除末尾分号
        decl = decl.rstrip(';').strip()
        if not decl:
            return None

        # 3. 处理匿名联合体/结构体字段: union { ... } name; 或 struct { ... } name;
        # 注意：内层注释已在 _parse_fields 中剥离，decl 中不含注释
        anon_match = re.match(r'(struct|union)\s*\{(.*)\}\s*(\w+)\s*$', decl, re.DOTALL)
        if anon_match:
            anon_type = anon_match.group(1)  # 'struct' or 'union'
            inner_content = anon_match.group(2).strip()
            name = anon_match.group(3)

            # 提取内层字段列表作为参考信息
            inner_fields = []
            for inner_line in inner_content.split(';'):
                inner_line = inner_line.strip()
                if inner_line and not inner_line.startswith('//'):
                    inner_tokens = inner_line.split()
                    if len(inner_tokens) >= 2:
                        inner_name = inner_tokens[-1].replace('*', '').strip()
                        inner_type = ' '.join(inner_tokens[:-1])
                        if inner_name and re.match(r'^\w+$', inner_name):
                            inner_fields.append(f'{inner_type} {inner_name}')

            inner_summary = ', '.join(inner_fields[:5])
            if len(inner_fields) > 5:
                inner_summary += f' ... ({len(inner_fields)} fields)'

            return StructField(
                name=name,
                type=f'{anon_type} {{ {inner_summary} }}',
                description=comment,
                location=SourceLocation(file=file_path)
            )

        # 检查const
        is_const = 'const' in decl
        decl = decl.replace('const', '').strip()

        # 检查volatile
        is_volatile = 'volatile' in decl
        decl = decl.replace('volatile', '').strip()

        # 检查数组
        is_array = '[' in decl
        array_size = None
        array_match = re.search(r'\[(\d*)\]', decl)
        if array_match:
            if array_match.group(1):
                array_size = int(array_match.group(1))
            decl = decl[:decl.find('[')]

        # 检查位域
        bit_field = None
        bit_match = re.search(r':\s*(\d+)', decl)
        if bit_match:
            bit_field = int(bit_match.group(1))
            decl = decl[:bit_match.start()]

        # 分离类型和名称
        tokens = decl.split()
        if len(tokens) < 2:
            return None

        # 处理指针
        name_with_ptr = tokens[-1]
        type_tokens = tokens[:-1]

        ptr_count = name_with_ptr.count('*')
        name = name_with_ptr.replace('*', '').strip()
        type_str = ' '.join(type_tokens)

        if is_volatile:
            type_str = 'volatile ' + type_str
        if ptr_count > 0:
            type_str += ' ' + '*' * ptr_count

        return StructField(
            name=name,
            type=type_str.strip(),
            description=comment,
            is_const=is_const,
            is_pointer=ptr_count > 0,
            is_array=is_array,
            array_size=array_size,
            bit_field=bit_field,
            location=SourceLocation(file=file_path)
        )
