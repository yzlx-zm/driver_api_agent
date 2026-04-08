"""数据流分析器

分析数据在模块中的流动方向
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum


class DataDirection(Enum):
    """数据方向"""
    INPUT = "输入"
    OUTPUT = "输出"
    BIDIRECTIONAL = "双向"
    INTERNAL = "内部"


@dataclass
class DataEndpoint:
    """数据端点"""
    name: str
    type: str  # 'param', 'return', 'struct_field', 'buffer'
    direction: DataDirection
    data_type: str
    description: str = ""


@dataclass
class DataTransform:
    """数据转换"""
    source: str
    target: str
    function: str  # 执行转换的函数
    description: str = ""


@dataclass
class DataflowInfo:
    """数据流信息"""
    inputs: List[DataEndpoint] = field(default_factory=list)
    outputs: List[DataEndpoint] = field(default_factory=list)
    transforms: List[DataTransform] = field(default_factory=list)
    buffers: List[str] = field(default_factory=list)  # 数据缓冲区
    flows: List[str] = field(default_factory=list)    # 数据流描述


class DataflowAnalyzer:
    """数据流分析器"""

    # 输入参数关键词
    INPUT_KEYWORDS = ['param', 'config', 'input', 'src', 'source', 'data', 'value']

    # 输出参数关键词
    OUTPUT_KEYWORDS = ['result', 'output', 'dst', 'dest', 'response', 'buf', 'buffer']

    # 双向参数关键词
    BIDIRECTIONAL_KEYWORDS = ['handle', 'ctx', 'context']

    def __init__(self, config: dict = None):
        self.config = config or {}

    def analyze(self, ir) -> DataflowInfo:
        """分析 IR，提取数据流信息"""
        info = DataflowInfo()

        # 1. 分析输入端点
        info.inputs = self._analyze_inputs(ir)

        # 2. 分析输出端点
        info.outputs = self._analyze_outputs(ir)

        # 3. 分析数据转换
        info.transforms = self._analyze_transforms(ir)

        # 4. 识别缓冲区
        info.buffers = self._identify_buffers(ir)

        # 5. 生成数据流描述
        info.flows = self._generate_flow_descriptions(ir, info)

        return info

    def _analyze_inputs(self, ir) -> List[DataEndpoint]:
        """分析输入端点"""
        inputs = []

        for func in ir.functions:
            for param in func.params:
                direction = self._infer_param_direction(param)

                if direction in (DataDirection.INPUT, DataDirection.BIDIRECTIONAL):
                    inputs.append(DataEndpoint(
                        name=f"{func.name}.{param.name}",
                        type="param",
                        direction=direction,
                        data_type=param.type,
                        description=param.description or ""
                    ))

        return inputs

    def _analyze_outputs(self, ir) -> List[DataEndpoint]:
        """分析输出端点"""
        outputs = []

        for func in ir.functions:
            # 返回值作为输出
            if func.return_type != "void":
                outputs.append(DataEndpoint(
                    name=f"{func.name}.return",
                    type="return",
                    direction=DataDirection.OUTPUT,
                    data_type=func.return_type,
                    description=func.return_desc or ""
                ))

            # OUT/INOUT 参数
            for param in func.params:
                direction = self._infer_param_direction(param)

                if direction in (DataDirection.OUTPUT, DataDirection.BIDIRECTIONAL):
                    outputs.append(DataEndpoint(
                        name=f"{func.name}.{param.name}",
                        type="param",
                        direction=direction,
                        data_type=param.type,
                        description=param.description or ""
                    ))

        return outputs

    def _infer_param_direction(self, param) -> DataDirection:
        """推断参数方向"""
        name = param.name.lower()

        # 如果有明确的 direction 标注
        if hasattr(param, 'direction') and param.direction:
            dir_str = str(param.direction.value).upper() if hasattr(param.direction, 'value') else str(param.direction).upper()
            if dir_str == 'IN':
                return DataDirection.INPUT
            elif dir_str == 'OUT':
                return DataDirection.OUTPUT
            elif dir_str == 'INOUT':
                return DataDirection.BIDIRECTIONAL

        # 基于参数名推断
        if any(kw in name for kw in self.OUTPUT_KEYWORDS):
            if param.is_pointer:
                return DataDirection.OUTPUT

        if any(kw in name for kw in self.BIDIRECTIONAL_KEYWORDS):
            return DataDirection.BIDIRECTIONAL

        # 指针参数默认为输入
        if param.is_pointer:
            # const 指针通常是输入
            if 'const' in param.type.lower():
                return DataDirection.INPUT
            return DataDirection.INPUT

        return DataDirection.INPUT

    def _analyze_transforms(self, ir) -> List[DataTransform]:
        """分析数据转换"""
        transforms = []

        for func in ir.functions:
            name = func.name.lower()

            # 发送类函数：参数 -> 硬件
            if any(kw in name for kw in ['send', 'write', 'transmit', 'output']):
                for param in func.params:
                    if 'data' in param.name.lower() or 'buf' in param.name.lower():
                        transforms.append(DataTransform(
                            source=param.name,
                            target="硬件/总线",
                            function=func.name,
                            description=f"发送数据到硬件"
                        ))

            # 接收类函数：硬件 -> 参数
            if any(kw in name for kw in ['receive', 'read', 'input', 'recv']):
                for param in func.params:
                    if param.is_pointer and 'data' in param.name.lower():
                        transforms.append(DataTransform(
                            source="硬件/总线",
                            target=param.name,
                            function=func.name,
                            description=f"从硬件接收数据"
                        ))

            # 转换类函数
            if any(kw in name for kw in ['convert', 'transform', 'parse', 'pack', 'unpack']):
                if len(func.params) >= 2:
                    transforms.append(DataTransform(
                        source=func.params[0].name,
                        target=func.params[-1].name,
                        function=func.name,
                        description=func.description or func.brief or "数据转换"
                    ))

        return transforms

    def _identify_buffers(self, ir) -> List[str]:
        """识别数据缓冲区"""
        buffers = []

        # 从结构体中查找 buffer 字段
        for struct in ir.structs:
            for field in struct.fields:
                fname = field.name.lower()
                ftype = field.type.lower()
                if any(kw in fname for kw in ['buf', 'buffer', 'data', 'payload']):
                    buffers.append(f"{struct.name}.{field.name}")
                elif '[' in field.type and any(kw in ftype for kw in ['uint8', 'char', 'byte']):
                    buffers.append(f"{struct.name}.{field.name}")

        # 从宏定义中查找 buffer 大小
        for macro in ir.macros:
            if any(kw in macro.name.lower() for kw in ['buf', 'buffer', 'max', 'size']):
                if 'len' in macro.name.lower() or 'size' in macro.name.lower():
                    buffers.append(f"宏定义: {macro.name}")

        return buffers

    def _generate_flow_descriptions(self, ir, info: DataflowInfo) -> List[str]:
        """生成数据流描述"""
        flows = []

        # 基于函数分类生成流描述
        init_funcs = []
        send_funcs = []
        recv_funcs = []
        process_funcs = []

        for func in ir.functions:
            name = func.name.lower()
            if any(kw in name for kw in ['init', 'start', 'open']):
                init_funcs.append(func.name)
            elif any(kw in name for kw in ['send', 'write', 'transmit']):
                send_funcs.append(func.name)
            elif any(kw in name for kw in ['recv', 'read', 'receive']):
                recv_funcs.append(func.name)
            elif any(kw in name for kw in ['process', 'handle', 'execute']):
                process_funcs.append(func.name)

        # 生成描述
        if init_funcs:
            flows.append(f"初始化流程: {' -> '.join(init_funcs[:3])}")
        if send_funcs:
            flows.append(f"数据发送: 应用层 -> {send_funcs[0]} -> 硬件")
        if recv_funcs:
            flows.append(f"数据接收: 硬件 -> {recv_funcs[0]} -> 应用层")
        if process_funcs:
            flows.append(f"数据处理: {process_funcs[0]} -> 数据解析 -> 结果返回")

        return flows

    def to_mermaid(self, info: DataflowInfo) -> str:
        """转换为 Mermaid 流程图"""
        lines = ["flowchart LR"]

        # 添加输入节点
        lines.append("    subgraph Inputs[输入]")
        for i, inp in enumerate(info.inputs[:5]):
            node_id = f"in_{i}"
            lines.append(f"        {node_id}[\"{inp.name}\"]")
        lines.append("    end")

        # 添加处理节点
        lines.append("    subgraph Process[处理]")
        lines.append("        proc1[参数校验]")
        lines.append("        proc2[数据处理]")
        lines.append("        proc3[结果生成]")
        lines.append("    end")

        # 添加输出节点
        lines.append("    subgraph Outputs[输出]")
        for i, out in enumerate(info.outputs[:5]):
            node_id = f"out_{i}"
            lines.append(f"        {node_id}[\"{out.name}\"]")
        lines.append("    end")

        # 添加连接
        lines.append("    Inputs --> Process")
        lines.append("    Process --> Outputs")

        return "\n".join(lines)
