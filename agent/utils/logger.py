"""日志管理模块"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


# 颜色代码
class Colors:
    """终端颜色"""
    RESET = '\033[0m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'


class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器"""

    LEVEL_COLORS = {
        logging.DEBUG: Colors.CYAN,
        logging.INFO: Colors.GREEN,
        logging.WARNING: Colors.YELLOW,
        logging.ERROR: Colors.RED,
        logging.CRITICAL: Colors.RED + Colors.BOLD,
    }

    def format(self, record):
        # 添加颜色
        if sys.stdout.isatty():
            color = self.LEVEL_COLORS.get(record.levelno, Colors.WHITE)
            record.levelname = f"{color}{record.levelname}{Colors.RESET}"

        return super().format(record)


def setup_logger(
    name: str = "driver_api_agent",
    level: str = "INFO",
    log_file: Optional[str] = None,
    log_to_file: bool = False
) -> logging.Logger:
    """
    设置并返回logger实例

    Args:
        name: logger名称
        level: 日志级别 (DEBUG/INFO/WARNING/ERROR)
        log_file: 日志文件路径
        log_to_file: 是否输出到文件

    Returns:
        配置好的logger实例
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 避免重复添加handler
    if logger.handlers:
        return logger

    # 控制台handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)

    # 格式化器
    console_format = ColoredFormatter(
        fmt="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S"
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # 文件handler（可选）
    if log_to_file and log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            fmt="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str = "driver_api_agent") -> logging.Logger:
    """
    获取logger实例

    Args:
        name: logger名称

    Returns:
        logger实例
    """
    return logging.getLogger(name)


# 模块级logger
_logger: Optional[logging.Logger] = None


def init_logger(config=None):
    """初始化全局logger"""
    global _logger

    level = "INFO"
    log_file = "logs/agent.log"
    log_to_file = False

    if config:
        level = getattr(config, 'log_level', level)
        log_file = getattr(config, 'log_file_path', log_file)
        log_to_file = getattr(config, 'log_file_enabled', log_to_file)

    _logger = setup_logger(
        name="driver_api_agent",
        level=level,
        log_file=log_file,
        log_to_file=log_to_file
    )

    return _logger


def log_debug(msg: str):
    """记录DEBUG日志"""
    if _logger:
        _logger.debug(msg)


def log_info(msg: str):
    """记录INFO日志"""
    if _logger:
        _logger.info(msg)


def log_warning(msg: str):
    """记录WARNING日志"""
    if _logger:
        _logger.warning(msg)


def log_error(msg: str):
    """记录ERROR日志"""
    if _logger:
        _logger.error(msg)


def log_critical(msg: str):
    """记录CRITICAL日志"""
    if _logger:
        _logger.critical(msg)
