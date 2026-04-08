"""文档覆盖率校验器

检查函数、结构体等的文档覆盖率
"""

from typing import Dict, Any, List
from .base import BaseValidator
from ..models.ir import ModuleIR, Function


class CoverageChecker(BaseValidator):
    """文档覆盖率校验器

    检查内容：
    1. 函数描述覆盖率
    2. 参数文档覆盖率
    3. 返回值文档覆盖率
    4. 结构体字段文档覆盖率
    """

    @property
    def name(self) -> str:
        return "Documentation Coverage Checker"

    def __init__(self, config: Dict = None):
        super().__init__(config)
        # 覆盖率阈值配置
        self.min_function_desc_coverage = self.config.get('min_function_desc', 80)
        self.min_param_doc_coverage = self.config.get('min_param_doc', 60)
        self.min_return_doc_coverage = self.config.get('min_return_doc', 50)
        self.min_struct_field_coverage = self.config.get('min_struct_field', 80)

        # 排除配置
        self.exclude_static = self.config.get('exclude_static', True)
        self.exclude_internal = self.config.get('exclude_internal', True)

    def check(self, ir: ModuleIR, **kwargs) -> 'ValidationReport':
        """
        执行文档覆盖率校验

        Args:
            ir: 模块中间表示

        Returns:
            校验报告
        """
        self.reset()

        # 获取要检查的函数列表
        functions = self._get_target_functions(ir)

        # 检查函数文档覆盖率
        self._check_function_coverage(functions)

        # 检查结构体字段覆盖率
        self._check_struct_coverage(ir)

        # 生成覆盖率报告
        self._generate_coverage_summary(ir, functions)

        return self.report

    def _get_target_functions(self, ir: ModuleIR) -> List[Function]:
        """获取需要检查的函数列表"""
        functions = []
        for func in ir.functions:
            # 排除 static 函数
            if self.exclude_static and func.is_static:
                continue
            # 排除内部函数（以 _ 开头）
            if self.exclude_internal and func.name.startswith('_'):
                continue
            functions.append(func)
        return functions

    def _check_function_coverage(self, functions: List[Function]):
        """检查函数文档覆盖率"""
        if not functions:
            return

        total = len(functions)
        has_desc = 0
        has_params_doc = 0
        has_return_doc = 0

        missing_desc: List[str] = []
        missing_params: List[str] = []
        missing_return: List[str] = []

        for func in functions:
            # 检查函数描述
            if func.description and func.description.strip():
                has_desc += 1
            elif func.brief and func.brief.strip():
                has_desc += 1
            else:
                missing_desc.append(func.name)

            # 检查参数文档
            if func.params:
                all_params_documented = all(
                    p.description and p.description.strip()
                    for p in func.params
                )
                if all_params_documented:
                    has_params_doc += 1
                else:
                    missing_params.append(func.name)
            else:
                # 无参数的函数视为已文档化
                has_params_doc += 1

            # 检查返回值文档
            if func.return_type == 'void':
                # void 返回值不需要文档
                has_return_doc += 1
            elif func.return_desc and func.return_desc.strip():
                has_return_doc += 1
            else:
                missing_return.append(func.name)

        # 计算覆盖率
        desc_coverage = (has_desc / total * 100) if total > 0 else 100
        params_coverage = (has_params_doc / total * 100) if total > 0 else 100
        return_coverage = (has_return_doc / total * 100) if total > 0 else 100

        # 检查是否低于阈值
        if desc_coverage < self.min_function_desc_coverage:
            self._add_warning(
                f"函数描述覆盖率为 {desc_coverage:.1f}%，低于最低要求 {self.min_function_desc_coverage}%",
                code="LOW_FUNCTION_DESC_COVERAGE",
                suggestion=f"为以下函数添加描述: {', '.join(missing_desc[:5])}{'...' if len(missing_desc) > 5 else ''}"
            )

        if params_coverage < self.min_param_doc_coverage:
            self._add_warning(
                f"参数文档覆盖率为 {params_coverage:.1f}%，低于最低要求 {self.min_param_doc_coverage}%",
                code="LOW_PARAM_DOC_COVERAGE",
                suggestion=f"为以下函数的参数添加文档: {', '.join(missing_params[:5])}{'...' if len(missing_params) > 5 else ''}"
            )

        if return_coverage < self.min_return_doc_coverage:
            self._add_warning(
                f"返回值文档覆盖率为 {return_coverage:.1f}%，低于最低要求 {self.min_return_doc_coverage}%",
                code="LOW_RETURN_DOC_COVERAGE",
                suggestion=f"为以下函数的返回值添加说明: {', '.join(missing_return[:5])}{'...' if len(missing_return) > 5 else ''}"
            )

    def _check_struct_coverage(self, ir: ModuleIR):
        """检查结构体字段文档覆盖率"""
        if not ir.structs:
            return

        for struct in ir.structs:
            if not struct.fields:
                continue

            total_fields = len(struct.fields)
            documented_fields = sum(
                1 for f in struct.fields
                if f.description and f.description.strip() and not self._is_placeholder(f.description)
            )

            coverage = (documented_fields / total_fields * 100) if total_fields > 0 else 100

            if coverage < self.min_struct_field_coverage:
                self._add_warning(
                    f"结构体 '{struct.name}' 字段文档覆盖率为 {coverage:.1f}%，低于最低要求 {self.min_struct_field_coverage}%",
                    location=struct.location,
                    code="LOW_STRUCT_FIELD_COVERAGE",
                    suggestion="为结构体字段添加注释说明"
                )

    def _is_placeholder(self, description: str) -> bool:
        """检查是否是占位符描述"""
        placeholders = ["待补充", "待填写", "TODO", "FIXME", "TBD", "XXX", "待完成", "..."]
        desc_lower = description.strip().lower()
        return any(p.lower() in desc_lower for p in placeholders)

    def _generate_coverage_summary(self, ir: ModuleIR, functions: List[Function]):
        """生成覆盖率摘要信息"""
        if not functions:
            self._add_info("没有公开函数需要检查文档覆盖率", code="NO_PUBLIC_FUNCTIONS")
            return

        # 计算总体覆盖率
        total = len(functions)
        documented = sum(
            1 for f in functions
            if f.description and f.description.strip()
        )
        coverage = (documented / total * 100) if total > 0 else 100

        self._add_info(
            f"文档覆盖率统计: {documented}/{total} 函数有描述 ({coverage:.1f}%)",
            code="COVERAGE_SUMMARY"
        )
