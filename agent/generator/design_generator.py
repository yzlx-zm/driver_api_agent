"""设计文档生成器

基于 IR 生成设计文档，包含架构图、依赖关系、数据流、时序图
"""

from typing import List, Optional
from datetime import datetime

from ..analyzer.architecture import ArchitectureAnalyzer, ArchitectureInfo
from ..analyzer.dependency import DependencyAnalyzer, DependencyGraph
from ..analyzer.dataflow import DataflowAnalyzer, DataflowInfo
from ..analyzer.sequence import SequenceAnalyzer, SequenceInfo
from ..models.ir import ModuleIR
from ..llm.description_generator import create_llm_client, DescriptionGenerator as LLMDescriptionGenerator


class DesignGenerator:
    """设计文档生成器"""

    def __init__(self, config: dict = None, llm_client=None):
        self.config = config or {}
        self.arch_analyzer = ArchitectureAnalyzer(config)
        self.dep_analyzer = DependencyAnalyzer(config)
        self.flow_analyzer = DataflowAnalyzer(config)
        self.seq_analyzer = SequenceAnalyzer(config)
        self.llm_client = llm_client
        self.llm_generator = None

        # 初始化 LLM 生成器（如果配置了）
        if llm_client and self.config.get('llm_enabled', False):
            self.llm_generator = LLMDescriptionGenerator(
                llm_client,
                {'auto_generate_desc': True}
            )

    def _get_description(self, obj, obj_type: str = "function") -> str:
        """
        获取对象的描述，如果缺失则尝试用 LLM 生成

        Args:
            obj: 函数/结构体/枚举等对象
            obj_type: 对象类型 (function/struct/enum/field)

        Returns:
            描述文本
        """
        # 优先使用现有描述
        desc = getattr(obj, 'description', None) or getattr(obj, 'brief', None)
        if desc and desc != '待补充':
            return desc

        # 如果配置了 LLM，尝试生成描述
        if self.llm_generator and self.config.get('llm_enabled', False):
            try:
                if obj_type == "function":
                    return self.llm_generator.generate_function_description(obj)
                elif obj_type == "field":
                    return self.llm_generator.generate_field_description(obj)
                elif obj_type == "struct":
                    return self.llm_generator.generate_struct_description(obj)
            except Exception:
                pass  # LLM 生成失败时回退到默认值

        return "待补充"

    def generate(self, ir: ModuleIR, arch_info: ArchitectureInfo = None,
                 dep_graph: DependencyGraph = None,
                 flow_info: DataflowInfo = None,
                 seq_info: SequenceInfo = None) -> str:
        """生成设计文档"""
        # 分析架构
        if arch_info is None:
            arch_info = self.arch_analyzer.analyze(ir)

        # 分析依赖
        if dep_graph is None:
            dep_graph = self.dep_analyzer.analyze(ir)

        # 分析数据流
        if flow_info is None:
            flow_info = self.flow_analyzer.analyze(ir)

        # 分析时序
        if seq_info is None:
            seq_info = self.seq_analyzer.analyze(ir)

        # 生成文档
        lines = []
        lines.extend(self._generate_header(arch_info))
        lines.extend(self._generate_overview(arch_info))
        lines.extend(self._generate_architecture(arch_info))
        lines.extend(self._generate_dependency_graph(dep_graph))
        lines.extend(self._generate_dataflow(flow_info))
        lines.extend(self._generate_sequences(seq_info))
        lines.extend(self._generate_interface_design(ir))
        lines.extend(self._generate_data_structures(ir))
        lines.extend(self._generate_design_decisions(ir, arch_info))
        lines.extend(self._generate_porting_guide(ir, arch_info))
        lines.extend(self._generate_footer())

        return "\n".join(lines)

    def _generate_header(self, arch_info: ArchitectureInfo) -> List[str]:
        """生成文档头部"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return [
            f"# {arch_info.module_name.upper()} 设计文档",
            "",
            f"> 生成时间: {now}",
            f"> 代码版本: unknown",
            "",
            "---",
            "",
        ]

    def _generate_overview(self, arch_info: ArchitectureInfo) -> List[str]:
        """生成概述章节"""
        lines = [
            "<!-- AUTO-GENERATED-START:overview -->",
            "## 1. 概述",
            "",
            "### 1.1 模块定位",
            "",
            f"本模块为 **{arch_info.module_purpose or '驱动'}** 提供软件接口。",
            "",
            "### 1.2 核心功能",
            "",
        ]

        # 添加组件功能说明
        for comp in arch_info.components:
            if comp.is_public:
                func_list = ", ".join([f"`{f}()`" for f in comp.functions[:3]])
                if len(comp.functions) > 3:
                    func_list += f" 等 {len(comp.functions)} 个函数"
                lines.append(f"- **{comp.name}**: {func_list}")

        lines.extend([
            "",
            "### 1.3 适用场景",
            "",
            "- 嵌入式设备驱动开发",
            "- 硬件抽象层实现",
            "- 模块化软件架构",
            "",
            "---",
            "<!-- AUTO-GENERATED-END:overview -->",
            "",
        ])

        return lines

    def _generate_architecture(self, arch_info: ArchitectureInfo) -> List[str]:
        """生成架构设计章节"""
        lines = [
            "<!-- AUTO-GENERATED-START:architecture -->",
            "## 2. 架构设计",
            "",
            "### 2.1 整体架构",
            "",
            "```mermaid",
            "graph TB",
        ]

        # 生成架构图
        # 添加组件节点
        for i, comp in enumerate(arch_info.components[:8]):
            node_id = f"comp_{i}"
            # 根据组件类型选择形状
            if comp.type.value == "初始化":
                lines.append(f"    {node_id}(\"{comp.name}\")")
            elif comp.type.value == "内部实现":
                lines.append(f"    {node_id}[[\"{comp.name}\"]]")
            else:
                lines.append(f"    {node_id}[\"{comp.name}\"]")

        # 添加层次连接
        if len(arch_info.components) >= 2:
            # 初始化 -> 业务
            init_comps = [c for c in arch_info.components if "初始化" in c.name]
            biz_comps = [c for c in arch_info.components if "业务" in c.name or "处理" in c.name]

            if init_comps and biz_comps:
                lines.append(f"    comp_0 --> comp_1")

        lines.extend([
            "```",
            "",
            "### 2.2 模块划分",
            "",
        ])

        # 模块划分表格
        lines.extend([
            "| 模块 | 类型 | 主要函数 | 说明 |",
            "|------|------|----------|------|",
        ])

        for comp in arch_info.components[:6]:
            funcs = ", ".join(comp.functions[:2])
            if len(comp.functions) > 2:
                funcs += "..."
            lines.append(f"| {comp.name} | {comp.type.value} | {funcs} | - |")

        lines.extend([
            "",
            "### 2.3 入口函数",
            "",
        ])

        if arch_info.entry_points:
            for ep in arch_info.entry_points:
                lines.append(f"- `{ep}()`")
        else:
            lines.append("- (待识别)")

        lines.extend([
            "",
            "---",
            "<!-- AUTO-GENERATED-END:architecture -->",
            "",
        ])

        return lines

    def _generate_dependency_graph(self, dep_graph: DependencyGraph) -> List[str]:
        """生成模块关系图章节"""
        lines = [
            "<!-- AUTO-GENERATED-START:dependency -->",
            "## 3. 模块关系图",
            "",
            "```mermaid",
        ]

        # 生成简化的依赖图
        lines.append("graph LR")

        # 添加应用层节点
        lines.append("    app[\"应用层\"]")

        # 添加核心模块
        lines.append("    driver[\"驱动模块\"]")

        # 添加硬件层
        lines.append("    hw[\"硬件层\"]")

        # 添加连接
        lines.append("    app -->|调用 API| driver")
        lines.append("    driver -->|寄存器操作| hw")
        lines.append("    hw -->|中断/回调| driver")
        lines.append("    driver -->|事件通知| app")

        lines.extend([
            "```",
            "",
            "**依赖说明**:",
            "",
            "- **应用层**: 调用驱动模块的公开 API",
            "- **驱动模块**: 封装硬件操作，提供统一接口",
            "- **硬件层**: 通过寄存器/总线与设备通信",
            "",
            "---",
            "<!-- AUTO-GENERATED-END:dependency -->",
            "",
        ])

        return lines

    def _generate_dataflow(self, flow_info: DataflowInfo) -> List[str]:
        """生成数据流图章节"""
        lines = [
            "<!-- AUTO-GENERATED-START:dataflow -->",
            "## 4. 数据流图",
            "",
            "### 4.1 数据流向",
            "",
            "```mermaid",
            "flowchart LR",
            "    A[\"输入参数\"] --> B[\"参数校验\"]",
            "    B --> C[\"数据打包\"]",
            "    C --> D[\"发送请求\"]",
            "    D --> E[\"等待响应\"]",
            "    E --> F[\"解包数据\"]",
            "    F --> G[\"返回结果\"]",
            "```",
            "",
            "### 4.2 数据缓冲区",
            "",
        ]

        if flow_info.buffers:
            for buf in flow_info.buffers[:5]:
                lines.append(f"- {buf}")
        else:
            lines.append("- (待分析)")

        lines.extend([
            "",
            "### 4.3 数据流描述",
            "",
        ])

        if flow_info.flows:
            for flow in flow_info.flows:
                lines.append(f"- {flow}")
        else:
            lines.append("- (待分析)")

        lines.extend([
            "",
            "---",
            "<!-- AUTO-GENERATED-END:dataflow -->",
            "",
        ])

        return lines

    def _generate_sequences(self, seq_info: SequenceInfo) -> List[str]:
        """生成时序图章节"""
        lines = [
            "<!-- AUTO-GENERATED-START:sequence -->",
            "## 5. 核心流程",
            "",
        ]

        # 为每个场景生成时序图
        for i, scenario in enumerate(seq_info.scenarios[:3]):
            lines.extend([
                f"### 5.{i+1} {scenario.name}",
                "",
            ])

            if scenario.description:
                lines.extend([
                    f"{scenario.description}",
                    "",
                ])

            # 生成 Mermaid 时序图
            lines.append("```mermaid")
            lines.extend(self.seq_analyzer.to_mermaid(scenario).split("\n"))
            lines.extend([
                "```",
                "",
            ])

        # 主要流程描述
        if seq_info.main_flows:
            lines.extend([
                "### 主要流程",
                "",
            ])
            for flow in seq_info.main_flows:
                lines.append(f"- {flow}")
            lines.append("")

        lines.extend([
            "---",
            "<!-- AUTO-GENERATED-END:sequence -->",
            "",
        ])

        return lines

    def _generate_interface_design(self, ir: ModuleIR) -> List[str]:
        """生成接口设计章节"""
        lines = [
            "<!-- AUTO-GENERATED-START:interface -->",
            "## 6. 接口设计",
            "",
            "### 6.1 公开接口",
            "",
        ]

        # 公开函数表格
        public_funcs = [f for f in ir.functions if f.is_public or not hasattr(f, 'is_public')]
        if public_funcs:
            lines.extend([
                "| 函数 | 说明 |",
                "|------|------|",
            ])
            for func in public_funcs[:15]:
                desc = self._get_description(func, "function")
                if len(desc) > 30:
                    desc = desc[:30] + "..."
                lines.append(f"| `{func.name}()` | {desc} |")

            if len(public_funcs) > 15:
                lines.append(f"| ... | 共 {len(public_funcs)} 个接口 |")

        lines.extend([
            "",
            "### 6.2 回调接口",
            "",
        ])

        # 回调函数 - 扩展识别规则
        callback_keywords = ['callback', 'handler', 'on_', 'notify', 'listener', 'event', 'cb_']
        callback_funcs = [f for f in ir.functions
                          if any(kw in f.name.lower() for kw in callback_keywords)]

        # 同时检查函数参数中是否有函数指针类型
        if hasattr(ir, 'typedefs'):
            for typedef in ir.typedefs:
                if 'callback' in typedef.name.lower() or 'handler' in typedef.name.lower():
                    # 如果有函数指针 typedef，查找使用它的函数
                    for f in ir.functions:
                        for param in f.params:
                            if typedef.name in param.type:
                                if f not in callback_funcs:
                                    callback_funcs.append(f)

        if callback_funcs:
            lines.extend([
                "| 回调 | 说明 |",
                "|------|------|",
            ])
            for func in callback_funcs[:5]:
                desc = self._get_description(func, "function")
                lines.append(f"| `{func.name}()` | {desc} |")
            if len(callback_funcs) > 5:
                lines.append(f"| ... | 共 {len(callback_funcs)} 个回调 |")
        else:
            lines.append("无显式回调接口。")

        lines.extend([
            "",
            "### 6.3 内部接口",
            "",
        ])

        # 内部函数
        internal_funcs = [f for f in ir.functions if f.is_static or f.name.startswith('_')]
        if internal_funcs:
            lines.append(f"共 {len(internal_funcs)} 个内部函数（static 或 `_` 前缀）。")
        else:
            lines.append("无内部接口。")

        lines.extend([
            "",
            "---",
            "<!-- AUTO-GENERATED-END:interface -->",
            "",
        ])

        return lines

    def _generate_data_structures(self, ir: ModuleIR) -> List[str]:
        """生成数据结构设计章节"""
        lines = [
            "<!-- AUTO-GENERATED-START:datastruct -->",
            "## 7. 数据结构设计",
            "",
            "### 7.1 核心数据结构",
            "",
        ]

        if ir.structs:
            for struct in ir.structs[:5]:
                lines.append(f"#### {struct.name}")
                lines.append("")
                if struct.description:
                    lines.append(f"{struct.description}")
                    lines.append("")

                lines.extend([
                    "| 字段 | 类型 | 说明 |",
                    "|------|------|------|",
                ])

                for field in struct.fields[:8]:
                    desc = self._get_description(field, "field")
                    if len(desc) > 25:
                        desc = desc[:25] + "..."
                    lines.append(f"| `{field.name}` | `{field.type}` | {desc} |")

                if len(struct.fields) > 8:
                    lines.append(f"| ... | ... | 共 {len(struct.fields)} 个字段 |")

                lines.append("")

        lines.extend([
            "### 7.2 枚举类型",
            "",
        ])

        if ir.enums:
            for enum in ir.enums[:3]:
                lines.append(f"#### {enum.name}")
                lines.append("")
                if enum.description:
                    lines.append(f"{enum.description}")
                    lines.append("")

                for value in enum.values[:6]:
                    lines.append(f"- `{value.name}`: {value.description or value.value}")

                if len(enum.values) > 6:
                    lines.append(f"- ... 共 {len(enum.values)} 个枚举值")

                lines.append("")

        lines.extend([
            "---",
            "<!-- AUTO-GENERATED-END:datastruct -->",
            "",
        ])

        return lines

    def _generate_design_decisions(self, ir: ModuleIR, arch_info: ArchitectureInfo) -> List[str]:
        """生成设计决策章节"""
        lines = [
            "<!-- AUTO-GENERATED-START:decisions -->",
            "## 8. 设计决策",
            "",
            "### 8.1 关键技术选择",
            "",
        ]

        # 基于代码分析推断设计决策
        decisions = []

        # 检查是否使用异步模式
        async_funcs = [f for f in ir.functions if 'async' in f.name.lower() or 'nonblock' in f.name.lower()]
        if async_funcs:
            decisions.append("- **异步处理模式**: 支持非阻塞调用和回调机制")

        # 检查是否有状态机
        state_enums = [e for e in ir.enums if 'state' in e.name.lower()]
        if state_enums:
            decisions.append("- **状态机设计**: 使用枚举定义模块运行状态")

        # 检查是否有错误码
        error_enums = [e for e in ir.enums if 'error' in e.name.lower() or 'result' in e.name.lower()]
        if error_enums:
            decisions.append("- **错误处理**: 定义统一的错误码和结果码")

        # 检查缓冲区管理
        buf_macros = [m for m in ir.macros if 'buf' in m.name.lower() or 'size' in m.name.lower()]
        if buf_macros:
            decisions.append("- **缓冲区管理**: 使用宏定义固定大小缓冲区")

        if decisions:
            lines.extend(decisions)
        else:
            lines.append("- (待补充)")

        lines.extend([
            "",
            "### 8.2 限制与约束",
            "",
            "- 线程安全: 需要外部同步保护（如有并发需求）",
            "- 内存管理: 使用静态分配，避免动态内存",
            "- 平台依赖: 需要实现底层硬件抽象层",
            "",
            "### 8.3 扩展点设计",
            "",
            "- 回调机制: 可注册自定义事件处理函数",
            "- 配置接口: 运行时可调整参数配置",
            "",
            "---",
            "<!-- AUTO-GENERATED-END:decisions -->",
            "",
        ])

        return lines

    def _generate_porting_guide(self, ir: ModuleIR, arch_info: ArchitectureInfo) -> List[str]:
        """生成移植指南章节"""
        lines = [
            "<!-- AUTO-GENERATED-START:porting -->",
            "## 9. 移植指南",
            "",
            "### 9.1 硬件依赖",
            "",
        ]

        # 列出硬件依赖
        if arch_info.dependencies:
            for dep in arch_info.dependencies:
                lines.append(f"- {dep}")
        else:
            lines.append("- GPIO")
            lines.append("- UART/SPI/I2C (根据配置)")

        lines.extend([
            "",
            "### 9.2 平台适配",
            "",
            "移植到新平台需要:",
            "",
            "1. **GPIO 配置**: 实现 GPIO 初始化和控制接口",
            "2. **通信接口**: 实现 UART/SPI/I2C 收发函数",
            "3. **时序控制**: 提供毫秒级延时函数",
            "4. **中断处理**: 配置中断回调（如需要）",
            "",
            "### 9.3 配置说明",
            "",
        ])

        # 列出配置宏
        config_macros = [m for m in ir.macros
                         if any(kw in m.name.lower() for kw in ['config', 'enable', 'debug', 'timeout'])]
        if config_macros:
            lines.extend([
                "| 宏 | 默认值 | 说明 |",
                "|------|--------|------|",
            ])
            for macro in config_macros[:5]:
                lines.append(f"| `{macro.name}` | `{macro.value}` | {macro.description or '待补充'} |")
        else:
            lines.append("参见 `config/default.yaml` 配置文件。")

        lines.extend([
            "",
            "---",
            "<!-- AUTO-GENERATED-END:porting -->",
            "",
        ])

        return lines

    def _generate_footer(self) -> List[str]:
        """生成文档尾部"""
        return [
            "<!-- AUTO-GENERATED-START:footer -->",
            "---",
            "",
            "*本文档由 Driver API Doc Agent 自动生成*",
            "<!-- AUTO-GENERATED-END:footer -->",
            "",
        ]
