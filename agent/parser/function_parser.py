"""函数声明解析器"""

import re
from typing import List, Tuple, Optional, Dict, Any
from .base import BaseParser
from ..models.ir import (
    Function, Parameter, ParamDirection,
    SourceLocation, FunctionCategory
)


class FunctionParser(BaseParser):
    """函数声明/定义解析器"""

    # 函数声明正则模式
    # 匹配: [static] [inline] 返回类型 函数名(参数列表);
    FUNC_DECL_PATTERN = re.compile(
        r'''(?mx)
        ^\s*
        (?P<static>static\s+)?
        (?P<inline>inline\s+)?
        (?P<return_type>
            (?:const\s+)?
            (?:unsigned\s+|signed\s+)?
            (?:
                void |
                int | short | long | char | float | double |
                uint\d+_t | int\d+_t | uintptr_t | intptr_t |
                size_t | bool | _Bool |
                \w+(?:\s*\*|\s*\* const|\s*\* const\s*\*)?
            )
        )
        \s+
        (?P<func_name>\w+)
        \s*
        \(
            (?P<params>
                (?:
                    void |
                    (?:
                        (?:
                            (?:const\s+)?
                            (?:unsigned\s+|signed\s+)?
                            (?:
                                void\s*\* |
                                int | short | long | char | float | double |
                                uint\d+_t | int\d+_t | uintptr_t | intptr_t |
                                size_t | bool | _Bool |
                                \w+(?:\s*\*|\s*\* const|\s*\*\*)?
                            )
                            (?:\s*\[\d*\])?  # 可选数组
                            \s+
                            \w+
                            (?:\s*\[\d*\])?  # 可选数组
                        )
                        (?:\s*,\s*[^)]+)*
                    )?
                )
            )?
        \)
        \s*;
        ''',
        re.VERBOSE
    )

    # 更简单的函数匹配模式（用于处理复杂情况）
    SIMPLE_FUNC_PATTERN = re.compile(
        r'''(?mx)
        ^\s*
        (?P<static>static\s+)?
        (?P<inline>inline\s+)?
        (?P<return_type>
            (?:const\s+)?
            (?:unsigned\s+|signed\s+)?
            [\w\s\*]+?
        )
        \s+
        (?P<func_name>\w+)
        \s*
        \(
        '''
    )

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.category_keywords = config.get('category_keywords', {
            "init": ["init", "deinit", "start", "stop", "reset", "open", "close"],
            "query": ["get", "is", "has", "check", "can", "should"],
            "callback": ["callback", "handler", "on_", "_cb", "_cbk"]
        }) if config else {}

    def parse(self, content: str, file_path: str) -> List[Function]:
        """
        解析函数声明

        Args:
            content: 源码内容
            file_path: 文件路径

        Returns:
            函数声明列表
        """
        functions = []
        lines = content.split('\n')

        # 预处理移除注释
        clean_content = self.remove_comments(content)

        # 使用逐行扫描+状态机方式解析
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # 跳过空行和预处理指令
            if not stripped or stripped.startswith('#'):
                i += 1
                continue

            # 尝试匹配函数声明
            func = self._try_parse_function(clean_content, lines, i, file_path)
            if func:
                functions.append(func)

            i += 1

        return functions

    def _try_parse_function(self, clean_content: str, lines: List[str], start_line: int, file_path: str) -> Optional[Function]:
        """
        尝试从指定行解析函数声明

        Args:
            clean_content: 清理后的内容
            lines: 原始行列表
            start_line: 起始行号（0-based）
            file_path: 文件路径

        Returns:
            Function对象或None
        """
        # 合并多行声明
        full_decl = ""
        brace_depth = 0
        has_open_brace = False

        for i in range(start_line, min(start_line + 20, len(lines))):
            line = lines[i].strip()

            # 检查是否是函数体的开始（有花括号）
            if '{' in line and not has_open_brace:
                # 这是函数定义，不是声明
                return None

            full_decl += " " + line

            # 检查括号
            brace_depth += line.count('(') - line.count(')')
            if '(' in line:
                has_open_brace = True

            # 检查是否是声明结束
            if ';' in line and brace_depth == 0:
                break

        full_decl = full_decl.strip()

        # 跳过typedef和结构体定义
        if full_decl.startswith('typedef') or full_decl.startswith('struct'):
            return None

        # 使用正则匹配
        match = self.SIMPLE_FUNC_PATTERN.match(full_decl)
        if not match:
            return None

        func_name = match.group('func_name')
        return_type = match.group('return_type').strip()

        # 跳过常见的非函数模式
        if func_name in ['if', 'while', 'for', 'switch', 'return', 'sizeof']:
            return None

        # 查找参数列表
        paren_start = full_decl.find('(')
        if paren_start == -1:
            return None

        paren_end = self.find_matching_brace(full_decl, paren_start)
        if paren_end == -1:
            return None

        params_str = full_decl[paren_start+1:paren_end].strip()

        # 检查是否是声明（以分号结尾）
        if ';' not in full_decl[paren_end:]:
            return None

        # 解析参数
        params = self._parse_params(params_str, file_path, start_line + 1)

        # 创建函数对象
        func = Function(
            name=func_name,
            return_type=return_type,
            params=params,
            is_static=match.group('static') is not None,
            is_inline=match.group('inline') is not None,
            location=SourceLocation(file=file_path, line=start_line + 1),
            header_file=file_path,
            is_public=match.group('static') is None
        )

        # 猜测函数分类
        func.category = self._guess_category(func_name)

        return func

    def _parse_params(self, params_str: str, file_path: str, line: int) -> List[Parameter]:
        """
        解析参数列表

        Args:
            params_str: 参数列表字符串
            file_path: 文件路径
            line: 行号

        Returns:
            参数列表
        """
        if not params_str or params_str == 'void':
            return []

        params = []

        # 分割参数
        param_parts = self._split_params(params_str)

        for part in param_parts:
            part = part.strip()
            if not part:
                continue

            param = self._parse_single_param(part, file_path, line)
            if param:
                params.append(param)

        return params

    def _split_params(self, params_str: str) -> List[str]:
        """
        分割参数，处理函数指针等复杂情况

        Args:
            params_str: 参数列表字符串

        Returns:
            参数字符串列表
        """
        params = []
        current = ""
        depth = 0

        for char in params_str:
            if char == '(' or char == '[':
                depth += 1
                current += char
            elif char == ')' or char == ']':
                depth -= 1
                current += char
            elif char == ',' and depth == 0:
                params.append(current.strip())
                current = ""
            else:
                current += char

        if current.strip():
            params.append(current.strip())

        return params

    def _parse_single_param(self, param_str: str, file_path: str, line: int) -> Optional[Parameter]:
        """
        解析单个参数

        Args:
            param_str: 参数字符串，如 "const fs5708_param_t *param"
            file_path: 文件路径
            line: 行号

        Returns:
            Parameter对象或None
        """
        param_str = param_str.strip()
        if not param_str:
            return None

        # 检查const
        is_const = 'const' in param_str
        param_str = param_str.replace('const', '').strip()

        # 检查数组
        is_array = '[' in param_str
        array_size = None
        if is_array:
            array_match = re.search(r'\[(\d*)\]', param_str)
            if array_match:
                if array_match.group(1):
                    array_size = int(array_match.group(1))
                param_str = param_str[:param_str.find('[')]

        # 分离类型和名称
        tokens = param_str.split()
        if len(tokens) < 2:
            # 可能是无名称参数（只有类型）
            return Parameter(
                name="",
                type=param_str.strip('* '),
                is_const=is_const,
                is_pointer='*' in param_str,
                is_array=is_array,
                array_size=array_size
            )

        # 最后一个token是名称（可能带*前缀）
        name_with_ptr = tokens[-1]
        type_tokens = tokens[:-1]

        # 处理类型中的指针
        ptr_count = name_with_ptr.count('*')
        name = name_with_ptr.replace('*', '').strip()
        type_str = ' '.join(type_tokens)

        # 不在 type_str 中加 *，is_pointer + to_decl() 会处理显示

        # 推断参数方向（传 ptr_count 因为 type_str 不再含 *）
        direction = self._infer_param_direction(type_str, name, is_const, ptr_count)

        return Parameter(
            name=name,
            type=type_str.strip(),
            direction=direction,
            is_const=is_const,
            is_pointer='*' in param_str or ptr_count > 0,
            is_array=is_array,
            array_size=array_size
        )

    def _infer_param_direction(self, type_str: str, name: str, is_const: bool, ptr_count: int = 0) -> ParamDirection:
        """
        推断参数方向

        Args:
            type_str: 类型字符串
            name: 参数名
            is_const: 是否为const
            ptr_count: 指针级数

        Returns:
            参数方向
        """
        # 指针类型
        if '*' in type_str or ptr_count > 0:
            if is_const:
                return ParamDirection.IN
            else:
                # 非const指针可能是OUT或INOUT
                if any(kw in name.lower() for kw in ['out', 'result', 'ret', 'buf', 'data']):
                    return ParamDirection.OUT
                return ParamDirection.INOUT

        return ParamDirection.IN

    def _guess_category(self, func_name: str) -> FunctionCategory:
        """根据函数名猜测分类"""
        name_lower = func_name.lower()

        for category, keywords in self.category_keywords.items():
            for kw in keywords:
                if kw in name_lower:
                    if category == "init":
                        return FunctionCategory.INIT
                    elif category == "query":
                        return FunctionCategory.QUERY
                    elif category == "callback":
                        return FunctionCategory.CALLBACK

        return FunctionCategory.BUSINESS

    def parse_definitions(self, content: str, file_path: str) -> List[Function]:
        """
        从 .c 文件中提取函数定义（带函数体）的签名

        与 parse() 不同，此方法提取的是实际的函数实现定义，
        而非前向声明。

        Args:
            content: 源码内容
            file_path: 文件路径

        Returns:
            函数定义列表
        """
        functions = []
        clean_content = self.remove_comments(content)
        lines = clean_content.split('\n')

        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # 跳过空行、预处理指令、typedef、struct
            if not stripped or stripped.startswith('#') or stripped.startswith('typedef') or stripped.startswith('struct'):
                i += 1
                continue

            # 尝试匹配函数定义
            func = self._try_parse_definition(clean_content, lines, i, file_path)
            if func:
                functions.append(func)

            i += 1

        return functions

    def _try_parse_definition(self, clean_content: str, lines: List[str],
                               start_line: int, file_path: str) -> Optional[Function]:
        """
        尝试从指定行解析函数定义（以 { 开头函数体的）

        与 _try_parse_function 的区别：
        - 函数声明以 ; 结尾 → _try_parse_function
        - 函数定义以 { 开头函数体 → _try_parse_definition
        """
        # 合并多行声明
        full_decl = ""
        paren_depth = 0
        has_open_paren = False

        for i in range(start_line, min(start_line + 20, len(lines))):
            line = lines[i].strip()

            full_decl += " " + line

            paren_depth += line.count('(') - line.count(')')
            if '(' in line:
                has_open_paren = True

            # 括号平衡后检查后续字符
            if has_open_paren and paren_depth <= 0:
                # 检查 ) 后面是否跟着 {（函数定义）而非 ;（声明）
                after_close = full_decl[full_decl.rfind(')') + 1:].strip()
                if after_close.startswith('{') or after_close == '':
                    # 可能是函数定义，继续检查下一行
                    if i + 1 < len(lines):
                        next_stripped = lines[i + 1].strip()
                        if next_stripped.startswith('{') or after_close.startswith('{'):
                            # 这是一个函数定义
                            break
                    if after_close.startswith('{'):
                        break
                elif ';' in after_close:
                    # 这是函数声明，不是定义
                    return None
                else:
                    return None

        full_decl = full_decl.strip()

        # 跳过非函数模式
        if full_decl.startswith('typedef') or full_decl.startswith('struct'):
            return None

        # 使用正则匹配
        match = self.SIMPLE_FUNC_PATTERN.match(full_decl)
        if not match:
            return None

        func_name = match.group('func_name')
        return_type = match.group('return_type').strip()

        # 跳过非函数关键词
        if func_name in ['if', 'while', 'for', 'switch', 'return', 'sizeof']:
            return None

        # 查找参数列表
        paren_start = full_decl.find('(')
        if paren_start == -1:
            return None

        paren_end = self.find_matching_brace(full_decl, paren_start)
        if paren_end == -1:
            return None

        params_str = full_decl[paren_start + 1:paren_end].strip()

        # 检查是否是函数定义（不是声明）
        after_params = full_decl[paren_end + 1:].strip()
        if after_params.startswith(';'):
            return None  # 这是声明，不是定义
        # 函数定义：) 后面可能是 { 或换行后的 {

        # 解析参数
        params = self._parse_params(params_str, file_path, start_line + 1)

        # 创建函数对象
        func = Function(
            name=func_name,
            return_type=return_type,
            params=params,
            is_static=match.group('static') is not None,
            is_inline=match.group('inline') is not None,
            location=SourceLocation(file=file_path, line=start_line + 1),
            header_file=file_path,
            source_file=file_path,
            implementation_line=start_line + 1,
            is_public=match.group('static') is None,
        )

        # 猜测函数分类
        func.category = self._guess_category(func_name)

        return func
