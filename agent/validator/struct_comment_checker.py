"""结构体注释校验器

检查结构体字段是否有注释说明
"""

from typing import Dict, Any, List
from .base import BaseValidator
from ..models.ir import ModuleIR, Struct, StructField


class StructCommentChecker(BaseValidator):
    """结构体注释校验器

    检查内容：
    1. 结构体是否有描述
    2. 结构体字段是否有注释说明
    """

    @property
    def name(self) -> str:
        return "Struct Comment Checker"

    def __init__(self, config: Dict = None):
        super().__init__(config)
        self.check_struct_desc = self.config.get('check_struct_desc', True)
        self.check_field_comments = self.config.get('check_field_comments', True)
        self.min_field_coverage = self.config.get('min_field_coverage', 80)  # 最低字段注释覆盖率

    def check(self, ir: ModuleIR, **kwargs) -> 'ValidationReport':
        """
        执行结构体注释校验

        Args:
            ir: 模块中间表示

        Returns:
            校验报告
        """
        self.reset()

        for struct in ir.structs:
            self._check_struct(struct)

        return self.report

    def _check_struct(self, struct: Struct):
        """检查单个结构体"""
        # 检查结构体描述
        if self.check_struct_desc:
            if not struct.description or struct.description.strip() == "":
                self._add_warning(
                    f"结构体 '{struct.name}' 缺少描述说明",
                    location=struct.location,
                    code="MISSING_STRUCT_DESC",
                    suggestion="为结构体添加 Doxygen 风格注释说明其用途"
                )

        # 检查字段注释
        if self.check_field_comments:
            self._check_field_comments(struct)

    def _check_field_comments(self, struct: Struct):
        """检查结构体字段注释"""
        if not struct.fields:
            return

        missing_fields: List[str] = []
        placeholder_fields: List[str] = []

        for field in struct.fields:
            if not field.description or field.description.strip() == "":
                missing_fields.append(field.name)
            elif self._is_placeholder(field.description):
                placeholder_fields.append(field.name)

        # 计算覆盖率
        total_fields = len(struct.fields)
        documented_fields = total_fields - len(missing_fields) - len(placeholder_fields)
        coverage = (documented_fields / total_fields * 100) if total_fields > 0 else 100

        # 生成报告
        if missing_fields:
            self._add_warning(
                f"结构体 '{struct.name}' 有 {len(missing_fields)} 个字段缺少注释: {', '.join(missing_fields[:5])}{'...' if len(missing_fields) > 5 else ''}",
                location=struct.location,
                code="MISSING_FIELD_COMMENT",
                suggestion="为字段添加 Doxygen 风格注释（如：/**< 字段说明 */）"
            )

        if placeholder_fields:
            self._add_info(
                f"结构体 '{struct.name}' 有 {len(placeholder_fields)} 个字段使用占位符描述: {', '.join(placeholder_fields[:3])}",
                location=struct.location,
                code="PLACEHOLDER_FIELD_DESC",
                suggestion="完善字段的实际描述"
            )

        # 覆盖率检查
        if coverage < self.min_field_coverage:
            self._add_warning(
                f"结构体 '{struct.name}' 字段注释覆盖率仅为 {coverage:.1f}%，低于最低要求 {self.min_field_coverage}%",
                location=struct.location,
                code="LOW_FIELD_COMMENT_COVERAGE",
                suggestion=f"提高字段注释覆盖率至 {self.min_field_coverage}% 以上"
            )

    def _is_placeholder(self, description: str) -> bool:
        """检查是否是占位符描述"""
        placeholders = [
            "待补充", "待填写", "TODO", "FIXME",
            "TBD", "XXX", "待完成", "..."
        ]
        desc_lower = description.strip().lower()
        return any(p.lower() in desc_lower for p in placeholders)
