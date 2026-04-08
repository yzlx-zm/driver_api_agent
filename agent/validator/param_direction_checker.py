"""参数方向校验器

检查函数参数的方向标注（IN/OUT/INOUT）是否正确
"""

import re
from typing import Dict, Any, List, Tuple
from .base import BaseValidator
from ..models.ir import ModuleIR, Function, Parameter, ParamDirection


class ParamDirectionChecker(BaseValidator):
    """参数方向校验器

    检查内容：
    1. 指针参数是否有明确的方向标注
    2. 方向标注是否与实际类型匹配
    3. const 修饰符与方向标注的一致性
    """

    @property
    def name(self) -> str:
        return "Parameter Direction Checker"

    def __init__(self, config: Dict = None):
        super().__init__(config)
        # 是否严格模式（未标注方向时警告）
        self.strict_mode = self.config.get('strict_mode', False)
        # 检查 const 一致性
        self.check_const_consistency = self.config.get('check_const_consistency', True)

    def check(self, ir: ModuleIR, **kwargs) -> 'ValidationReport':
        """
        执行参数方向校验

        Args:
            ir: 模块中间表示

        Returns:
            校验报告
        """
        self.reset()

        for func in ir.functions:
            self._check_function_params(func)

        return self.report

    def _check_function_params(self, func: Function):
        """检查函数的参数方向"""
        if not func.params:
            return

        for i, param in enumerate(func.params):
            self._check_single_param(func.name, i, param)

    def _check_single_param(self, func_name: str, index: int, param: Parameter):
        """检查单个参数的方向标注"""
        # 分析参数类型
        type_info = self._analyze_param_type(param.type)
        # 补充：如果 type_str 中不含 * 但 is_pointer=True，也标记为指针
        if param.is_pointer:
            type_info['is_pointer'] = True
            if param.type.count('*') >= 1:
                type_info['is_double_pointer'] = param.type.count('*') >= 2

        # 推断期望的方向
        expected_direction = self._infer_expected_direction(param, type_info)

        # 检查方向标注
        if param.direction == ParamDirection.UNKNOWN:
            if self.strict_mode and type_info['is_pointer']:
                self._add_warning(
                    f"函数 '{func_name}' 参数 '{param.name}' 缺少方向标注 (IN/OUT/INOUT)",
                    code="MISSING_PARAM_DIRECTION",
                    suggestion="在注释中使用 @param[out] 或 @param[in,out] 标注参数方向"
                )
        else:
            # 检查方向标注是否与类型一致
            self._check_direction_consistency(func_name, param, type_info, expected_direction)

    def _analyze_param_type(self, type_str: str) -> Dict[str, Any]:
        """
        分析参数类型

        Returns:
            {
                'is_pointer': bool,
                'is_double_pointer': bool,
                'is_const': bool,
                'is_array': bool,
                'base_type': str
            }
        """
        type_str = type_str.strip()

        return {
            'is_pointer': '*' in type_str or 'pointer' in type_str.lower(),
            'is_double_pointer': type_str.count('*') >= 2,
            'is_const': 'const' in type_str.lower(),
            'is_array': '[' in type_str and ']' in type_str,
            'base_type': self._extract_base_type(type_str)
        }

    def _extract_base_type(self, type_str: str) -> str:
        """提取基础类型（移除 const、*、[] 等）"""
        # 移除 const
        result = re.sub(r'\bconst\b', '', type_str, flags=re.IGNORECASE)
        # 移除指针符号
        result = re.sub(r'\*+', '', result)
        # 移除数组符号
        result = re.sub(r'\[.*?\]', '', result)
        return result.strip()

    def _infer_expected_direction(self, param: Parameter, type_info: Dict) -> ParamDirection:
        """
        根据参数类型推断期望的方向

        规则：
        - const T* -> IN
        - T* (非 const) -> OUT 或 INOUT
        - T** -> OUT
        - T (非指针) -> IN
        """
        if not type_info['is_pointer'] and not type_info['is_array']:
            return ParamDirection.IN

        if type_info['is_double_pointer']:
            return ParamDirection.OUT

        if type_info['is_const']:
            return ParamDirection.IN

        # 非常量指针，可能是 OUT 或 INOUT
        # 如果参数名包含 result、output、out 等，推测为 OUT
        name_lower = param.name.lower()
        out_indicators = ['result', 'output', 'out', 'ret', 'resp', 'response']
        if any(ind in name_lower for ind in out_indicators):
            return ParamDirection.OUT

        # 默认为 INOUT
        return ParamDirection.INOUT

    def _check_direction_consistency(self, func_name: str, param: Parameter,
                                      type_info: Dict, expected: ParamDirection):
        """检查方向标注是否与类型一致"""
        actual = param.direction

        # IN 标注但类型非常量指针
        if actual == ParamDirection.IN:
            if type_info['is_pointer'] and not type_info['is_const']:
                if self.check_const_consistency:
                    self._add_info(
                        f"函数 '{func_name}' 参数 '{param.name}' 标注为 IN 但类型为非常量指针，考虑添加 const 修饰符或改为 INOUT",
                        code="IN_PARAM_WITHOUT_CONST",
                        suggestion="添加 const 修饰符或更改方向标注为 INOUT"
                    )

        # OUT/INOUT 标注但类型不是指针
        if actual in (ParamDirection.OUT, ParamDirection.INOUT):
            if not type_info['is_pointer'] and not type_info['is_array']:
                self._add_warning(
                    f"函数 '{func_name}' 参数 '{param.name}' 标注为 {actual.value} 但类型不是指针",
                    code="OUT_PARAM_NOT_POINTER",
                    suggestion="OUT/INOUT 参数应该是指针类型"
                )

        # OUT 标注但类型是 const 指针
        if actual == ParamDirection.OUT:
            if type_info['is_pointer'] and type_info['is_const']:
                self._add_warning(
                    f"函数 '{func_name}' 参数 '{param.name}' 标注为 OUT 但类型为 const 指针，const 指针无法修改内容",
                    code="OUT_PARAM_WITH_CONST",
                    suggestion="移除 const 修饰符或更改方向标注"
                )
