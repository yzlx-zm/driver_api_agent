"""Token 使用追踪

记录 LLM 调用的 token 消耗和费用估算
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime


@dataclass
class UsageRecord:
    """单次 API 调用记录"""
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    timestamp: str = ""
    prompt_type: str = ""  # "function_desc", "param_desc", "struct_desc" 等

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


# 费用表：每百万 token 的费用 (input, output)
COST_PER_MILLION = {
    ("Claude", "claude-opus-4-6"): (15.0, 75.0),
    ("Claude", "claude-sonnet-4-6"): (3.0, 15.0),
    ("Claude", "claude-haiku-4-5-20251001"): (0.80, 4.0),
    ("OpenAI", "gpt-4o"): (2.50, 10.0),
    ("OpenAI", "gpt-4o-mini"): (0.15, 0.60),
}


class UsageTracker:
    """Token 使用追踪器"""

    def __init__(self):
        self.records: List[UsageRecord] = []

    def record(self, provider: str, model: str,
               input_tokens: int, output_tokens: int,
               prompt_type: str = "") -> None:
        """
        记录一次 API 调用

        Args:
            provider: 提供商名称
            model: 模型名称
            input_tokens: 输入 token 数
            output_tokens: 输出 token 数
            prompt_type: 提示类型
        """
        self.records.append(UsageRecord(
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            timestamp=datetime.now().isoformat(),
            prompt_type=prompt_type,
        ))

    def record_from_usage(self, provider: str, model: str,
                          usage, prompt_type: str = "") -> None:
        """
        从 TokenUsage 对象记录

        Args:
            provider: 提供商名称
            model: 模型名称
            usage: TokenUsage 对象 (有 input_tokens, output_tokens 属性)
            prompt_type: 提示类型
        """
        self.record(
            provider=provider,
            model=model,
            input_tokens=getattr(usage, 'input_tokens', 0),
            output_tokens=getattr(usage, 'output_tokens', 0),
            prompt_type=prompt_type,
        )

    def get_summary(self) -> Dict:
        """
        获取使用摘要

        Returns:
            包含总量和费用的字典
        """
        total_input = sum(r.input_tokens for r in self.records)
        total_output = sum(r.output_tokens for r in self.records)
        total_cost = sum(self._calc_cost(r) for r in self.records)

        by_type = {}
        for r in self.records:
            t = r.prompt_type or "other"
            if t not in by_type:
                by_type[t] = {"calls": 0, "input_tokens": 0, "output_tokens": 0}
            by_type[t]["calls"] += 1
            by_type[t]["input_tokens"] += r.input_tokens
            by_type[t]["output_tokens"] += r.output_tokens

        return {
            "total_calls": len(self.records),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_tokens": total_input + total_output,
            "estimated_cost_usd": round(total_cost, 6),
            "by_type": by_type,
        }

    def print_report(self) -> str:
        """
        生成可读的使用报告

        Returns:
            格式化的报告文本
        """
        if not self.records:
            return "无 LLM 调用记录"

        summary = self.get_summary()
        lines = [
            "=== LLM 使用报告 ===",
            f"总调用次数: {summary['total_calls']}",
            f"总 Token: {summary['total_tokens']} "
            f"(输入: {summary['total_input_tokens']}, "
            f"输出: {summary['total_output_tokens']})",
            f"预估费用: ${summary['estimated_cost_usd']:.4f}",
        ]

        if summary['by_type']:
            lines.append("--- 按类型统计 ---")
            for ptype, data in sorted(summary['by_type'].items()):
                lines.append(
                    f"  {ptype}: {data['calls']} 次调用, "
                    f"{data['input_tokens'] + data['output_tokens']} tokens"
                )

        return "\n".join(lines)

    def _calc_cost(self, record: UsageRecord) -> float:
        """计算单次调用费用"""
        key = (record.provider, record.model)
        if key in COST_PER_MILLION:
            input_cost, output_cost = COST_PER_MILLION[key]
            return (record.input_tokens * input_cost / 1_000_000 +
                    record.output_tokens * output_cost / 1_000_000)
        return 0.0
