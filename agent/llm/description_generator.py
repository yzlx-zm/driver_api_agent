"""描述生成器

使用 LLM 为函数、结构体等生成描述
"""

from typing import Dict, Any, Optional, List, TYPE_CHECKING
from .base import BaseLLMClient
from .claude_client import ClaudeClient
from ..models.ir import Function, Struct, Enum, Macro, Parameter, StructField, EnumValue

if TYPE_CHECKING:
    from .response_cache import ResponseCache
    from .usage_tracker import UsageTracker


class DescriptionGenerator:
    """描述生成器

    使用 LLM 为代码元素生成描述
    """

    # 系统提示模板
    SYSTEM_PROMPT = """你是一个嵌入式驱动文档专家。你的任务是为 C 语言驱动代码生成简洁、准确的描述。

规则：
1. 描述应该简洁明了，不超过 2 句话
2. 使用中文
3. 不要添加多余的解释或格式
4. 对于函数，说明其功能和主要用途
5. 对于结构体，说明其存储的数据
6. 对于枚举，说明其表示的状态或类型
7. 对于宏，说明其用途和值含义"""

    # 函数描述提示模板
    FUNC_PROMPT_TEMPLATE = """请为以下 C 语言函数生成简洁的描述（一句话）：

函数签名: {signature}
{extra_context}

只输出描述文本，不要其他内容。"""

    # 结构体描述提示模板
    STRUCT_PROMPT_TEMPLATE = """请为以下 C 语言结构体生成简洁的描述（一句话）：

结构体名称: {name}
字段列表:
{fields}

只输出描述文本，不要其他内容。"""

    # 枚举描述提示模板
    ENUM_PROMPT_TEMPLATE = """请为以下 C 语言枚举生成简洁的描述（一句话）：

枚举名称: {name}
枚举值: {values}

只输出描述文本，不要其他内容。"""

    # 宏描述提示模板
    MACRO_PROMPT_TEMPLATE = """请为以下 C 语言宏生成简洁的描述（一句话）：

宏名称: {name}
宏值: {value}

只输出描述文本，不要其他内容。"""

    # 参数描述提示模板
    PARAM_DESC_TEMPLATE = """请为以下 C 语言函数参数生成简洁描述（一句话，不超过20字）：

函数: {func_name}
函数描述: {func_desc}
参数名: {param_name}
参数类型: {param_type}
参数方向: {direction}

只输出描述文本，不要其他内容。"""

    # 返回值描述提示模板
    RETURN_DESC_TEMPLATE = """请为以下 C 语言函数的返回值生成描述（一句话）：

函数: {func_name}
函数描述: {func_desc}
返回值类型: {return_type}

只输出描述文本，不要其他内容。"""

    # 结构体字段描述提示模板
    FIELD_DESC_TEMPLATE = """请为以下 C 语言结构体字段生成简洁描述（一句话，不超过20字）：

结构体: {struct_name}
结构体描述: {struct_desc}
字段名: {field_name}
字段类型: {field_type}

只输出描述文本，不要其他内容。"""

    # 枚举值描述提示模板
    ENUM_VALUE_DESC_TEMPLATE = """请为以下 C 语言枚举值生成简洁描述（一句话，不超过15字）：

枚举: {enum_name}
枚举描述: {enum_desc}
枚举值名: {value_name}
数值: {value}

只输出描述文本，不要其他内容。"""

    def __init__(self, client: BaseLLMClient, config: Dict[str, Any] = None,
                 cache: 'ResponseCache' = None, tracker: 'UsageTracker' = None):
        """
        初始化描述生成器

        Args:
            client: LLM 客户端
            config: 配置
                - max_description_length: 最大描述长度
                - batch_size: 批量处理大小
            cache: 响应缓存（可选）
            tracker: 使用追踪器（可选）
        """
        self.client = client
        self.config = config or {}
        self.max_length = self.config.get('max_description_length', 100)
        self.batch_size = self.config.get('batch_size', 10)
        self.cache = cache
        self.tracker = tracker

    def generate_function_description(self, func: Function,
                                       context: str = "") -> str:
        """
        为函数生成描述

        Args:
            func: 函数对象
            context: 额外上下文（如相关注释）

        Returns:
            生成的描述
        """
        extra = ""
        if context:
            extra = f"\n相关注释: {context}"
        elif func.brief:
            extra = f"\n现有注释: {func.brief}"

        prompt = self.FUNC_PROMPT_TEMPLATE.format(
            signature=func.to_signature(),
            extra_context=extra
        )

        try:
            description = self._generate(prompt)
            return self._truncate(description, self.max_length)
        except Exception:
            # 失败时返回占位符
            return f"执行 {func.name} 功能"

    def generate_struct_description(self, struct: Struct) -> str:
        """
        为结构体生成描述

        Args:
            struct: 结构体对象

        Returns:
            生成的描述
        """
        fields_str = "\n".join(
            f"  - {f.name}: {f.type}"
            for f in struct.fields[:10]  # 最多显示10个字段
        )
        if len(struct.fields) > 10:
            fields_str += f"\n  - ... (共 {len(struct.fields)} 个字段)"

        prompt = self.STRUCT_PROMPT_TEMPLATE.format(
            name=struct.name or struct.typedef_name,
            fields=fields_str
        )

        try:
            description = self._generate(prompt)
            return self._truncate(description, self.max_length)
        except Exception:
            return f"{struct.name or struct.typedef_name} 结构体"

    def generate_enum_description(self, enum: Enum) -> str:
        """
        为枚举生成描述

        Args:
            enum: 枚举对象

        Returns:
            生成的描述
        """
        values_str = ", ".join(v.name for v in enum.values[:10])
        if len(enum.values) > 10:
            values_str += f" ... (共 {len(enum.values)} 个)"

        prompt = self.ENUM_PROMPT_TEMPLATE.format(
            name=enum.name or enum.typedef_name,
            values=values_str
        )

        try:
            description = self._generate(prompt)
            return self._truncate(description, self.max_length)
        except Exception:
            return f"{enum.name or enum.typedef_name} 枚举类型"

    def generate_macro_description(self, macro: Macro) -> str:
        """
        为宏生成描述

        Args:
            macro: 宏对象

        Returns:
            生成的描述
        """
        prompt = self.MACRO_PROMPT_TEMPLATE.format(
            name=macro.name,
            value=macro.value or "(空)"
        )

        try:
            description = self._generate(prompt)
            return self._truncate(description, self.max_length)
        except Exception:
            return f"{macro.name} 宏定义"

    def generate_param_description(self, func: Function, param: Parameter) -> str:
        """
        为函数参数生成描述

        Args:
            func: 函数对象
            param: 参数对象

        Returns:
            生成的描述
        """
        direction_map = {"IN": "输入", "OUT": "输出", "INOUT": "输入输出", "UNKNOWN": "未知"}
        prompt = self.PARAM_DESC_TEMPLATE.format(
            func_name=func.name,
            func_desc=func.description or func.brief or "未知功能",
            param_name=param.name,
            param_type=param.type,
            direction=direction_map.get(str(param.direction), "未知"),
        )

        try:
            description = self._generate(prompt)
            return self._truncate(description, 50)
        except Exception:
            return f"{param.name} 参数"

    def generate_return_description(self, func: Function) -> str:
        """
        为函数返回值生成描述

        Args:
            func: 函数对象

        Returns:
            生成的描述
        """
        if func.return_type == "void":
            return "无"

        prompt = self.RETURN_DESC_TEMPLATE.format(
            func_name=func.name,
            func_desc=func.description or func.brief or "未知功能",
            return_type=func.return_type,
        )

        try:
            description = self._generate(prompt)
            return self._truncate(description, 50)
        except Exception:
            return f"{func.return_type} 类型返回值"

    def generate_struct_field_description(self, struct: Struct,
                                           field: StructField) -> str:
        """
        为结构体字段生成描述

        Args:
            struct: 结构体对象
            field: 字段对象

        Returns:
            生成的描述
        """
        prompt = self.FIELD_DESC_TEMPLATE.format(
            struct_name=struct.name or struct.typedef_name,
            struct_desc=struct.description or "未知结构体",
            field_name=field.name,
            field_type=field.type,
        )

        try:
            description = self._generate(prompt)
            return self._truncate(description, 50)
        except Exception:
            return f"{field.name} 字段"

    def generate_enum_value_description(self, enum: Enum,
                                         value: EnumValue) -> str:
        """
        为枚举值生成描述

        Args:
            enum: 枚举对象
            value: 枚举值对象

        Returns:
            生成的描述
        """
        prompt = self.ENUM_VALUE_DESC_TEMPLATE.format(
            enum_name=enum.name or enum.typedef_name,
            enum_desc=enum.description or "未知枚举",
            value_name=value.name,
            value=value.value,
        )

        try:
            description = self._generate(prompt)
            return self._truncate(description, 30)
        except Exception:
            return f"{value.name}"

    def batch_generate_function_descriptions(self,
                                              functions: List[Function]) -> Dict[str, str]:
        """
        批量生成函数描述

        Args:
            functions: 函数列表

        Returns:
            函数名 -> 描述 的映射
        """
        results = {}

        for i in range(0, len(functions), self.batch_size):
            batch = functions[i:i + self.batch_size]
            for func in batch:
                if not func.description or self._is_placeholder(func.description):
                    results[func.name] = self.generate_function_description(func)

        return results

    def _generate(self, prompt: str, prompt_type: str = "") -> str:
        """调用 LLM 生成，带缓存、重试和追踪"""
        # 检查缓存
        if self.cache:
            cached = self.cache.get(prompt, self.SYSTEM_PROMPT)
            if cached is not None:
                return cached

        # 调用 LLM（带重试）
        try:
            response = self.client.generate_with_system(
                self.SYSTEM_PROMPT, prompt
            )
        except Exception:
            # 重试
            response = self.client.generate_with_retry(
                prompt, max_retries=2, system_prompt=self.SYSTEM_PROMPT
            )
            if response is None:
                raise

        # 记录使用量
        if self.tracker and hasattr(self.client, 'last_usage'):
            self.tracker.record(
                provider=self.client.name,
                model=self.client.model,
                input_tokens=self.client.last_usage.input_tokens,
                output_tokens=self.client.last_usage.output_tokens,
                prompt_type=prompt_type,
            )

        # 写入缓存
        if self.cache:
            self.cache.put(prompt, response, self.SYSTEM_PROMPT)

        return response

    def _truncate(self, text: str, max_length: int) -> str:
        """截断文本"""
        text = text.strip()
        if len(text) <= max_length:
            return text
        # 在句号处截断
        sentences = text.replace('。', '。\n').split('\n')
        result = ""
        for s in sentences:
            if len(result + s) <= max_length:
                result += s
            else:
                break
        return result.strip() or text[:max_length]

    def _is_placeholder(self, description: str) -> bool:
        """检查是否是占位符"""
        placeholders = ["待补充", "待填写", "TODO", "FIXME", "TBD", "XXX"]
        return any(p in description for p in placeholders)


def create_llm_client(config: Dict[str, Any]) -> Optional[BaseLLMClient]:
    """
    根据配置创建 LLM 客户端

    Args:
        config: 配置字典
            - llm_enabled: 是否启用
            - llm_provider: 提供商 (claude/openai/deepseek)
            - llm_api_key: API 密钥
            - llm_model: 模型名称
            - llm_base_url: 自定义 API 地址（可选）

    Returns:
        LLM 客户端，如果未启用则返回 None
    """
    if not config.get('llm_enabled', False):
        return None

    provider = config.get('llm_provider', 'claude')

    client_config = {
        'api_key': config.get('llm_api_key'),
        'model': config.get('llm_model'),
        'max_tokens': config.get('llm_max_tokens', 500),
        'temperature': config.get('llm_temperature', 0.7),
        'base_url': config.get('llm_base_url'),  # 支持自定义 API 地址
    }

    if provider == 'claude':
        return ClaudeClient(client_config)
    elif provider in ('openai', 'deepseek'):
        # DeepSeek 使用 OpenAI 兼容 API
        from .openai_client import OpenAIClient
        return OpenAIClient(client_config)
    else:
        return None
