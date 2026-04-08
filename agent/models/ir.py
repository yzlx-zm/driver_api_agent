"""
中间表示(IR)数据模型

定义用于存储解析结果的中间数据结构
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime


class ParamDirection(Enum):
    """参数方向"""
    IN = "IN"
    OUT = "OUT"
    INOUT = "INOUT"
    UNKNOWN = ""


class FunctionCategory(Enum):
    """函数分类"""
    INIT = "初始化接口"
    BUSINESS = "业务接口"
    QUERY = "查询接口"
    CALLBACK = "回调接口"
    INTERNAL = "内部接口"
    UNKNOWN = "其他"


@dataclass
class SourceLocation:
    """源码位置"""
    file: str = ""
    line: int = 0
    column: int = 0

    def __str__(self):
        if self.file:
            return f"{self.file}:{self.line}"
        return f"line {self.line}"


@dataclass
class Parameter:
    """函数参数"""
    name: str
    type: str
    direction: ParamDirection = ParamDirection.UNKNOWN
    description: str = ""
    is_const: bool = False
    is_pointer: bool = False
    is_array: bool = False
    array_size: Optional[int] = None

    def to_decl(self) -> str:
        """生成声明字符串"""
        decl = self.type
        if self.is_const:
            decl = f"const {decl}"
        if self.is_pointer:
            decl = f"{decl} *{self.name}"
        elif self.is_array:
            if self.array_size:
                decl = f"{decl} {self.name}[{self.array_size}]"
            else:
                decl = f"{decl} {self.name}[]"
        else:
            decl = f"{decl} {self.name}"
        return decl


@dataclass
class Function:
    """函数声明/定义"""
    name: str
    return_type: str
    params: List[Parameter] = field(default_factory=list)
    description: str = ""
    category: FunctionCategory = FunctionCategory.UNKNOWN

    # 源码位置
    location: SourceLocation = field(default_factory=SourceLocation)
    header_file: str = ""
    source_file: str = ""
    implementation_line: int = 0  # .c文件中的行号

    # 属性
    is_static: bool = False
    is_inline: bool = False
    is_deprecated: bool = False
    is_public: bool = True

    # 注释信息
    brief: str = ""  # 简短描述
    details: str = ""  # 详细描述
    return_desc: str = ""  # 返回值说明
    notes: List[str] = field(default_factory=list)  # 注意事项
    see_also: List[str] = field(default_factory=list)  # 相关函数

    def to_signature(self) -> str:
        """生成函数签名"""
        params_str = ", ".join(p.to_decl() for p in self.params) if self.params else "void"
        signature = f"{self.return_type} {self.name}({params_str})"
        return signature

    def guess_category(self, keywords: Dict[str, List[str]]) -> FunctionCategory:
        """根据函数名猜测分类"""
        name_lower = self.name.lower()

        for category, kws in keywords.items():
            for kw in kws:
                if kw in name_lower:
                    if category == "init":
                        return FunctionCategory.INIT
                    elif category == "query":
                        return FunctionCategory.QUERY
                    elif category == "callback":
                        return FunctionCategory.CALLBACK

        return FunctionCategory.BUSINESS


@dataclass
class StructField:
    """结构体字段"""
    name: str
    type: str
    description: str = ""
    is_const: bool = False
    is_pointer: bool = False
    is_array: bool = False
    array_size: Optional[int] = None
    bit_field: Optional[int] = None  # 位域

    location: SourceLocation = field(default_factory=SourceLocation)


@dataclass
class Struct:
    """结构体定义"""
    name: str
    fields: List[StructField] = field(default_factory=list)
    description: str = ""
    location: SourceLocation = field(default_factory=SourceLocation)
    header_file: str = ""

    # 类型信息
    is_typedef: bool = False
    typedef_name: str = ""  # typedef的别名
    is_packed: bool = False
    is_union: bool = False  # union也算在这里

    def get_size_info(self) -> str:
        """估算结构体大小信息"""
        # TODO: 根据字段类型计算大小
        return "待计算"


@dataclass
class EnumValue:
    """枚举值"""
    name: str
    value: int = 0
    description: str = ""
    location: SourceLocation = field(default_factory=SourceLocation)


@dataclass
class Enum:
    """枚举定义"""
    name: str
    values: List[EnumValue] = field(default_factory=list)
    description: str = ""
    location: SourceLocation = field(default_factory=SourceLocation)
    header_file: str = ""

    # 类型信息
    is_typedef: bool = False
    typedef_name: str = ""
    base_type: str = "int"  # 底层类型

    def get_value_by_name(self, name: str) -> Optional[EnumValue]:
        """根据名称获取枚举值"""
        for v in self.values:
            if v.name == name:
                return v
        return None


@dataclass
class Macro:
    """宏定义"""
    name: str
    value: str = ""
    description: str = ""
    category: str = "常量"  # 常量/配置/调试/协议
    location: SourceLocation = field(default_factory=SourceLocation)
    header_file: str = ""

    # 宏类型
    is_function_like: bool = False  # 是否为宏函数
    params: List[str] = field(default_factory=list)  # 宏函数参数

    # 值解析
    value_type: str = "unknown"  # number/string/expression
    numeric_value: Optional[int] = None

    def parse_value(self) -> Any:
        """尝试解析宏值"""
        if not self.value:
            return None

        # 尝试解析数字
        try:
            if self.value.startswith('0x') or self.value.startswith('0X'):
                return int(self.value, 16)
            elif self.value.startswith('0b') or self.value.startswith('0B'):
                return int(self.value, 2)
            else:
                return int(self.value)
        except ValueError:
            pass

        # 字符串
        if self.value.startswith('"') or self.value.startswith("'"):
            return self.value.strip('"\'')

        return self.value


@dataclass
class Typedef:
    """typedef定义"""
    name: str
    target_type: str
    description: str = ""
    location: SourceLocation = field(default_factory=SourceLocation)
    header_file: str = ""

    # 类型分类
    is_function_pointer: bool = False
    func_params: List[Parameter] = field(default_factory=list)
    func_return_type: str = ""


@dataclass
class Include:
    """头文件包含"""
    path: str
    is_system: bool = False  # <...> vs "..."
    location: SourceLocation = field(default_factory=SourceLocation)


@dataclass
class Comment:
    """注释块"""
    content: str
    style: str = "block"  # block/line/doxygen
    location: SourceLocation = field(default_factory=SourceLocation)

    # Doxygen解析结果
    brief: str = ""
    params: Dict[str, str] = field(default_factory=dict)
    returns: str = ""
    notes: List[str] = field(default_factory=list)


@dataclass
class ModuleIR:
    """
    模块中间表示

    存储一个模块（通常是一个.h/.c文件对）的所有解析信息
    """
    # 基本信息
    name: str = ""
    description: str = ""
    header_file: str = ""
    source_file: str = ""

    # 解析结果
    functions: List[Function] = field(default_factory=list)
    structs: List[Struct] = field(default_factory=list)
    enums: List[Enum] = field(default_factory=list)
    macros: List[Macro] = field(default_factory=list)
    typedefs: List[Typedef] = field(default_factory=list)
    includes: List[Include] = field(default_factory=list)
    comments: List[Comment] = field(default_factory=list)

    # 元数据
    git_commit: str = ""
    generated_time: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # 统计
    def get_stats(self) -> Dict[str, int]:
        """获取统计信息"""
        return {
            "functions": len(self.functions),
            "public_functions": len([f for f in self.functions if f.is_public]),
            "static_functions": len([f for f in self.functions if f.is_static]),
            "structs": len(self.structs),
            "enums": len(self.enums),
            "macros": len(self.macros),
            "typedefs": len(self.typedefs),
        }

    # 查询方法
    def get_function(self, name: str) -> Optional[Function]:
        """根据名称获取函数"""
        for func in self.functions:
            if func.name == name:
                return func
        return None

    def get_struct(self, name: str) -> Optional[Struct]:
        """根据名称获取结构体"""
        for struct in self.structs:
            if struct.name == name or struct.typedef_name == name:
                return struct
        return None

    def get_enum(self, name: str) -> Optional[Enum]:
        """根据名称获取枚举"""
        for enum in self.enums:
            if enum.name == name or enum.typedef_name == name:
                return enum
        return None

    def get_macro(self, name: str) -> Optional[Macro]:
        """根据名称获取宏"""
        for macro in self.macros:
            if macro.name == name:
                return macro
        return None


@dataclass
class ValidationResult:
    """校验结果"""
    level: str  # ERROR/WARNING/INFO
    message: str
    location: Optional[SourceLocation] = None
    code: str = ""  # 错误码
    suggestion: str = ""  # 修复建议


@dataclass
class ValidationReport:
    """校验报告"""
    module_name: str
    results: List[ValidationResult] = field(default_factory=list)

    def add_error(self, message: str, location: SourceLocation = None, code: str = "", suggestion: str = ""):
        self.results.append(ValidationResult("ERROR", message, location, code, suggestion))

    def add_warning(self, message: str, location: SourceLocation = None, code: str = "", suggestion: str = ""):
        self.results.append(ValidationResult("WARNING", message, location, code, suggestion))

    def add_info(self, message: str, location: SourceLocation = None, code: str = "", suggestion: str = ""):
        self.results.append(ValidationResult("INFO", message, location, code, suggestion))

    def has_errors(self) -> bool:
        return any(r.level == "ERROR" for r in self.results)

    def has_warnings(self) -> bool:
        return any(r.level == "WARNING" for r in self.results)

    def get_summary(self) -> str:
        """获取摘要"""
        errors = sum(1 for r in self.results if r.level == "ERROR")
        warnings = sum(1 for r in self.results if r.level == "WARNING")
        infos = sum(1 for r in self.results if r.level == "INFO")

        lines = [f"=== 校验报告 [{self.module_name}] ===", ""]

        for r in self.results:
            loc_str = f" ({r.location})" if r.location else ""
            lines.append(f"[{r.level}] {r.message}{loc_str}")
            if r.suggestion:
                lines.append(f"  建议: {r.suggestion}")

        lines.append("")
        lines.append(f"总计: {errors} 错误, {warnings} 警告, {infos} 提示")

        return "\n".join(lines)
