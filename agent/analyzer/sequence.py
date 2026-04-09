"""时序图分析器

分析函数调用序列和流程
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum


class SequenceStepType(Enum):
    """时序步骤类型"""
    SYNC_CALL = "同步调用"
    ASYNC_CALL = "异步调用"
    CALLBACK = "回调"
    RESPONSE = "响应"
    LOOP = "循环"
    CONDITION = "条件分支"


@dataclass
class SequenceStep:
    """时序步骤"""
    source: str
    target: str
    action: str
    step_type: SequenceStepType = SequenceStepType.SYNC_CALL
    description: str = ""
    return_value: str = ""


@dataclass
class SequenceScenario:
    """时序场景"""
    name: str
    description: str
    steps: List[SequenceStep] = field(default_factory=list)
    participants: List[str] = field(default_factory=list)


@dataclass
class SequenceInfo:
    """时序信息"""
    scenarios: List[SequenceScenario] = field(default_factory=list)
    main_flows: List[str] = field(default_factory=list)


class SequenceAnalyzer:
    """时序图分析器"""

    # 初始化场景关键词
    INIT_SCENARIO_KEYWORDS = ['init', 'start', 'begin', 'open', 'setup', 'config']

    # 业务场景关键词
    BUSINESS_SCENARIO_KEYWORDS = [
        ('enroll', '注册/录入流程'),
        ('verify', '验证/校验流程'),
        ('delete', '删除流程'),
        ('query', '查询流程'),
        ('send', '发送流程'),
        ('receive', '接收流程'),
        ('process', '处理流程'),
    ]

    def __init__(self, config: dict = None):
        self.config = config or {}

    def analyze(self, ir) -> SequenceInfo:
        """分析 IR，提取时序信息"""
        info = SequenceInfo()

        # 1. 分析初始化场景
        init_scenario = self._analyze_init_scenario(ir)
        if init_scenario:
            info.scenarios.append(init_scenario)

        # 2. 分析业务场景
        business_scenarios = self._analyze_business_scenarios(ir)
        info.scenarios.extend(business_scenarios)

        # 3. 提取主要流程
        info.main_flows = self._extract_main_flows(ir)

        return info

    def _analyze_init_scenario(self, ir) -> Optional[SequenceScenario]:
        """分析初始化场景"""
        init_funcs = []
        config_funcs = []
        start_funcs = []

        for func in ir.functions:
            name = func.name.lower()
            if 'init' in name:
                init_funcs.append(func)
            elif 'config' in name:
                config_funcs.append(func)
            elif 'start' in name or 'begin' in name:
                start_funcs.append(func)

        if not init_funcs:
            return None

        scenario = SequenceScenario(
            name="初始化流程",
            description="模块初始化的标准流程",
            participants=["应用层", "驱动模块", "硬件层"]
        )

        # 生成步骤
        steps = []

        # 1. 应用层调用初始化
        if init_funcs:
            func = init_funcs[0]
            steps.append(SequenceStep(
                source="应用层",
                target="驱动模块",
                action=f"{func.name}()",
                step_type=SequenceStepType.SYNC_CALL,
                description="调用初始化函数"
            ))

            # 2. 驱动模块配置硬件
            if config_funcs:
                steps.append(SequenceStep(
                    source="驱动模块",
                    target="硬件层",
                    action=f"{config_funcs[0].name}()",
                    step_type=SequenceStepType.SYNC_CALL,
                    description="配置硬件参数"
                ))

            # 3. 硬件响应
            steps.append(SequenceStep(
                source="硬件层",
                target="驱动模块",
                action="配置完成",
                step_type=SequenceStepType.RESPONSE,
                description="硬件配置完成"
            ))

            # 4. 返回初始化结果
            ret_type = init_funcs[0].return_type
            steps.append(SequenceStep(
                source="驱动模块",
                target="应用层",
                action=f"返回 {ret_type}",
                step_type=SequenceStepType.RESPONSE,
                description="初始化结果"
            ))

        # 5. 启动流程
        if start_funcs:
            steps.append(SequenceStep(
                source="应用层",
                target="驱动模块",
                action=f"{start_funcs[0].name}()",
                step_type=SequenceStepType.SYNC_CALL,
                description="启动模块"
            ))

        scenario.steps = steps
        return scenario

    def _analyze_business_scenarios(self, ir) -> List[SequenceScenario]:
        """分析业务场景"""
        scenarios = []

        for keyword, desc in self.BUSINESS_SCENARIO_KEYWORDS:
            funcs = [f for f in ir.functions if keyword in f.name.lower()]
            if funcs:
                scenario = self._create_business_scenario(ir, keyword, desc, funcs)
                if scenario:
                    scenarios.append(scenario)

        return scenarios[:5]  # 最多5个业务场景

    def _create_business_scenario(self, ir, keyword: str, desc: str,
                                   funcs: list) -> Optional[SequenceScenario]:
        """创建业务场景"""
        # 查找相关函数
        main_func = funcs[0]

        # 查找回调函数
        callback_funcs = [f for f in ir.functions
                          if 'callback' in f.name.lower() or 'handler' in f.name.lower()]

        # 查找结果获取函数
        result_funcs = [f for f in ir.functions
                        if 'result' in f.name.lower() or 'get' in f.name.lower()]

        scenario = SequenceScenario(
            name=desc,
            description=f"{main_func.description or main_func.brief or desc}",
            participants=["应用层", "驱动模块", "硬件层"]
        )

        steps = []

        # 1. 应用层发起请求
        steps.append(SequenceStep(
            source="应用层",
            target="驱动模块",
            action=f"{main_func.name}()",
            step_type=SequenceStepType.SYNC_CALL,
            description=main_func.description or "发起业务请求"
        ))

        # 2. 驱动模块处理
        is_async = any(kw in main_func.name.lower() for kw in ['async', 'nonblock'])
        if is_async:
            steps.append(SequenceStep(
                source="驱动模块",
                target="应用层",
                action="立即返回",
                step_type=SequenceStepType.RESPONSE,
                description="非阻塞调用立即返回"
            ))

        # 3. 硬件交互
        steps.append(SequenceStep(
            source="驱动模块",
            target="硬件层",
            action="发送命令/数据",
            step_type=SequenceStepType.SYNC_CALL,
            description="与硬件设备通信"
        ))

        # 4. 硬件响应
        steps.append(SequenceStep(
            source="硬件层",
            target="驱动模块",
            action="响应数据",
            step_type=SequenceStepType.RESPONSE,
            description="硬件返回处理结果"
        ))

        # 5. 回调或返回
        if callback_funcs and is_async:
            steps.append(SequenceStep(
                source="驱动模块",
                target="应用层",
                action=f"{callback_funcs[0].name}()",
                step_type=SequenceStepType.CALLBACK,
                description="回调通知结果"
            ))
        elif result_funcs:
            steps.append(SequenceStep(
                source="应用层",
                target="驱动模块",
                action=f"{result_funcs[0].name}()",
                step_type=SequenceStepType.SYNC_CALL,
                description="获取处理结果"
            ))

        scenario.steps = steps
        return scenario

    def _extract_main_flows(self, ir) -> List[str]:
        """提取主要流程描述"""
        flows = []

        # 基于函数分类归纳流程
        categories = {
            'init': [],
            'business': [],
            'query': [],
            'control': []
        }

        for func in ir.functions:
            name = func.name.lower()
            if any(kw in name for kw in ['init', 'start', 'deinit', 'stop']):
                categories['init'].append(func.name)
            elif any(kw in name for kw in ['send', 'recv', 'process', 'enroll', 'verify']):
                categories['business'].append(func.name)
            elif any(kw in name for kw in ['get', 'is', 'has', 'check']):
                categories['query'].append(func.name)
            elif any(kw in name for kw in ['set', 'config', 'enable']):
                categories['control'].append(func.name)

        if categories['init']:
            flows.append(f"初始化: {' -> '.join(categories['init'][:3])}")
        if categories['business']:
            flows.append(f"业务处理: {', '.join(categories['business'][:3])}")
        if categories['query']:
            flows.append(f"状态查询: {', '.join(categories['query'][:3])}")

        return flows

    def to_mermaid(self, scenario: SequenceScenario) -> str:
        """转换为 Mermaid 时序图"""
        lines = ["sequenceDiagram"]

        # 添加参与者
        for participant in scenario.participants:
            safe_name = participant.replace(" ", "_")
            lines.append(f"    participant {safe_name} as {participant}")

        # 添加步骤
        for step in scenario.steps:
            source = step.source.replace(" ", "_")
            target = step.target.replace(" ", "_")

            if step.step_type == SequenceStepType.SYNC_CALL:
                lines.append(f"    {source}->>{target}: {step.action}")
            elif step.step_type == SequenceStepType.ASYNC_CALL:
                lines.append(f"    {source}-){target}: {step.action}")
            elif step.step_type == SequenceStepType.CALLBACK:
                lines.append(f"    {source}->>{target}: {step.action}")
            elif step.step_type == SequenceStepType.RESPONSE:
                lines.append(f"    {source}-->>{target}: {step.action}")
            else:
                lines.append(f"    {source}->>{target}: {step.action}")

        return "\n".join(lines)
