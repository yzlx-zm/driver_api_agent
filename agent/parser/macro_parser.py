"""宏定义解析器"""

import re
from typing import List, Optional, Dict, Any
from .base import BaseParser
from ..models.ir import Macro, SourceLocation


class MacroParser(BaseParser):
    """宏定义解析器"""

    # 匹配 #define NAME VALUE 或 #define NAME(params) VALUE
    MACRO_PATTERN = re.compile(
        r'''(?mx)
        ^\s*
        \#define\s+
        (?P<name>\w+)
        (?:\((?P<params>[^)]*)\))?  # 可选的宏函数参数
        \s*
        (?P<value>.*?)
        (?:
            (?:/\*|//)  # 注释开始
            |
            $  # 行尾
        )
        '''
    )

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.hardware_keywords = config.get('hardware_keywords', [
            'UART', 'GPIO', 'SPI', 'I2C', 'PWM', 'ADC', 'DAC',
            'TIMER', 'IRQ', 'PIN', 'PORT', 'RCU', 'DMA'
        ]) if config else []
        self.protocol_keywords = config.get('protocol_keywords', [
            'CMD', 'MSG', 'MSGID', 'FRAME', 'PACKET',
            'TIMEOUT', 'SIZE', 'BUF', 'LEN'
        ]) if config else []

    def parse(self, content: str, file_path: str) -> List[Macro]:
        """
        解析宏定义

        Args:
            content: 源码内容
            file_path: 文件路径

        Returns:
            宏定义列表
        """
        macros = []
        lines = content.split('\n')

        i = 0
        while i < len(lines):
            line = lines[i]

            # 检查是否是#define开始
            if not line.strip().startswith('#define'):
                i += 1
                continue

            # 合并续行
            full_line = line
            while full_line.rstrip().endswith('\\') and i < len(lines) - 1:
                i += 1
                full_line = full_line.rstrip()[:-1] + lines[i]

            # 解析宏
            macro = self._parse_macro(full_line, file_path, i + 1)
            if macro:
                macros.append(macro)

            i += 1

        return macros

    def _parse_macro(self, line: str, file_path: str, line_num: int) -> Optional[Macro]:
        """
        解析单个宏定义

        Args:
            line: 宏定义行
            file_path: 文件路径
            line_num: 行号

        Returns:
            Macro对象或None
        """
        # 移除行尾注释
        code_part = line
        comment_part = ""

        # 查找行尾注释
        comment_match = re.search(r'\s*/[/*](.*)$', line)
        if comment_match:
            code_part = line[:comment_match.start()]
            comment_part = comment_match.group(1).strip('/* ')

        match = self.MACRO_PATTERN.match(code_part)
        if not match:
            return None

        name = match.group('name')
        params_str = match.group('params')
        value = match.group('value').strip()

        # 判断是否为宏函数
        is_function_like = params_str is not None
        params = []
        if is_function_like:
            params = [p.strip() for p in params_str.split(',') if p.strip()]

        # 猜测分类
        category = self._guess_category(name)

        # 解析值类型
        value_type, numeric_value = self._parse_value_type(value)

        return Macro(
            name=name,
            value=value,
            description=comment_part,
            category=category,
            is_function_like=is_function_like,
            params=params,
            value_type=value_type,
            numeric_value=numeric_value,
            location=SourceLocation(file=file_path, line=line_num),
            header_file=file_path
        )

    def _guess_category(self, name: str) -> str:
        """
        猜测宏的类别

        Args:
            name: 宏名称

        Returns:
            类别字符串
        """
        name_upper = name.upper()

        # 硬件配置
        for kw in self.hardware_keywords:
            if kw in name_upper:
                return "硬件配置"

        # 协议常量
        for kw in self.protocol_keywords:
            if kw in name_upper:
                return "协议常量"

        # 状态码
        if any(kw in name_upper for kw in ['STATE', 'STATUS', 'ERROR', 'SUCCESS', 'FAIL']):
            return "状态码"

        # 调试
        if 'DEBUG' in name_upper or 'LOG' in name_upper or 'PRINT' in name_upper:
            return "调试"

        return "常量"

    def _parse_value_type(self, value: str) -> tuple:
        """
        解析宏值的类型

        Args:
            value: 宏值字符串

        Returns:
            (类型, 数值) 元组
        """
        if not value:
            return ("empty", None)

        value = value.strip()

        # 数字
        try:
            if value.startswith('0x') or value.startswith('0X'):
                return ("number", int(value, 16))
            elif value.startswith('0b') or value.startswith('0B'):
                return ("number", int(value, 2))
            elif value.endswith('U') or value.endswith('u'):
                return ("number", int(value[:-1]))
            elif value.endswith('UL') or value.endswith('ul'):
                return ("number", int(value[:-2]))
            else:
                num = int(value)
                return ("number", num)
        except ValueError:
            pass

        # 字符串
        if value.startswith('"') or value.startswith("'"):
            return ("string", None)

        # 字符
        if len(value) == 3 and value.startswith("'") and value.endswith("'"):
            return ("char", ord(value[1]))

        # 表达式
        return ("expression", None)
