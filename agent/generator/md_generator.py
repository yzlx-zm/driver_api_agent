"""Markdown文档生成器"""

import re
from typing import List, Dict, Any, Optional
from datetime import datetime
import os

from ..models.ir import (
    ModuleIR, Function, Struct, Enum, Macro,
    FunctionCategory, ValidationReport
)
from ..incremental import wrap_in_auto_region


# 函数名 → 中文功能描述 推断规则
# 格式: (pattern, description, is_prefix_action)
# is_prefix_action=True 表示动作应在领域词之前（如 "判断是否" + "就绪" = "判断是否就绪"）
_FUNC_NAME_DESC_MAP = {
    # 前缀型动作（动作 + 领域词）- 优先匹配
    r'_parse_': ('解析', True),
    r'_get_': ('获取', True),
    r'_set_': ('设置', True),
    r'_is_': ('判断', True),
    r'_has_': ('判断是否有', True),
    r'_can_': ('判断能否', True),
    r'_check_': ('检查', True),
    r'_delete_': ('删除', True),
    r'_enroll_': ('录入', True),
    # 后缀型动作（领域词 + 动作）
    r'_init$': ('初始化', False),
    r'_deinit$': ('反初始化', False),
    r'_start$': ('启动', False),
    r'_stop$': ('停止', False),
    r'_reset$': ('重置', False),
    r'_enable$': ('使能', False),
    r'_disable$': ('禁用', False),
    r'_send$': ('发送', False),
    r'_recv$': ('接收', False),
    r'_receive$': ('接收', False),
    r'_process$': ('处理', False),
    r'_update$': ('更新', False),
    r'_count$': ('计数', False),
    r'_ctrl$': ('控制', False),
    r'_config$': ('配置', False),
    r'_schedule$': ('调度', False),
    r'_handle': ('处理', False),
    r'_callback$': ('回调', False),
    r'_verify$': ('校验/识别', False),
    r'_powerdown': ('关机', False),
    r'_sleep$': ('休眠', False),
    r'_wakeup$': ('唤醒', False),
    r'_clear$': ('清空', False),
    r'_test$': ('测试', False),
    r'_reply$': ('回复', False),
}

# 领域关键词 → 中文语义
_DOMAIN_KEYWORDS = {
    'uart': '串口', 'pwr': '电源', 'power': '电源',
    'frame': '帧', 'hs': '握手', 'handshake': '握手',
    'face': '人脸', 'palm': '掌静脉', 'enroll': '录入',
    'verify': '识别/校验', 'delete': '删除', 'del': '删除',
    'version': '版本', 'ota': 'OTA升级', 'status': '状态',
    'state': '状态', 'life': '生命周期', 'cmd': '命令',
    'user': '用户', 'uid': 'UID', 'mode': '模式',
    'work_mode': '工作模式', 'ready': '就绪', 'busy': '忙',
    'cap_lock': '采集锁定', 'module': '模组', 'baudrate': '波特率',
    'result': '结果', 'param': '参数',
    'rx': '接收', 'tx': '发送', 'buf': '缓冲区', 'buffer': '缓冲区',
    'msg': '消息', 'note': '通知', 'reply': '回复', 'log': '日志',
    'ctx': '上下文', 'context': '上下文',
    'sleep': '休眠', 'wakeup': '唤醒', 'stop': '停止',
}


class MarkdownGenerator:
    """Markdown API文档生成器"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.template_language = self.config.get('template_language', 'zh')
        self.include_toc = self.config.get('template_include_toc', True)
        # 区域标记配置
        self.use_region_markers = self.config.get('use_region_markers', True)

    def _wrap_region(self, content: str, region_name: str) -> str:
        if not self.use_region_markers:
            return content
        return wrap_in_auto_region(region_name, content)

    def generate(self, ir: ModuleIR, validation_report: Optional[ValidationReport] = None) -> str:
        """生成Markdown文档（动态章节编号）"""
        sections = []
        chapter_num = 1

        # 1. 标题（不包装在区域中，不计章节号）
        sections.append(self._generate_header(ir))

        # 2. 概述
        overview = self._generate_overview(ir, chapter_num)
        sections.append(self._wrap_region(overview, "overview"))
        chapter_num += 1

        # 3. 硬件配置
        hardware_macros = [m for m in ir.macros if m.category == "硬件配置"]
        if hardware_macros:
            hw_section = self._generate_hardware_section(hardware_macros, chapter_num)
            sections.append(self._wrap_region(hw_section, "hardware"))
            chapter_num += 1

        # 4. 协议常量
        protocol_macros = [m for m in ir.macros if m.category == "协议常量"]
        if protocol_macros:
            proto_section = self._generate_protocol_section(protocol_macros, chapter_num)
            sections.append(self._wrap_region(proto_section, "protocol"))
            chapter_num += 1

        # 5. 数据结构
        if ir.structs or ir.enums:
            data_section = self._generate_data_structures(ir, chapter_num)
            sections.append(self._wrap_region(data_section, "data_structures"))
            chapter_num += 1

        # 6. API接口
        api_section = self._generate_api_section(ir, chapter_num)
        sections.append(self._wrap_region(api_section, "api"))
        chapter_num += 1

        # 7. 常量/宏定义（展示未被前述章节覆盖的所有宏）
        shown_categories = {"硬件配置", "协议常量", "调试"}
        remaining_macros = [m for m in ir.macros if m.category not in shown_categories]
        if remaining_macros:
            macro_section = self._generate_macros_section(remaining_macros, chapter_num)
            sections.append(self._wrap_region(macro_section, "macros"))
            chapter_num += 1

        # 8. 使用示例
        examples_section = self._generate_examples_section(chapter_num)
        sections.append(self._wrap_region(examples_section, "examples"))
        chapter_num += 1

        # 9. 已知限制
        limitations_section = self._generate_limitations_section(chapter_num)
        sections.append(self._wrap_region(limitations_section, "limitations"))
        chapter_num += 1

        # 10. 移植说明
        porting_section = self._generate_porting_section(ir, chapter_num)
        sections.append(self._wrap_region(porting_section, "porting"))
        chapter_num += 1

        # 11. 参考资料
        references_section = self._generate_references_section(chapter_num)
        sections.append(self._wrap_region(references_section, "references"))
        chapter_num += 1

        # 12. 版本历史
        changelog_section = self._generate_changelog_section(ir, chapter_num)
        sections.append(self._wrap_region(changelog_section, "changelog"))
        chapter_num += 1

        # 校验报告已移除（不包含在生成的文档中）

        return '\n\n'.join(sections)

    def _generate_header(self, ir: ModuleIR) -> str:
        """生成文档头部"""
        lines = [
            f"# {ir.name or 'Driver'} API 文档",
            "",
            f"> 生成时间: {ir.generated_time}",
            f"> 代码版本: {ir.git_commit or 'unknown'}",
            "",
            "---"
        ]
        return '\n'.join(lines)

    def _generate_overview(self, ir: ModuleIR, chapter: int) -> str:
        """生成概述"""
        stats = ir.get_stats()

        lines = [
            f"## {chapter}. 概述",
            "",
            f"- **模块名称**: {ir.name or 'Unknown'}",
            f"- **功能描述**: {ir.description or '待补充'}",
            f"- **头文件**: `{os.path.basename(ir.header_file)}`" if ir.header_file else "- **头文件**: 待确定",
            "",
            "**统计信息**:",
            "",
            f"| 项目 | 数量 |",
            f"|------|------|",
            f"| 公开函数 | {stats['public_functions']} |",
            f"| 静态函数 | {stats['static_functions']} |",
            f"| 结构体 | {stats['structs']} |",
            f"| 枚举 | {stats['enums']} |",
            f"| 宏定义 | {stats['macros']} |",
            "",
            "---"
        ]
        return '\n'.join(lines)

    def _generate_hardware_section(self, macros: List[Macro], chapter: int) -> str:
        """生成硬件配置章节"""
        lines = [
            f"## {chapter}. 硬件配置",
            "",
            "| 宏名称 | 值 | 说明 |",
            "|--------|-----|------|",
        ]

        for macro in macros:
            value = f"`{macro.value}`" if macro.value else "-"
            desc = macro.description or "待补充"
            lines.append(f"| `{macro.name}` | {value} | {desc} |")

        lines.append("")
        lines.append("---")
        return '\n'.join(lines)

    def _generate_protocol_section(self, macros: List[Macro], chapter: int) -> str:
        """生成协议常量章节"""
        lines = [
            f"## {chapter}. 协议常量",
            "",
            "| 宏名称 | 值 | 说明 |",
            "|--------|-----|------|",
        ]

        for macro in macros:
            value = f"`{macro.value}`" if macro.value else "-"
            desc = macro.description or "待补充"
            lines.append(f"| `{macro.name}` | {value} | {desc} |")

        lines.append("")
        lines.append("---")
        return '\n'.join(lines)

    def _generate_data_structures(self, ir: ModuleIR, chapter: int) -> str:
        """生成数据结构章节"""
        lines = [f"## {chapter}. 数据结构", ""]

        # 枚举类型
        if ir.enums:
            lines.append(f"### {chapter}.1 枚举类型")
            lines.append("")

            for enum in ir.enums:
                lines.extend(self._generate_enum(enum))
                lines.append("")

        # 结构体
        if ir.structs:
            lines.append(f"### {chapter}.2 结构体")
            lines.append("")

            for struct in ir.structs:
                lines.extend(self._generate_struct(struct))
                lines.append("")

        lines.append("---")
        return '\n'.join(lines)

    def _generate_enum(self, enum: Enum) -> List[str]:
        """生成枚举文档"""
        lines = [
            f"#### {enum.name}",
            "",
            enum.description or "待补充",
            "",
            "| 枚举值 | 数值 | 说明 |",
            "|--------|------|------|",
        ]

        for value in enum.values:
            desc = value.description or "待补充"
            lines.append(f"| `{value.name}` | {value.value} | {desc} |")

        return lines

    def _generate_struct(self, struct: Struct) -> List[str]:
        """生成结构体文档"""
        lines = [
            f"#### {struct.name}",
            "",
            struct.description or "待补充",
            "",
            "| 字段名 | 类型 | 说明 |",
            "|--------|------|------|",
        ]

        for field in struct.fields:
            desc = field.description or "待补充"
            type_str = f"`{field.type}`"
            if field.is_array and field.array_size:
                type_str = f"`{field.type}[{field.array_size}]`"
            lines.append(f"| `{field.name}` | {type_str} | {desc} |")

        return lines

    def _generate_api_section(self, ir: ModuleIR, chapter: int) -> str:
        """生成API接口章节"""
        lines = [f"## {chapter}. API 接口", ""]

        # 按分类组织函数
        categories = self._categorize_functions(ir.functions)

        section_num = 1
        for category, functions in categories.items():
            if not functions:
                continue

            lines.append(f"### {chapter}.{section_num} {category.value}")
            lines.append("")

            for func in functions:
                lines.extend(self._generate_function_doc(func))
                lines.append("")
                lines.append("---")
                lines.append("")

            section_num += 1

        lines.append("---")
        return '\n'.join(lines)

    def _categorize_functions(self, functions: List[Function]) -> Dict[FunctionCategory, List[Function]]:
        """按分类组织函数"""
        categories = {
            FunctionCategory.INIT: [],
            FunctionCategory.BUSINESS: [],
            FunctionCategory.QUERY: [],
            FunctionCategory.CALLBACK: [],
            FunctionCategory.INTERNAL: [],
            FunctionCategory.UNKNOWN: [],
        }

        for func in functions:
            categories[func.category].append(func)

        return categories

    def _infer_description(self, func: Function) -> str:
        """从函数名推断中文功能描述"""
        name = func.name
        name_lower = name.lower()

        # 1. 先找动作
        action = ""
        is_prefix = False
        for pattern, (desc, prefix) in _FUNC_NAME_DESC_MAP.items():
            if re.search(pattern, name):
                action = desc
                is_prefix = prefix
                break

        # 2. 找领域关键词（排除与动作语义重复的，避免子串重复）
        domain_parts = []
        matched_kw = {}  # kw -> (cn, position)
        # 按关键词长度降序排列，优先匹配长关键词
        sorted_keywords = sorted(_DOMAIN_KEYWORDS.items(), key=lambda x: -len(x[0]))
        for kw, cn in sorted_keywords:
            if kw in name_lower:
                # 去重：如果已匹配的长关键词包含当前关键词，跳过
                if any(kw in mkw for mkw in matched_kw):
                    continue
                # 去重：如果领域词的每个字符都已出现在动作描述中，跳过
                if action and all(ch in action for ch in cn if ch not in '/、'):
                    continue
                pos = name_lower.find(kw)
                matched_kw[kw] = (cn, pos)

        # 按在函数名中的位置排序
        domain_parts = [cn for cn, _ in sorted(matched_kw.values(), key=lambda x: x[1])]

        domain = ''.join(domain_parts)

        # 3. 组合结果
        if action and domain:
            if is_prefix:
                return f"{action}{domain}"
            else:
                return f"{domain}{action}"
        elif action:
            return action
        elif domain:
            return domain

        # 4. 兜底：分段解析
        parts = name.split('_')
        if len(parts) > 1:
            last = parts[-1].lower()
            for pattern, (desc, _) in _FUNC_NAME_DESC_MAP.items():
                if re.search(pattern, f'_{last}$'):
                    return desc

        return ""

    def _generate_function_doc(self, func: Function) -> List[str]:
        """生成函数文档"""
        # 确定功能描述：优先用注释，否则推断
        description = func.description or func.brief or ""
        if not description or description == '待补充':
            description = self._infer_description(func) or "待补充"

        lines = [
            f"#### {func.name}",
            "",
            f"**功能**: {description}",
            "",
            "**函数原型**:",
            "```c",
            func.to_signature(),
            "```",
            "",
        ]

        # 参数表
        if func.params:
            lines.extend([
                "**参数**:",
                "",
                "| 参数名 | 类型 | 方向 | 说明 |",
                "|--------|------|------|------|",
            ])

            for param in func.params:
                direction = param.direction.value if param.direction else "IN"
                desc = param.description or "待补充"
                # 类型显示：补充指针/数组修饰
                ptype = param.type
                if param.is_pointer:
                    ptype += " *"
                if param.is_array and param.array_size:
                    ptype += f"[{param.array_size}]"
                elif param.is_array:
                    ptype += "[]"
                lines.append(f"| `{param.name}` | `{ptype}` | {direction} | {desc} |")

            lines.append("")

        # 返回值
        return_desc = func.return_desc or ("无" if func.return_type == "void" else "待补充")
        lines.extend([
            f"**返回值**: `{func.return_type}` - {return_desc}",
            "",
        ])

        # 使用说明
        if func.notes:
            lines.append("**使用说明**:")
            for note in func.notes:
                lines.append(f"- {note}")
            lines.append("")

        # 相关函数
        if func.see_also:
            lines.append("**相关函数**:")
            for see in func.see_also:
                lines.append(f"- `{see}`")
            lines.append("")

        return lines

    def _generate_macros_section(self, macros: List[Macro], chapter: int) -> str:
        """生成常量/宏定义章节（分类展示所有未在前面章节出现的宏）"""
        lines = [f"## {chapter}. 常量定义", ""]

        # 按类别分组
        groups: Dict[str, List[Macro]] = {}
        for m in macros:
            cat = m.category or "常量"
            groups.setdefault(cat, []).append(m)

        sub_num = 1
        for cat_name, cat_macros in groups.items():
            if cat_name in ("硬件配置", "协议常量"):
                continue  # 已在前述章节展示
            lines.append(f"### {chapter}.{sub_num} {cat_name}")
            lines.append("")
            lines.append("| 宏名称 | 值 | 说明 |")
            lines.append("|--------|-----|------|")
            for macro in cat_macros:
                value = f"`{macro.value}`" if macro.value else "-"
                desc = macro.description or "待补充"
                lines.append(f"| `{macro.name}` | {value} | {desc} |")
            lines.append("")
            sub_num += 1

        lines.append("---")
        return '\n'.join(lines)

    def _generate_examples_section(self, chapter: int) -> str:
        """生成使用示例章节"""
        lines = [
            f"## {chapter}. 使用示例",
            "",
            "```c",
            "// 待补充",
            "```",
            "",
            "---"
        ]
        return '\n'.join(lines)

    def _generate_limitations_section(self, chapter: int) -> str:
        """生成已知限制章节"""
        lines = [
            f"## {chapter}. 已知限制",
            "",
            "- 待补充",
            "",
            "---"
        ]
        return '\n'.join(lines)

    def _generate_porting_section(self, ir: ModuleIR, chapter: int) -> str:
        """生成移植说明章节"""
        lines = [
            f"## {chapter}. 移植说明",
            "",
            f"### {chapter}.1 硬件依赖",
            "",
            "待补充",
            "",
            f"### {chapter}.2 移植步骤",
            "",
            "1. 待补充",
            "",
            "---"
        ]
        return '\n'.join(lines)

    def _generate_references_section(self, chapter: int) -> str:
        """生成参考资料章节"""
        lines = [
            f"## {chapter}. 参考资料",
            "",
            "- 待补充",
            "",
            "---"
        ]
        return '\n'.join(lines)

    def _generate_changelog_section(self, ir: ModuleIR, chapter: int) -> str:
        """生成版本历史章节"""
        lines = [
            f"## {chapter}. 版本历史",
            "",
            "| 版本 | 日期 | 变更说明 |",
            "|------|------|----------|",
            f"| v1.0 | {ir.generated_time[:10]} | 初始版本 |",
            "",
            "---"
        ]
        return '\n'.join(lines)

    def _generate_validation_report_section(self, report: ValidationReport, chapter: int) -> str:
        """生成校验报告章节（精简版：去重，INFO 不逐条展示）"""
        lines = [
            f"## {chapter}. 校验报告",
            "",
            "```",
        ]

        errors = [r for r in report.results if r.level == "ERROR"]
        warnings = self._deduplicate_results([r for r in report.results if r.level == "WARNING"])
        infos = [r for r in report.results if r.level == "INFO"]

        if errors:
            lines.append("=== 错误 ===")
            for r in errors:
                lines.append(f"[ERROR] {r.message}")

        if warnings:
            lines.append("")
            lines.append("=== 警告 ===")
            for r in warnings:
                loc_str = f" ({r.location})" if r.location else ""
                lines.append(f"[WARNING] {r.message}{loc_str}")

        if infos:
            # INFO 只显示汇总，不逐条列出
            # 统计 INFO 类型
            info_types: Dict[str, int] = {}
            for r in infos:
                key = r.message.split('(')[0].strip() if '(' in r.message else r.message
                info_types[key] = info_types.get(key, 0) + 1

            lines.append("")
            lines.append("=== 提示 ===")
            for msg, count in info_types.items():
                lines.append(f"[INFO] {msg} (共 {count} 条)")

        total_errors = len(errors)
        total_warnings = len(warnings)
        total_infos = len(infos)
        lines.append("")
        lines.append(f"总计: {total_errors} 错误, {total_warnings} 警告, {total_infos} 提示")
        lines.append("```")
        lines.append("")

        return '\n'.join(lines)

    def _deduplicate_results(self, results: list) -> list:
        """去重校验结果（合并不同校验器对同一结构的相似警告）"""
        seen = set()
        deduped = []
        for r in results:
            # 以结构体/函数名 + "覆盖率" 作为去重 key（合并不同校验器的重复报告）
            msg = r.message
            struct_match = re.search(r"结构体\s+'(\w+)'", msg)
            func_match = re.search(r"函数\s+'(\w+)'", msg)

            if struct_match and '覆盖率' in msg:
                # 同一结构体的覆盖率警告，只保留第一条
                key = f"struct_coverage:{struct_match.group(1)}"
            elif func_match and '没有声明' in msg and 'static' not in msg:
                # 同一函数的"没有声明"警告
                key = f"no_decl:{func_match.group(1)}"
            else:
                key = msg.split('(')[0].strip() if '(' in msg else msg

            if key not in seen:
                seen.add(key)
                deduped.append(r)
        return deduped
