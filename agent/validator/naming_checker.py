"""命名规范校验器

检查函数、变量、宏等的命名是否符合规范
"""

import re
from typing import Dict, Any, List, Set
from .base import BaseValidator
from ..models.ir import ModuleIR, Function, Macro, Enum, EnumValue


class NamingChecker(BaseValidator):
    """命名规范校验器

    检查内容：
    1. 函数名前缀检查
    2. 宏名前缀检查
    3. snake_case 命名检查
    4. 枚举值命名检查
    """

    @property
    def name(self) -> str:
        return "Naming Convention Checker"

    # 命名模式
    SNAKE_CASE_PATTERN = re.compile(r'^[a-z][a-z0-9_]*$')
    UPPER_SNAKE_CASE_PATTERN = re.compile(r'^[A-Z][A-Z0-9_]*$')
    CAMEL_CASE_PATTERN = re.compile(r'^[a-z][a-zA-Z0-9]*$')
    PASCAL_CASE_PATTERN = re.compile(r'^[A-Z][a-zA-Z0-9]*$')

    def __init__(self, config: Dict = None):
        super().__init__(config)
        # 前缀配置
        self.function_prefix = self.config.get('function_prefix', '')
        self.macro_prefix = self.config.get('macro_prefix', '')
        self.enum_prefix = self.config.get('enum_prefix', '')
        self.struct_prefix = self.config.get('struct_prefix', '')

        # 命名风格配置
        self.require_snake_case = self.config.get('snake_case', True)
        self.require_enum_uppercase = self.config.get('enum_uppercase', True)

        # 允许的特殊名称（如 main, init 等）
        self.allowed_names: Set[str] = set(self.config.get('allowed_names', [
            'main', 'init', 'deinit', 'exit', 'abort',
            'malloc', 'free', 'calloc', 'realloc'
        ]))

    def check(self, ir: ModuleIR, **kwargs) -> 'ValidationReport':
        """
        执行命名规范校验

        Args:
            ir: 模块中间表示

        Returns:
            校验报告
        """
        self.reset()

        # 检查函数命名
        for func in ir.functions:
            self._check_function_naming(func)

        # 检查宏命名
        for macro in ir.macros:
            self._check_macro_naming(macro)

        # 检查枚举命名
        for enum in ir.enums:
            self._check_enum_naming(enum)

        # 检查结构体命名
        for struct in ir.structs:
            self._check_struct_naming(struct)

        return self.report

    def _check_function_naming(self, func: Function):
        """检查函数命名"""
        name = func.name

        # 跳过允许的特殊名称
        if name in self.allowed_names:
            return

        # 检查前缀
        if self.function_prefix and not name.startswith(self.function_prefix):
            self._add_info(
                f"函数 '{name}' 不符合命名前缀规范，应以 '{self.function_prefix}' 开头",
                location=func.location,
                code="FUNCTION_PREFIX_MISMATCH",
                suggestion=f"重命名为 {self.function_prefix}{name}"
            )

        # 检查 snake_case
        if self.require_snake_case and not self.SNAKE_CASE_PATTERN.match(name):
            self._add_info(
                f"函数 '{name}' 不符合 snake_case 命名规范",
                location=func.location,
                code="FUNCTION_NAMING_STYLE",
                suggestion="使用小写字母和下划线，如：function_name"
            )

    def _check_macro_naming(self, macro: Macro):
        """检查宏命名"""
        name = macro.name

        # 检查前缀
        if self.macro_prefix and not name.startswith(self.macro_prefix):
            self._add_info(
                f"宏 '{name}' 不符合命名前缀规范，应以 '{self.macro_prefix}' 开头",
                location=macro.location,
                code="MACRO_PREFIX_MISMATCH",
                suggestion=f"重命名为 {self.macro_prefix}{name}"
            )

        # 宏通常应该全大写
        if not self.UPPER_SNAKE_CASE_PATTERN.match(name):
            # 某些宏函数可能是小写的（如 min, max）
            if not macro.is_function_like or not self.CAMEL_CASE_PATTERN.match(name):
                self._add_info(
                    f"宏 '{name}' 不符合全大写命名规范",
                    location=macro.location,
                    code="MACRO_NAMING_STYLE",
                    suggestion="宏名应使用大写字母和下划线，如：MACRO_NAME"
                )

    def _check_enum_naming(self, enum: Enum):
        """检查枚举命名"""
        name = enum.name or enum.typedef_name
        if not name:
            return

        # 检查前缀
        if self.enum_prefix and not name.startswith(self.enum_prefix):
            self._add_info(
                f"枚举 '{name}' 不符合命名前缀规范，应以 '{self.enum_prefix}' 开头",
                location=enum.location,
                code="ENUM_PREFIX_MISMATCH",
                suggestion=f"重命名为 {self.enum_prefix}{name}"
            )

        # 检查枚举值
        self._check_enum_values(enum)

    def _check_enum_values(self, enum: Enum):
        """检查枚举值命名"""
        if not enum.values:
            return

        # 尝试推断前缀
        if enum.values:
            first_value = enum.values[0].name
            # 推断公共前缀（如 FS5708_STATE_）
            inferred_prefix = self._infer_common_prefix([v.name for v in enum.values])

            for value in enum.values:
                if self.require_enum_uppercase:
                    if not self.UPPER_SNAKE_CASE_PATTERN.match(value.name):
                        self._add_info(
                            f"枚举值 '{value.name}' 不符合全大写命名规范",
                            location=value.location,
                            code="ENUM_VALUE_NAMING_STYLE",
                            suggestion="枚举值应使用大写字母和下划线"
                        )

    def _check_struct_naming(self, struct):
        """检查结构体命名"""
        name = struct.name or struct.typedef_name
        if not name:
            return

        # 检查前缀
        if self.struct_prefix and not name.startswith(self.struct_prefix):
            self._add_info(
                f"结构体 '{name}' 不符合命名前缀规范，应以 '{self.struct_prefix}' 开头",
                location=struct.location,
                code="STRUCT_PREFIX_MISMATCH",
                suggestion=f"重命名为 {self.struct_prefix}{name}"
            )

        # 结构体通常使用 snake_case_t 后缀
        if not name.endswith('_t') and struct.is_typedef:
            self._add_info(
                f"typedef 结构体 '{name}' 建议使用 '_t' 后缀",
                location=struct.location,
                code="STRUCT_TYPEDEF_SUFFIX",
                suggestion="按照 C 惯例，typedef 结构体应以 '_t' 结尾"
            )

    def _infer_common_prefix(self, names: List[str]) -> str:
        """推断名称列表的公共前缀"""
        if not names:
            return ""

        first = names[0]
        for i, char in enumerate(first):
            if not all(name[i] == char if i < len(name) else False for name in names):
                return first[:i]

        return first
