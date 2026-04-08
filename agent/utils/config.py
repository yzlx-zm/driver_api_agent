"""配置管理模块"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class Config:
    """配置类"""
    # 输入配置
    input_encoding: str = "utf-8"
    input_extensions: list = field(default_factory=lambda: [".h", ".c"])
    input_exclude_patterns: list = field(default_factory=lambda: ["*_test.c", "*_test.h"])

    # 输出配置
    output_format: str = "markdown"
    output_encoding: str = "utf-8"
    output_filename_template: str = "{module}_API_Document.md"

    # 解析配置
    parser_include_static: bool = True
    parser_extract_comments: bool = True
    parser_comment_style: str = "all"
    parser_category_keywords: Dict[str, list] = field(default_factory=lambda: {
        "init": ["init", "deinit", "start", "stop", "reset"],
        "query": ["get", "is", "has", "check"],
        "callback": ["callback", "handler", "on_"]
    })

    # 校验配置
    validator_enabled: bool = True
    validator_level: str = "normal"
    validator_check_signature: bool = True
    validator_check_struct_comments: bool = True
    validator_check_coverage: bool = True
    validator_check_naming: bool = True

    # LLM配置
    llm_enabled: bool = False
    llm_provider: str = "claude"
    llm_api_key: str = ""
    llm_model: str = "claude-sonnet-4-6"
    llm_base_url: str = ""  # 自定义 API 地址（DeepSeek 等兼容 API）
    llm_max_desc_length: int = 200
    llm_max_tokens: int = 500
    llm_temperature: float = 0.7
    llm_auto_generate_desc: bool = True
    llm_cache_enabled: bool = True
    llm_cache_dir: str = ".cache/llm"
    llm_track_usage: bool = True
    llm_fallback_provider: str = ""

    # 模板配置
    template_language: str = "zh"
    template_include_toc: bool = True
    template_include_examples: bool = True
    template_include_limitations: bool = True
    template_include_porting: bool = True

    # 增量更新配置
    incremental_enabled: bool = True

    # 日志配置
    log_level: str = "INFO"
    log_file_enabled: bool = False
    log_file_path: str = "logs/agent.log"


class ConfigManager:
    """配置管理器"""

    DEFAULT_CONFIG_FILE = "config/default.yaml"

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Config:
        """加载配置"""
        config = Config()

        # 尝试加载配置文件
        yaml_path = self._find_config_file()
        if yaml_path and os.path.exists(yaml_path):
            with open(yaml_path, 'r', encoding='utf-8') as f:
                yaml_config = yaml.safe_load(f)
                if yaml_config:
                    config = self._apply_yaml_config(config, yaml_config)

        # 环境变量覆盖
        config = self._apply_env_overrides(config)

        return config

    def _find_config_file(self) -> Optional[str]:
        """查找配置文件"""
        if self.config_path:
            return self.config_path

        # 按优先级查找
        search_paths = [
            self.DEFAULT_CONFIG_FILE,
            "config/default.yaml",
            "default.yaml",
        ]

        for path in search_paths:
            if os.path.exists(path):
                return path

        return None

    def _apply_yaml_config(self, config: Config, yaml_config: Dict[str, Any]) -> Config:
        """应用YAML配置"""
        # 输入配置
        if 'input' in yaml_config:
            input_cfg = yaml_config['input']
            config.input_encoding = input_cfg.get('encoding', config.input_encoding)
            config.input_extensions = input_cfg.get('extensions', config.input_extensions)
            config.input_exclude_patterns = input_cfg.get('exclude_patterns', config.input_exclude_patterns)

        # 输出配置
        if 'output' in yaml_config:
            output_cfg = yaml_config['output']
            config.output_format = output_cfg.get('format', config.output_format)
            config.output_encoding = output_cfg.get('encoding', config.output_encoding)
            config.output_filename_template = output_cfg.get('filename_template', config.output_filename_template)

        # 解析配置
        if 'parser' in yaml_config:
            parser_cfg = yaml_config['parser']
            config.parser_include_static = parser_cfg.get('include_static', config.parser_include_static)
            config.parser_extract_comments = parser_cfg.get('extract_comments', config.parser_extract_comments)
            config.parser_comment_style = parser_cfg.get('comment_style', config.parser_comment_style)
            if 'category_keywords' in parser_cfg:
                config.parser_category_keywords = parser_cfg['category_keywords']

        # 校验配置
        if 'validator' in yaml_config:
            validator_cfg = yaml_config['validator']
            config.validator_enabled = validator_cfg.get('enabled', config.validator_enabled)
            config.validator_level = validator_cfg.get('level', config.validator_level)
            config.validator_check_signature = validator_cfg.get('check_signature', config.validator_check_signature)
            config.validator_check_struct_comments = validator_cfg.get('check_struct_comments', config.validator_check_struct_comments)
            config.validator_check_coverage = validator_cfg.get('check_coverage', config.validator_check_coverage)
            config.validator_check_naming = validator_cfg.get('check_naming', config.validator_check_naming)

        # LLM配置
        if 'llm' in yaml_config:
            llm_cfg = yaml_config['llm']
            config.llm_enabled = llm_cfg.get('enabled', config.llm_enabled)
            config.llm_provider = llm_cfg.get('provider', config.llm_provider)
            config.llm_api_key = llm_cfg.get('api_key', config.llm_api_key)
            config.llm_model = llm_cfg.get('model', config.llm_model)
            config.llm_base_url = llm_cfg.get('base_url', config.llm_base_url)
            config.llm_max_desc_length = llm_cfg.get('max_desc_length', config.llm_max_desc_length)
            config.llm_max_tokens = llm_cfg.get('max_tokens', config.llm_max_tokens)
            config.llm_temperature = llm_cfg.get('temperature', config.llm_temperature)
            config.llm_auto_generate_desc = llm_cfg.get('auto_generate_desc', config.llm_auto_generate_desc)
            config.llm_cache_enabled = llm_cfg.get('cache_enabled', config.llm_cache_enabled)
            config.llm_cache_dir = llm_cfg.get('cache_dir', config.llm_cache_dir)
            config.llm_track_usage = llm_cfg.get('track_usage', config.llm_track_usage)
            config.llm_fallback_provider = llm_cfg.get('fallback_provider', config.llm_fallback_provider)

        # 模板配置
        if 'template' in yaml_config:
            template_cfg = yaml_config['template']
            config.template_language = template_cfg.get('language', config.template_language)
            config.template_include_toc = template_cfg.get('include_toc', config.template_include_toc)
            config.template_include_examples = template_cfg.get('include_examples', config.template_include_examples)
            config.template_include_limitations = template_cfg.get('include_limitations', config.template_include_limitations)
            config.template_include_porting = template_cfg.get('include_porting', config.template_include_porting)

        # 增量更新配置
        if 'incremental' in yaml_config:
            incremental_cfg = yaml_config['incremental']
            config.incremental_enabled = incremental_cfg.get('enabled', config.incremental_enabled)

        # 日志配置
        if 'logging' in yaml_config:
            log_cfg = yaml_config['logging']
            config.log_level = log_cfg.get('level', config.log_level)
            config.log_file_enabled = log_cfg.get('file_enabled', config.log_file_enabled)
            config.log_file_path = log_cfg.get('file_path', config.log_file_path)

        return config

    def _apply_env_overrides(self, config: Config) -> Config:
        """应用环境变量覆盖"""
        # LLM API Key
        if os.environ.get('LLM_API_KEY'):
            config.llm_api_key = os.environ['LLM_API_KEY']

        # LLM Enabled
        if os.environ.get('LLM_ENABLED'):
            config.llm_enabled = os.environ['LLM_ENABLED'].lower() in ('true', '1', 'yes')

        # Log Level
        if os.environ.get('LOG_LEVEL'):
            config.log_level = os.environ['LOG_LEVEL']

        return config

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        return getattr(self.config, key, default)

    @property
    def all(self) -> Config:
        """获取完整配置"""
        return self.config


# 全局配置管理器实例
_config_manager: Optional[ConfigManager] = None


def get_config_manager(config_path: Optional[str] = None) -> ConfigManager:
    """获取配置管理器单例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(config_path)
    return _config_manager


def get_config() -> Config:
    """获取配置对象"""
    return get_config_manager().all
