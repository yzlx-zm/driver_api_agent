"""签名一致性校验器

检查.h声明和.c定义的函数签名是否一致
"""

from typing import List, Dict, Optional
from .base import BaseValidator
from ..models.ir import (
    Function, Parameter, ParamDirection,
    SourceLocation, ValidationReport, ValidationResult, ModuleIR
)


class SignatureChecker(BaseValidator):
    """签名一致性校验器

    检查内容：
    1. 声明与定义的返回值类型是否一致
    2. 参数数量是否一致
    3. 参数类型是否一致
    4. 参数名称是否一致（警告级别）
    """

    @property
    def name(self) -> str:
        return "Signature Checker"

    def __init__(self, config: Dict = None):
        super().__init__(config)
        self._declarations: List[Function] = []
        self._definitions: List[Function] = []

    def check(self, ir: ModuleIR, **kwargs) -> ValidationReport:
        """
        检查声明与定义的一致性

        Args:
            ir: 模块中间表示
            **kwargs: 额外参数
                - declarations: .h文件中的函数声明
                - definitions: .c文件中的函数定义

        Returns:
            校验报告
        """
        self.reset()

        # 获取声明和定义
        self._declarations = kwargs.get('declarations', [])
        self._definitions = kwargs.get('definitions', [])

        # 如果没有传入，尝试从 IR 获取
        if not self._declarations and hasattr(ir, '_declarations'):
            self._declarations = getattr(ir, '_declarations', [])
        if not self._definitions and hasattr(ir, '_definitions'):
            self._definitions = getattr(ir, '_definitions', [])

        # 构建声明和定义的映射
        decl_map = {f.name: f for f in self._declarations}
        def_map = {f.name: f for f in self._definitions}

        # 1. 检查声明是否有对应定义
        self._check_orphan_declarations(decl_map, def_map)

        # 2. 检查定义是否有对应声明
        self._check_orphan_definitions(decl_map, def_map)

        # 3. 检查签名一致性
        self._check_signature_consistency(decl_map, def_map)

        return self.report

    def _check_orphan_declarations(self, decl_map: Dict[str, Function], def_map: Dict[str, Function]):
        """
        检查只有声明没有定义的函数（可能是extern或inline）
        """
        for name, decl in decl_map.items():
            if name not in def_map:
                # static函数可以没有定义（可能在.h中）
                if not decl.is_static:
                    self._add_info(
                        f"函数 '{name}' 只有声明没有定义（可能是extern函数或inline函数）",
                        location=decl.location,
                        code="ORPHAN_DECL"
                    )

    def _check_orphan_definitions(self, decl_map: Dict[str, Function], def_map: Dict[str, Function]):
        """
        检查只有定义没有声明的函数（可能是static函数）
        """
        for name, defn in def_map.items():
            if name not in decl_map:
                # static函数通常在.c中定义，不需要在.h中声明
                if defn.is_static:
                    self._add_info(
                        f"static函数 '{name}' 没有在头文件中声明（正常情况）",
                        location=defn.location,
                        code="STATIC_NO_DECL"
                    )
                else:
                    self._add_warning(
                        f"函数 '{name}' 有定义但没有声明",
                        location=defn.location,
                        code="MISSING_DECL",
                        suggestion="在头文件中添加函数声明"
                    )

    def _check_signature_consistency(self, decl_map: Dict[str, Function], def_map: Dict[str, Function]):
        """
        检查签名一致性：返回值类型和参数列表
        """
        for name, decl in decl_map.items():
            if name not in def_map:
                continue

            defn = def_map[name]

            # 检查返回值类型
            self._check_return_type(decl, defn)

            # 检查参数列表
            self._check_parameters(decl, defn)

    def _check_return_type(self, decl: Function, defn: Function):
        """检查返回值类型是否一致"""
        decl_return = self._normalize_type(decl.return_type)
        defn_return = self._normalize_type(defn.return_type)

        if decl_return != defn_return:
            self._add_error(
                f"函数 '{decl.name}' 返回值类型不一致: 声明为 '{decl.return_type}', 定义为 '{defn.return_type}'",
                location=decl.location,
                code="RETURN_TYPE_MISMATCH",
                suggestion="统一返回值类型"
            )

    def _check_parameters(self, decl: Function, defn: Function):
        """检查参数列表是否一致"""
        # 参数数量
        if len(decl.params) != len(defn.params):
            self._add_error(
                f"函数 '{decl.name}' 参数数量不一致: 声明有 {len(decl.params)} 个, 定义有 {len(defn.params)} 个",
                location=decl.location,
                code="PARAM_COUNT_MISMATCH",
                suggestion="检查参数列表"
            )
            return

        # 逐个检查参数
        for i, (decl_param, defn_param) in enumerate(zip(decl.params, defn.params)):
            self._check_single_parameter(decl.name, i, decl_param, defn_param, decl.location)

    def _check_single_parameter(self, func_name: str, index: int,
                                 decl_param: Parameter, defn_param: Parameter,
                                 location: SourceLocation):
        """检查单个参数"""
        # 类型检查
        decl_type = self._normalize_type(decl_param.type)
        defn_type = self._normalize_type(defn_param.type)

        if decl_type != defn_type:
            self._add_error(
                f"函数 '{func_name}' 第 {index + 1} 个参数类型不一致: 声明为 '{decl_param.type}', 定义为 '{defn_param.type}'",
                location=location,
                code="PARAM_TYPE_MISMATCH",
                suggestion="统一参数类型"
            )

        # 名称检查（仅警告）
        if decl_param.name != defn_param.name:
            self._add_warning(
                f"函数 '{func_name}' 第 {index + 1} 个参数名称不一致: 声明为 '{decl_param.name}', 定义为 '{defn_param.name}'",
                location=location,
                code="PARAM_NAME_DIFF",
                suggestion="建议统一参数名称以提高可读性"
            )

    def _normalize_type(self, type_str: str) -> str:
        """
        标准化类型字符串用于比较

        移除多余空格，统一格式
        """
        if not type_str:
            return ""

        # 移除多余空格
        normalized = " ".join(type_str.split())

        # 移除指针前后的空格
        normalized = normalized.replace(" *", "*").replace("* ", "*")

        # 统一 const 位置
        if "const" in normalized:
            parts = normalized.split()
            if parts[0] != "const":
                # 将 const 移到前面
                parts = [p for p in parts if p != "const"]
                normalized = "const " + " ".join(parts)

        return normalized
