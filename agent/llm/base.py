"""LLM 客户端基类

定义统一的 LLM 客户端接口
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List


@dataclass
class TokenUsage:
    """Token 使用量"""
    input_tokens: int = 0
    output_tokens: int = 0


class BaseLLMClient(ABC):
    """LLM 客户端基类

    所有 LLM 提供商的客户端都应该继承此类
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化 LLM 客户端

        Args:
            config: 客户端配置
                - api_key: API 密钥（可从环境变量读取）
                - model: 模型名称
                - max_tokens: 最大 token 数
                - temperature: 温度参数
        """
        self.config = config or {}
        self.api_key = self._get_api_key()
        self.model = self.config.get('model', self._default_model)
        self.max_tokens = self.config.get('max_tokens', 500)
        self.temperature = self.config.get('temperature', 0.7)
        self.last_usage: TokenUsage = TokenUsage()

    @property
    @abstractmethod
    def name(self) -> str:
        """客户端名称"""
        pass

    @property
    @abstractmethod
    def _default_model(self) -> str:
        """默认模型"""
        pass

    @abstractmethod
    def generate(self, prompt: str, max_tokens: int = None) -> str:
        """
        生成文本

        Args:
            prompt: 输入提示
            max_tokens: 最大 token 数（可选，覆盖默认值）

        Returns:
            生成的文本
        """
        pass

    @abstractmethod
    def generate_with_system(self, system_prompt: str, user_prompt: str,
                             max_tokens: int = None) -> str:
        """
        带系统提示的生成

        Args:
            system_prompt: 系统提示
            user_prompt: 用户提示
            max_tokens: 最大 token 数

        Returns:
            生成的文本
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        检查客户端是否可用

        Returns:
            是否配置正确且可用
        """
        pass

    def _get_api_key(self) -> Optional[str]:
        """
        获取 API 密钥

        优先从配置读取，其次从环境变量

        Returns:
            API 密钥
        """
        import os

        # 从配置读取
        if 'api_key' in self.config:
            return self.config['api_key']

        # 从环境变量读取（尝试多种可能的名称）
        env_keys = self._api_key_env_names
        for key in env_keys:
            value = os.environ.get(key)
            if value:
                return value

        return None

    @property
    def _api_key_env_names(self) -> List[str]:
        """API 密钥的环境变量名列表"""
        return ['LLM_API_KEY', 'API_KEY']

    def generate_with_retry(self, prompt: str, max_retries: int = 3,
                            system_prompt: str = None) -> Optional[str]:
        """
        带重试的生成

        Args:
            prompt: 输入提示
            max_retries: 最大重试次数
            system_prompt: 系统提示（可选）

        Returns:
            生成的文本，失败返回 None
        """
        import time

        for attempt in range(max_retries):
            try:
                if system_prompt:
                    return self.generate_with_system(system_prompt, prompt)
                return self.generate(prompt)
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(1 * (attempt + 1))  # 递增等待
                else:
                    raise e

        return None


class LLMError(Exception):
    """LLM 错误基类"""
    pass


class APIKeyError(LLMError):
    """API 密钥错误"""
    pass


class RateLimitError(LLMError):
    """速率限制错误"""
    pass


class ModelNotAvailableError(LLMError):
    """模型不可用错误"""
    pass
