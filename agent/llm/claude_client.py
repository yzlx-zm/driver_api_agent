"""Claude API 客户端

使用 Anthropic SDK 调用 Claude API
"""

from typing import Dict, Any, Optional, List
from .base import BaseLLMClient, APIKeyError, LLMError, TokenUsage


class ClaudeClient(BaseLLMClient):
    """Claude API 客户端"""

    @property
    def name(self) -> str:
        return "Claude"

    @property
    def _default_model(self) -> str:
        return "claude-sonnet-4-6"

    @property
    def _api_key_env_names(self) -> List[str]:
        return ['ANTHROPIC_API_KEY', 'CLAUDE_API_KEY', 'LLM_API_KEY']

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self._client = None

    def _get_client(self):
        """获取或创建 Anthropic 客户端"""
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise LLMError("请安装 anthropic 库: pip install anthropic")
        return self._client

    def is_available(self) -> bool:
        """检查是否可用"""
        if not self.api_key:
            return False
        try:
            import anthropic
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

        Raises:
            APIKeyError: API 密钥无效
            LLMError: 其他错误
        """
        if not self.api_key:
            raise APIKeyError("未配置 Anthropic API Key")

        client = self._get_client()
        tokens = max_tokens or self.max_tokens

        try:
            message = client.messages.create(
                model=self.model,
                max_tokens=tokens,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}]
            )
            self._update_usage(message)
            return message.content[0].text

        except Exception as e:
            error_str = str(e).lower()

            if 'api_key' in error_str or 'authentication' in error_str:
                raise APIKeyError(f"API Key 无效: {e}")
            elif 'rate' in error_str or 'limit' in error_str:
                raise LLMError(f"速率限制: {e}")
            else:
                raise LLMError(f"Claude API 调用失败: {e}")

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
            raise APIKeyError("未配置 Anthropic API Key")

        client = self._get_client()
        tokens = max_tokens or self.max_tokens

        try:
            message = client.messages.create(
                model=self.model,
                max_tokens=tokens,
                temperature=self.temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )
            self._update_usage(message)
            return message.content[0].text

        except Exception as e:
            raise LLMError(f"Claude API 调用失败: {e}")

    def _update_usage(self, message) -> None:
        """从 API 响应更新 token 使用量"""
        try:
            if hasattr(message, 'usage') and message.usage:
                self.last_usage = TokenUsage(
                    input_tokens=getattr(message.usage, 'input_tokens', 0),
                    output_tokens=getattr(message.usage, 'output_tokens', 0),
                )
        except Exception:
            pass
