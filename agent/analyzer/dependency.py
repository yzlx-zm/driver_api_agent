"""依赖关系分析器

分析函数、模块之间的依赖和调用关系
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple, Optional
import re


@dataclass
class DependencyNode:
    """依赖图节点"""
    id: str
    name: str
    type: str  # 'function', 'struct', 'enum', 'macro'
    is_public: bool = True


@dataclass
class DependencyEdge:
    """依赖图边"""
    source: str  # 源节点 ID
    target: str  # 目标节点 ID
    type: str    # 'calls', 'uses', 'implements', 'references'
    label: str = ""


@dataclass
class DependencyGraph:
    """依赖关系图"""
    nodes: List[DependencyNode] = field(default_factory=list)
    edges: List[DependencyEdge] = field(default_factory=list)

    def get_node(self, node_id: str) -> Optional[DependencyNode]:
        """获取节点"""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def get_outgoing_edges(self, node_id: str) -> List[DependencyEdge]:
        """获取节点的出边"""
        return [e for e in self.edges if e.source == node_id]

    def get_incoming_edges(self, node_id: str) -> List[DependencyEdge]:
        """获取节点的入边"""
        return [e for e in self.edges if e.target == node_id]


class DependencyAnalyzer:
    """依赖关系分析器"""

    def __init__(self, config: dict = None):
        self.config = config or {}

    def analyze(self, ir) -> DependencyGraph:
        """分析 IR，构建依赖图"""
        graph = DependencyGraph()

        # 1. 添加节点
        self._add_nodes(ir, graph)

        # 2. 分析函数调用关系
        self._analyze_function_calls(ir, graph)

        # 3. 分析类型使用关系
        self._analyze_type_usage(ir, graph)

        # 4. 分析结构体字段依赖
        self._analyze_struct_fields(ir, graph)

        return graph

    def _add_nodes(self, ir, graph: DependencyGraph):
        """添加所有节点"""
        # 添加函数节点
        for func in ir.functions:
            graph.nodes.append(DependencyNode(
                id=f"func:{func.name}",
                name=func.name,
                type="function",
                is_public=func.is_public if hasattr(func, 'is_public') else True
            ))

        # 添加结构体节点
        for struct in ir.structs:
            graph.nodes.append(DependencyNode(
                id=f"struct:{struct.name}",
                name=struct.name,
                type="struct",
                is_public=True
            ))

        # 添加枚举节点
        for enum in ir.enums:
            graph.nodes.append(DependencyNode(
                id=f"enum:{enum.name}",
                name=enum.name,
                type="enum",
                is_public=True
            ))

    def _analyze_function_calls(self, ir, graph: DependencyGraph):
        """分析函数调用关系"""
        # 构建函数名到ID的映射
        func_names = {f.name for f in ir.functions}

        for func in ir.functions:
            # 从函数描述和注释中推断调用关系
            text = f"{func.description or ''} {func.brief or ''}"

            # 检查文本中提到的其他函数
            for other_func in ir.functions:
                if other_func.name != func.name and other_func.name in text:
                    graph.edges.append(DependencyEdge(
                        source=f"func:{func.name}",
                        target=f"func:{other_func.name}",
                        type="references",
                        label="提及"
                    ))

    def _analyze_type_usage(self, ir, graph: DependencyGraph):
        """分析类型使用关系"""
        struct_names = {s.name for s in ir.structs}
        enum_names = {e.name for e in ir.enums}

        for func in ir.functions:
            # 检查参数中使用的类型
            for param in func.params:
                ptype = param.type
                if '*' in ptype:
                    ptype = ptype.replace('*', '').strip()

                # 检查是否使用了结构体
                if ptype in struct_names:
                    graph.edges.append(DependencyEdge(
                        source=f"func:{func.name}",
                        target=f"struct:{ptype}",
                        type="uses",
                        label="参数类型"
                    ))

                # 检查是否使用了枚举
                if ptype in enum_names:
                    graph.edges.append(DependencyEdge(
                        source=f"func:{func.name}",
                        target=f"enum:{ptype}",
                        type="uses",
                        label="参数类型"
                    ))

            # 检查返回值类型
            ret_type = func.return_type
            if '*' in ret_type:
                ret_type = ret_type.replace('*', '').strip()

            if ret_type in struct_names:
                graph.edges.append(DependencyEdge(
                    source=f"func:{func.name}",
                    target=f"struct:{ret_type}",
                    type="uses",
                    label="返回类型"
                ))

            if ret_type in enum_names:
                graph.edges.append(DependencyEdge(
                    source=f"func:{func.name}",
                    target=f"enum:{ret_type}",
                    type="uses",
                    label="返回类型"
                ))

    def _analyze_struct_fields(self, ir, graph: DependencyGraph):
        """分析结构体字段中的类型依赖"""
        struct_names = {s.name for s in ir.structs}
        enum_names = {e.name for e in ir.enums}

        for struct in ir.structs:
            for field in struct.fields:
                ftype = field.type
                if '[' in ftype:
                    ftype = ftype.split('[')[0].strip()
                if '*' in ftype:
                    ftype = ftype.replace('*', '').strip()

                # 检查是否引用了其他结构体
                if ftype in struct_names and ftype != struct.name:
                    graph.edges.append(DependencyEdge(
                        source=f"struct:{struct.name}",
                        target=f"struct:{ftype}",
                        type="references",
                        label="字段类型"
                    ))

                # 检查是否引用了枚举
                if ftype in enum_names:
                    graph.edges.append(DependencyEdge(
                        source=f"struct:{struct.name}",
                        target=f"enum:{ftype}",
                        type="uses",
                        label="字段类型"
                    ))

    def to_mermaid(self, graph: DependencyGraph, max_nodes: int = 20) -> str:
        """转换为 Mermaid 图表代码"""
        lines = ["graph TB"]

        # 限制节点数量
        nodes = graph.nodes[:max_nodes]
        node_ids = {n.id for n in nodes}

        # 过滤边
        edges = [e for e in graph.edges if e.source in node_ids and e.target in node_ids]

        # 添加节点定义
        for node in nodes:
            shape = "["
            if node.type == "function":
                shape = "(" if node.is_public else "(["
            elif node.type == "struct":
                shape = "["
            elif node.type == "enum":
                shape = "{"

            end_shape = {")", "]", "})", "]}", ")"}.pop() if shape in {"(", "([", "[", "{"} else "]"
            if shape == "(":
                end_shape = ")"
            elif shape == "([":
                end_shape = "])"
            elif shape == "[":
                end_shape = "]"
            elif shape == "{":
                end_shape = "}"

            # 使用简化的 ID
            node_id = node.id.replace(":", "_")
            lines.append(f"    {node_id}{shape}\"{node.name}\"{end_shape}")

        # 添加边
        for edge in edges[:max_nodes * 2]:
            source = edge.source.replace(":", "_")
            target = edge.target.replace(":", "_")
            label = f"|{edge.label}|" if edge.label else ""
            lines.append(f"    {source} -->{label} {target}")

        return "\n".join(lines)
