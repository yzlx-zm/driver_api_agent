"""LLM 响应缓存

使用 JSON 文件缓存 LLM 响应，避免重复调用
"""

import json
import hashlib
import os
import tempfile
from typing import Dict, Any, Optional
from datetime import datetime


class ResponseCache:
    """LLM 响应文件缓存

    使用 SHA-256(prompt) 作为 key，缓存 LLM 生成的描述
    """

    def __init__(self, cache_dir: str = ".cache/llm"):
        """
        初始化缓存

        Args:
            cache_dir: 缓存目录
        """
        self.cache_dir = cache_dir
        self._cache_file = os.path.join(cache_dir, "responses.json")
        self._data: Dict[str, Dict[str, Any]] = {}
        self._hits = 0
        self._misses = 0
        self._load()

    def _cache_key(self, prompt: str, system_prompt: str = None) -> str:
        """生成缓存 key"""
        content = f"{system_prompt or ''}|||{prompt}"
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def get(self, prompt: str, system_prompt: str = None) -> Optional[str]:
        """
        从缓存获取响应

        Args:
            prompt: 用户提示
            system_prompt: 系统提示

        Returns:
            缓存的响应文本，未命中返回 None
        """
        key = self._cache_key(prompt, system_prompt)
        entry = self._data.get(key)

        if entry is not None:
            self._hits += 1
            return entry.get('text')

        self._misses += 1
        return None

    def put(self, prompt: str, response: str, system_prompt: str = None,
            metadata: Dict[str, Any] = None) -> None:
        """
        写入缓存

        Args:
            prompt: 用户提示
            response: LLM 响应
            system_prompt: 系统提示
            metadata: 额外元数据 (provider, model 等)
        """
        key = self._cache_key(prompt, system_prompt)
        entry = {
            'text': response,
            'timestamp': datetime.now().isoformat(),
        }
        if metadata:
            entry.update(metadata)

        self._data[key] = entry
        self._save()

    def clear(self) -> None:
        """清空缓存"""
        self._data = {}
        self._hits = 0
        self._misses = 0
        self._save()

    def stats(self) -> Dict[str, int]:
        """
        获取缓存统计

        Returns:
            包含 entries, hits, misses 的字典
        """
        return {
            'entries': len(self._data),
            'hits': self._hits,
            'misses': self._misses,
        }

    def _load(self) -> None:
        """从文件加载缓存"""
        if os.path.exists(self._cache_file):
            try:
                with open(self._cache_file, 'r', encoding='utf-8') as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._data = {}

    def _save(self) -> None:
        """保存缓存到文件（原子写入）"""
        os.makedirs(self.cache_dir, exist_ok=True)
        try:
            # 原子写入：先写临时文件，再重命名
            fd, tmp_path = tempfile.mkstemp(
                dir=self.cache_dir, suffix='.tmp'
            )
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    json.dump(self._data, f, ensure_ascii=False, indent=2)
                # Windows 上需要先删除目标文件
                if os.path.exists(self._cache_file):
                    os.remove(self._cache_file)
                os.rename(tmp_path, self._cache_file)
            except Exception:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                raise
        except IOError:
            pass
