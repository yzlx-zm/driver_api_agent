"""OpenAI API 客户端

使用 OpenAI SDK 调用 GPT 系列模型
"""

from typing import Dict, Any, Optional, List
from .base import BaseLLMClient, APIKeyError, LLMError, TokenUsage


class OpenAIClient(BaseLLMClient):
    """OpenAI API 客户端"""

    @property
    def name(self) -> str:
        return "OpenAI"

    @property
    def _default_model(self) -> str:
        return "gpt-4o-mini"

    @property
    def _api_key_env_names(self) -> List[str]:
        return ['OPENAI_API_KEY', 'LLM_API_KEY']

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self._client = None
        # 支持自定义 base_url（用于 DeepSeek 等兼容 API）
        self.base_url = self.config.get('base_url')

    def _get_client(self):
        """获取或创建 OpenAI 客户端"""
        if self._client is None:
            try:
                from openai import OpenAI
                client_kwargs = {'api_key': self.api_key}
                if self.base_url:
                    client_kwargs['base_url'] = self.base_url
                self._client = OpenAI(**client_kwargs)
            except ImportError:
                raise LLMError("请安装 openai 库: pip install openai")
        return self._client

    def is_available(self) -> bool:
        """检查是否可用"""
        if not self.api_key:
            return False
        try:
            from openai import OpenAI  # noqa: F401
            return True
        except ImportError:
            return False

    def generate(self, prompt: str, max_tokens: int = None) -> str:
        """
        生成文本

        Args:
            prompt: 输入提示
            max_tokens: 最大 token 数

        Returns:
            生成的文本
        """
        if not self.api_key:
            raise APIKeyError("未配置 OpenAI API Key")

        client = self._get_client()
        tokens = max_tokens or self.max_tokens

        try:
            response = client.chat.completions.create(
                model=self.model,
                max_tokens=tokens,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}]
            )
            self._update_usage(response)
            return response.choices[0].message.content

        except Exception as e:
            error_str = str(e).lower()
            if 'api_key' in error_str or 'authentication' in error_str:
                raise APIKeyError(f"API Key 无效: {e}")
            elif 'rate' in error_str or 'limit' in error_str:
                raise LLMError(f"速率限制: {e}")
            else:
                raise LLMError(f"OpenAI API 调用失败: {e}")

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
        if not self.api_key:
            raise APIKeyError("未配置 OpenAI API Key")

        client = self._get_client()
        tokens = max_tokens or self.max_tokens

        try:
            response = client.chat.completions.create(
                model=self.model,
                max_tokens=tokens,
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            self._update_usage(response)
            return response.choices[0].message.content

        except Exception as e:
            raise LLMError(f"OpenAI API 调用失败: {e}")

    def _update_usage(self, response) -> None:
        """从 API 响应更新 token 使用量"""
        try:
            if hasattr(response, 'usage') and response.usage:
                self.last_usage = TokenUsage(
                    input_tokens=getattr(response.usage, 'prompt_tokens', 0),
                    output_tokens=getattr(response.usage, 'completion_tokens', 0),
                )
        except Exception:
            pass
