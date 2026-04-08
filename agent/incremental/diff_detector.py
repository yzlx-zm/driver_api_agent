"""IR 差异检测器

检测两个版本 IR 之间的差异
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple
from ..models.ir import ModuleIR, Function, Struct, Enum, Macro


@dataclass
class DiffResult:
    """差异检测结果"""

    # 函数变更
    added_functions: List[str] = field(default_factory=list)
    removed_functions: List[str] = field(default_factory=list)
    modified_functions: List[str] = field(default_factory=list)  # 签名变化

    # 结构体变更
    added_structs: List[str] = field(default_factory=list)
    removed_structs: List[str] = field(default_factory=list)
    modified_structs: List[str] = field(default_factory=list)

    # 枚举变更
    added_enums: List[str] = field(default_factory=list)
    removed_enums: List[str] = field(default_factory=list)
    modified_enums: List[str] = field(default_factory=list)

    # 宏变更
    added_macros: List[str] = field(default_factory=list)
    removed_macros: List[str] = field(default_factory=list)
    modified_macros: List[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        """是否有任何变更"""
        return bool(
            self.added_functions or self.removed_functions or self.modified_functions or
            self.added_structs or self.removed_structs or self.modified_structs or
            self.added_enums or self.removed_enums or self.modified_enums or
            self.added_macros or self.removed_macros or self.modified_macros
        )

    @property
    def total_changes(self) -> int:
        """总变更数"""
        return (
            len(self.added_functions) + len(self.removed_functions) + len(self.modified_functions) +
            len(self.added_structs) + len(self.removed_structs) + len(self.modified_structs) +
            len(self.added_enums) + len(self.removed_enums) + len(self.modified_enums) +
            len(self.added_macros) + len(self.removed_macros) + len(self.modified_macros)
        )

    def get_summary(self) -> str:
        """获取变更摘要"""
        lines = ["=== 代码变更摘要 ==="]

        if self.added_functions:
            lines.append(f"+ 新增函数: {', '.join(self.added_functions[:5])}{'...' if len(self.added_functions) > 5 else ''}")
        if self.removed_functions:
            lines.append(f"- 删除函数: {', '.join(self.removed_functions[:5])}{'...' if len(self.removed_functions) > 5 else ''}")
        if self.modified_functions:
            lines.append(f"* 修改函数: {', '.join(self.modified_functions[:5])}{'...' if len(self.modified_functions) > 5 else ''}")

        if self.added_structs:
            lines.append(f"+ 新增结构体: {', '.join(self.added_structs[:5])}")
        if self.removed_structs:
            lines.append(f"- 删除结构体: {', '.join(self.removed_structs[:5])}")
        if self.modified_structs:
            lines.append(f"* 修改结构体: {', '.join(self.modified_structs[:5])}")

        if self.added_enums:
            lines.append(f"+ 新增枚举: {', '.join(self.added_enums[:5])}")
        if self.removed_enums:
            lines.append(f"- 删除枚举: {', '.join(self.removed_enums[:5])}")

        if self.added_macros:
            lines.append(f"+ 新增宏: {len(self.added_macros)} 个")
        if self.removed_macros:
            lines.append(f"- 删除宏: {len(self.removed_macros)} 个")

        lines.append(f"\n总计: {self.total_changes} 处变更")

        return "\n".join(lines)


class DiffDetector:
    """IR 差异检测器

    比较新旧两个版本的 IR，检测变更
    """

    def compare(self, old_ir: Optional[ModuleIR], new_ir: ModuleIR) -> DiffResult:
        """
        比较两个版本的 IR

        Args:
            old_ir: 旧版本 IR（如果是首次生成则为 None）
            new_ir: 新版本 IR

        Returns:
            差异检测结果
        """
        result = DiffResult()

        if old_ir is None:
            # 首次生成，所有内容都是新增
            result.added_functions = [f.name for f in new_ir.functions]
            result.added_structs = [s.name or s.typedef_name for s in new_ir.structs]
            result.added_enums = [e.name or e.typedef_name for e in new_ir.enums]
            result.added_macros = [m.name for m in new_ir.macros]
            return result

        # 比较函数
        self._compare_functions(old_ir, new_ir, result)

        # 比较结构体
        self._compare_structs(old_ir, new_ir, result)

        # 比较枚举
        self._compare_enums(old_ir, new_ir, result)

        # 比较宏
        self._compare_macros(old_ir, new_ir, result)

        return result

    def _compare_functions(self, old_ir: ModuleIR, new_ir: ModuleIR, result: DiffResult):
        """比较函数"""
        old_funcs = {f.name: f for f in old_ir.functions}
        new_funcs = {f.name: f for f in new_ir.functions}

        old_names = set(old_funcs.keys())
        new_names = set(new_funcs.keys())

        result.added_functions = list(new_names - old_names)
        result.removed_functions = list(old_names - new_names)

        # 检查修改（签名变化）
        common_names = old_names & new_names
        for name in common_names:
            if self._is_function_modified(old_funcs[name], new_funcs[name]):
                result.modified_functions.append(name)

    def _is_function_modified(self, old: Function, new: Function) -> bool:
        """检查函数是否被修改（签名变化）"""
        # 比较返回类型
        if old.return_type != new.return_type:
            return True

        # 比较参数
        if len(old.params) != len(new.params):
            return True

        for old_p, new_p in zip(old.params, new.params):
            if old_p.type != new_p.type:
                return True

        return False

    def _compare_structs(self, old_ir: ModuleIR, new_ir: ModuleIR, result: DiffResult):
        """比较结构体"""
        old_structs = {self._struct_key(s): s for s in old_ir.structs}
        new_structs = {self._struct_key(s): s for s in new_ir.structs}

        old_keys = set(old_structs.keys())
        new_keys = set(new_structs.keys())

        result.added_structs = list(new_keys - old_keys)
        result.removed_structs = list(old_keys - new_keys)

        # 检查修改
        common_keys = old_keys & new_keys
        for key in common_keys:
            if self._is_struct_modified(old_structs[key], new_structs[key]):
                result.modified_structs.append(key)

    def _struct_key(self, s: Struct) -> str:
        """获取结构体的唯一标识"""
        return s.typedef_name or s.name or ""

    def _is_struct_modified(self, old: Struct, new: Struct) -> bool:
        """检查结构体是否被修改"""
        # 比较字段数量
        if len(old.fields) != len(new.fields):
            return True

        # 比较字段类型
        for old_f, new_f in zip(old.fields, new.fields):
            if old_f.type != new_f.type or old_f.name != new_f.name:
                return True

        return False

    def _compare_enums(self, old_ir: ModuleIR, new_ir: ModuleIR, result: DiffResult):
        """比较枚举"""
        old_enums = {self._enum_key(e): e for e in old_ir.enums}
        new_enums = {self._enum_key(e): e for e in new_ir.enums}

        old_keys = set(old_enums.keys())
        new_keys = set(new_enums.keys())

        result.added_enums = list(new_keys - old_keys)
        result.removed_enums = list(old_keys - new_keys)

        # 检查修改
        common_keys = old_keys & new_keys
        for key in common_keys:
            if self._is_enum_modified(old_enums[key], new_enums[key]):
                result.modified_enums.append(key)

    def _enum_key(self, e: Enum) -> str:
        """获取枚举的唯一标识"""
        return e.typedef_name or e.name or ""

    def _is_enum_modified(self, old: Enum, new: Enum) -> bool:
        """检查枚举是否被修改"""
        if len(old.values) != len(new.values):
            return True

        for old_v, new_v in zip(old.values, new.values):
            if old_v.name != new_v.name:
                return True

        return False

    def _compare_macros(self, old_ir: ModuleIR, new_ir: ModuleIR, result: DiffResult):
        """比较宏"""
        old_macros = {m.name: m for m in old_ir.macros}
        new_macros = {m.name: m for m in new_ir.macros}

        old_names = set(old_macros.keys())
        new_names = set(new_macros.keys())

        result.added_macros = list(new_names - old_names)
        result.removed_macros = list(old_names - new_names)

        # 检查修改（值变化）
        common_names = old_names & new_names
        for name in common_names:
            if old_macros[name].value != new_macros[name].value:
                result.modified_macros.append(name)
