"""架构分析器

分析代码的整体架构、模块划分、层次结构
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from enum import Enum


class ComponentType(Enum):
    """组件类型"""
    INIT = "初始化"
    BUSINESS = "业务处理"
    DATA = "数据管理"
    CALLBACK = "回调处理"
    QUERY = "查询接口"
    CONTROL = "控制接口"
    UTILITY = "工具函数"
    INTERNAL = "内部实现"


@dataclass
class Component:
    """架构组件"""
    name: str
    type: ComponentType
    functions: List[str] = field(default_factory=list)
    description: str = ""
    is_public: bool = True


@dataclass
class Layer:
    """架构层次"""
    name: str
    components: List[Component] = field(default_factory=list)
    description: str = ""


@dataclass
class ArchitectureInfo:
    """架构信息"""
    module_name: str
    module_purpose: str = ""
    components: List[Component] = field(default_factory=list)
    layers: List[Layer] = field(default_factory=list)
    entry_points: List[str] = field(default_factory=list)  # 入口函数
    key_structs: List[str] = field(default_factory=list)   # 核心数据结构
    key_enums: List[str] = field(default_factory=list)     # 核心枚举
    dependencies: List[str] = field(default_factory=list)  # 外部依赖


class ArchitectureAnalyzer:
    """架构分析器"""

    # 初始化相关关键词
    INIT_KEYWORDS = ['init', 'deinit', 'start', 'stop', 'reset', 'begin', 'end', 'open', 'close']

    # 业务处理关键词
    BUSINESS_KEYWORDS = ['process', 'handle', 'execute', 'run', 'perform', 'send', 'receive',
                         'enroll', 'verify', 'delete', 'update', 'create', 'register']

    # 查询关键词
    QUERY_KEYWORDS = ['get', 'is', 'has', 'check', 'query', 'fetch', 'read', 'find']

    # 回调关键词
    CALLBACK_KEYWORDS = ['callback', 'handler', 'on_', 'notify', 'event', 'listener']

    # 控制关键词
    CONTROL_KEYWORDS = ['set', 'config', 'enable', 'disable', 'configure', 'setup']

    def __init__(self, config: dict = None):
        self.config = config or {}

    def analyze(self, ir) -> ArchitectureInfo:
        """分析 IR，提取架构信息"""
        info = ArchitectureInfo(
            module_name=self._extract_module_name(ir),
            module_purpose=self._infer_module_purpose(ir),
        )

        # 分析组件
        info.components = self._analyze_components(ir)

        # 分析层次
        info.layers = self._analyze_layers(ir, info.components)

        # 提取入口点
        info.entry_points = self._extract_entry_points(ir)

        # 提取核心数据结构
        info.key_structs = self._extract_key_structs(ir)
        info.key_enums = self._extract_key_enums(ir)

        # 提取外部依赖
        info.dependencies = self._extract_dependencies(ir)

        return info

    def _extract_module_name(self, ir) -> str:
        """提取模块名称"""
        if hasattr(ir, 'module') and ir.module:
            return ir.module.name or "Unknown"

        # 从函数名推断模块名
        if ir.functions:
            first_func = ir.functions[0].name
            # 去除常见后缀获取前缀
            for suffix in ['_init', '_deinit', '_start', '_stop', '_begin', '_end']:
                if first_func.endswith(suffix):
                    return first_func[:-len(suffix)]

            # 从下划线分割的第一部分获取
            parts = first_func.split('_')
            if len(parts) > 1:
                return parts[0]

        return "Unknown"

    def _infer_module_purpose(self, ir) -> str:
        """推断模块用途"""
        # 基于函数名和描述推断
        purposes = []

        for func in ir.functions[:10]:  # 检查前10个函数
            desc = func.description or func.brief or ""
            name = func.name.lower()

            if 'face' in name or '人脸' in desc:
                purposes.append("人脸识别")
            if 'palm' in name or '掌静脉' in desc or '掌纹' in desc:
                purposes.append("掌静脉识别")
            if 'uart' in name or 'serial' in name:
                purposes.append("串口通信")
            if 'spi' in name:
                purposes.append("SPI通信")
            if 'i2c' in name or 'iic' in name:
                purposes.append("I2C通信")
            if 'gpio' in name:
                purposes.append("GPIO控制")
            if 'lcd' in name or 'display' in name or 'screen' in name:
                purposes.append("显示屏驱动")
            if 'sensor' in name:
                purposes.append("传感器驱动")

        # 去重并返回
        unique_purposes = list(dict.fromkeys(purposes))
        return "、".join(unique_purposes) if unique_purposes else "驱动模块"

    def _analyze_components(self, ir) -> List[Component]:
        """分析组件划分"""
        components: Dict[ComponentType, Component] = {}

        for func in ir.functions:
            comp_type = self._classify_function(func)

            if comp_type not in components:
                components[comp_type] = Component(
                    name=self._get_component_name(comp_type),
                    type=comp_type,
                    is_public=True
                )

            components[comp_type].functions.append(func.name)

        return list(components.values())

    def _classify_function(self, func) -> ComponentType:
        """分类函数到组件类型"""
        name = func.name.lower()

        # 检查是否为静态/内部函数
        if func.is_static or name.startswith('_'):
            # 检查是否为回调
            for kw in self.CALLBACK_KEYWORDS:
                if kw in name:
                    return ComponentType.CALLBACK
            return ComponentType.INTERNAL

        # 初始化相关
        for kw in self.INIT_KEYWORDS:
            if kw in name:
                return ComponentType.INIT

        # 回调相关
        for kw in self.CALLBACK_KEYWORDS:
            if kw in name:
                return ComponentType.CALLBACK

        # 查询相关
        for kw in self.QUERY_KEYWORDS:
            if name.startswith(kw) or f'_{kw}' in name:
                return ComponentType.QUERY

        # 控制相关
        for kw in self.CONTROL_KEYWORDS:
            if name.startswith(kw) or f'_{kw}' in name:
                return ComponentType.CONTROL

        # 业务处理
        for kw in self.BUSINESS_KEYWORDS:
            if kw in name:
                return ComponentType.BUSINESS

        # 默认为业务处理
        return ComponentType.BUSINESS

    def _get_component_name(self, comp_type: ComponentType) -> str:
        """获取组件显示名称"""
        names = {
            ComponentType.INIT: "初始化模块",
            ComponentType.BUSINESS: "业务处理模块",
            ComponentType.DATA: "数据管理模块",
            ComponentType.CALLBACK: "回调处理模块",
            ComponentType.QUERY: "查询接口模块",
            ComponentType.CONTROL: "控制接口模块",
            ComponentType.UTILITY: "工具函数模块",
            ComponentType.INTERNAL: "内部实现模块",
        }
        return names.get(comp_type, "其他模块")

    def _analyze_layers(self, ir, components: List[Component]) -> List[Layer]:
        """分析架构层次"""
        layers = []

        # 接口层 - 公开 API
        public_funcs = [c for c in components if c.is_public and c.type != ComponentType.INTERNAL]
        if public_funcs:
            layers.append(Layer(
                name="接口层",
                components=public_funcs,
                description="对外公开的 API 接口"
            ))

        # 实现层 - 内部实现
        internal_funcs = [c for c in components if c.type == ComponentType.INTERNAL]
        if internal_funcs:
            layers.append(Layer(
                name="实现层",
                components=internal_funcs,
                description="内部实现函数"
            ))

        return layers

    def _extract_entry_points(self, ir) -> List[str]:
        """提取入口函数"""
        entry_points = []

        for func in ir.functions:
            if func.is_public:
                name = func.name.lower()
                for kw in self.INIT_KEYWORDS:
                    if kw in name:
                        entry_points.append(func.name)
                        break

        return entry_points[:5]  # 最多返回5个

    def _extract_key_structs(self, ir) -> List[str]:
        """提取核心数据结构"""
        key_structs = []

        for struct in ir.structs:
            name = struct.name.lower()
            # 上下文/配置/参数结构通常是核心
            if any(kw in name for kw in ['ctx', 'context', 'config', 'param', 'handle']):
                key_structs.append(struct.name)

        return key_structs[:5]

    def _extract_key_enums(self, ir) -> List[str]:
        """提取核心枚举"""
        key_enums = []

        for enum in ir.enums:
            name = enum.name.lower()
            # 状态/错误码/命令枚举通常是核心
            if any(kw in name for kw in ['state', 'status', 'error', 'cmd', 'result', 'type']):
                key_enums.append(enum.name)

        return key_enums[:5]

    def _extract_dependencies(self, ir) -> List[str]:
        """提取外部依赖"""
        deps = set()

        # 从函数参数类型推断
        for func in ir.functions:
            for param in func.params:
                ptype = param.type.lower()
                # 标准库和常见硬件抽象层
                if any(hw in ptype for hw in ['gpio', 'uart', 'spi', 'i2c', 'timer', 'dma']):
                    deps.add(ptype.split('_')[0].upper())

        return sorted(list(deps))
