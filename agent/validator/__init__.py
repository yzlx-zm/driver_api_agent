"""校验器模块

提供统一的校验器注册和管理机制
"""

from typing import Dict, List, Any, Type, Optional
from .base import BaseValidator
from .signature_checker import SignatureChecker
from .struct_comment_checker import StructCommentChecker
from .naming_checker import NamingChecker
from .coverage_checker import CoverageChecker
from .param_direction_checker import ParamDirectionChecker
from ..models.ir import ModuleIR, ValidationReport


class ValidatorRegistry:
    """校验器注册表

    管理所有校验器的创建和执行
    """

    # 注册的校验器类
    _validators: Dict[str, Type[BaseValidator]] = {
        'signature': SignatureChecker,
        'struct_comment': StructCommentChecker,
        'naming': NamingChecker,
        'coverage': CoverageChecker,
        'param_direction': ParamDirectionChecker,
    }

    @classmethod
    def register(cls, name: str, validator_class: Type[BaseValidator]):
        """
        注册新的校验器

        Args:
            name: 校验器名称
            validator_class: 校验器类
        """
        cls._validators[name] = validator_class

    @classmethod
    def create(cls, name: str, config: Dict = None) -> BaseValidator:
        """
        创建校验器实例

        Args:
            name: 校验器名称
            config: 校验器配置

        Returns:
            校验器实例

        Raises:
            ValueError: 校验器名称不存在
        """
        if name not in cls._validators:
            raise ValueError(f"Unknown validator: {name}. Available: {list(cls._validators.keys())}")
        return cls._validators[name](config)

    @classmethod
    def create_all_enabled(cls, config: Dict) -> List[BaseValidator]:
        """
        创建所有启用的校验器

        Args:
            config: 全局配置字典

        Returns:
            校验器实例列表
        """
        validators = []

        # 签名校验器
        if config.get('validator_check_signature', True):
            validators.append(cls.create('signature', config.get('validator_signature', {})))

        # 结构体注释校验器
        if config.get('validator_check_struct_comments', True):
            validators.append(cls.create('struct_comment', config.get('validator_struct_comment', {})))

        # 命名规范校验器
        if config.get('validator_check_naming', True):
            naming_config = {
                'function_prefix': config.get('validator_naming_function_prefix', ''),
                'macro_prefix': config.get('validator_naming_macro_prefix', ''),
                'enum_prefix': config.get('validator_naming_enum_prefix', ''),
                'struct_prefix': config.get('validator_naming_struct_prefix', ''),
                'snake_case': config.get('validator_naming_snake_case', True),
                'enum_uppercase': config.get('validator_naming_enum_uppercase', True),
            }
            validators.append(cls.create('naming', naming_config))

        # 覆盖率校验器
        if config.get('validator_check_coverage', True):
            coverage_config = {
                'min_function_desc': config.get('validator_coverage_min_description', 80),
                'min_param_doc': config.get('validator_coverage_min_param_doc', 60),
                'min_return_doc': config.get('validator_coverage_min_return_doc', 50),
            }
            validators.append(cls.create('coverage', coverage_config))

        # 参数方向校验器
        if config.get('validator_check_param_direction', True):
            validators.append(cls.create('param_direction', config.get('validator_param_direction', {})))

        return validators

    @classmethod
    def available_validators(cls) -> List[str]:
        """获取所有可用的校验器名称"""
        return list(cls._validators.keys())


class ValidationRunner:
    """校验执行器

    执行所有校验器并汇总结果
    """

    def __init__(self, config: Dict = None):
        """
        初始化校验执行器

        Args:
            config: 全局配置
        """
        self.config = config or {}
        self.validators = ValidatorRegistry.create_all_enabled(self.config)
        self.reports: List[ValidationReport] = []

    def run_all(self, ir: ModuleIR, **kwargs) -> ValidationReport:
        """
        执行所有校验器

        Args:
            ir: 模块中间表示
            **kwargs: 额外参数传递给校验器

        Returns:
            汇总的校验报告
        """
        self.reports = []

        for validator in self.validators:
            try:
                report = validator.check(ir, **kwargs)
                self.reports.append(report)
            except Exception as e:
                # 创建错误报告
                error_report = ValidationReport(module_name=validator.name)
                error_report.add_error(
                    f"校验器执行失败: {str(e)}",
                    code="VALIDATOR_ERROR"
                )
                self.reports.append(error_report)

        # 汇总所有报告
        return self._merge_reports()

    def _merge_reports(self) -> ValidationReport:
        """合并所有校验报告"""
        merged = ValidationReport(module_name="All Validators")

        for report in self.reports:
            for result in report.results:
                merged.results.append(result)

        return merged


# 导出
__all__ = [
    'BaseValidator',
    'SignatureChecker',
    'StructCommentChecker',
    'NamingChecker',
    'CoverageChecker',
    'ParamDirectionChecker',
    'ValidatorRegistry',
    'ValidationRunner',
]
