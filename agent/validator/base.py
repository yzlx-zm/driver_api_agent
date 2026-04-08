"""校验器基类

定义统一的校验器接口
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from ..models.ir import ModuleIR, ValidationReport, ValidationResult


class BaseValidator(ABC):
    """校验器基类

    所有校验器都应该继承此类并实现 check 方法
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化校验器

        Args:
            config: 校验器配置
        """
        self.config = config or {}
        self._report: Optional[ValidationReport] = None

    @property
    @abstractmethod
    def name(self) -> str:
        """校验器名称"""
        pass

    @property
    def enabled(self) -> bool:
        """是否启用（从配置读取）"""
        return self.config.get('enabled', True)

    @property
    def report(self) -> ValidationReport:
        """获取当前校验报告"""
        if self._report is None:
            self._report = self._create_report()
        return self._report

    def _create_report(self, module_name: str = None) -> ValidationReport:
        """
        创建校验报告

        Args:
            module_name: 模块名称，默认使用校验器名称

        Returns:
            新的校验报告
        """
        return ValidationReport(module_name=module_name or self.name)

    def reset(self):
        """重置校验器状态"""
        self._report = None

    @abstractmethod
    def check(self, ir: ModuleIR, **kwargs) -> ValidationReport:
        """
        执行校验

        Args:
            ir: 模块中间表示
            **kwargs: 额外参数
                - declarations: List[Function] - .h 文件中的函数声明
                - definitions: List[Function] - .c 文件中的函数定义

        Returns:
            校验报告
        """
        pass

    # ============ 辅助方法 ============

    def _add_error(self, message: str, location=None, code: str = "", suggestion: str = ""):
        """添加错误"""
        self.report.add_error(message, location, code, suggestion)

    def _add_warning(self, message: str, location=None, code: str = "", suggestion: str = ""):
        """添加警告"""
        self.report.add_warning(message, location, code, suggestion)

    def _add_info(self, message: str, location=None, code: str = "", suggestion: str = ""):
        """添加提示"""
        self.report.add_info(message, location, code, suggestion)

    def _format_location(self, location) -> str:
        """格式化位置信息"""
        if location is None:
            return ""
        if hasattr(location, 'file') and hasattr(location, 'line'):
            return f"{location.file}:{location.line}"
        return str(location)
