"""文件工具函数"""

import os
import fnmatch
from pathlib import Path
from typing import List, Optional, Tuple


def read_file(file_path: str, encoding: str = 'utf-8') -> Tuple[str, bool]:
    """
    读取文件内容

    Args:
        file_path: 文件路径
        encoding: 文件编码

    Returns:
        (内容, 是否成功)
    """
    try:
        with open(file_path, 'r', encoding=encoding) as f:
            return f.read(), True
    except UnicodeDecodeError:
        # 尝试其他编码
        for enc in ['gbk', 'gb2312', 'latin-1']:
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    return f.read(), True
            except:
                continue
        return f"无法解码文件: {file_path}", False
    except Exception as e:
        return f"读取文件失败: {e}", False


def write_file(file_path: str, content: str, encoding: str = 'utf-8') -> bool:
    """
    写入文件内容

    Args:
        file_path: 文件路径
        content: 文件内容
        encoding: 文件编码

    Returns:
        是否成功
    """
    try:
        # 确保目录存在
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, 'w', encoding=encoding) as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"写入文件失败: {e}")
        return False


def get_file_list(
    directory: str,
    extensions: List[str] = None,
    exclude_patterns: List[str] = None,
    recursive: bool = True
) -> List[str]:
    """
    获取目录下的文件列表

    Args:
        directory: 目录路径
        extensions: 文件扩展名列表，如 ['.h', '.c']
        exclude_patterns: 排除的文件模式列表
        recursive: 是否递归搜索

    Returns:
        文件路径列表
    """
    if extensions is None:
        extensions = ['.h', '.c']
    if exclude_patterns is None:
        exclude_patterns = []

    files = []
    directory = Path(directory)

    if not directory.exists():
        return files

    if recursive:
        pattern = '**/*'
    else:
        pattern = '*'

    for ext in extensions:
        for file_path in directory.glob(f"{pattern}{ext}"):
            file_str = str(file_path)

            # 检查排除模式
            should_exclude = False
            for excl in exclude_patterns:
                if fnmatch.fnmatch(file_path.name, excl):
                    should_exclude = True
                    break

            if not should_exclude:
                files.append(file_str)

    return sorted(files)


def get_line_number(content: str, position: int) -> int:
    """
    根据位置获取行号

    Args:
        content: 文本内容
        position: 字符位置

    Returns:
        行号（1-based）
    """
    return content[:position].count('\n') + 1


def get_line_content(content: str, line_number: int) -> str:
    """
    获取指定行的内容

    Args:
        content: 文本内容
        line_number: 行号（1-based）

    Returns:
        行内容
    """
    lines = content.split('\n')
    if 1 <= line_number <= len(lines):
        return lines[line_number - 1]
    return ""


def detect_encoding(file_path: str) -> str:
    """
    检测文件编码

    Args:
        file_path: 文件路径

    Returns:
        编码名称
    """
    # 常见编码列表
    encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1', 'cp1252']

    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                f.read()
            return encoding
        except:
            continue

    return 'utf-8'  # 默认返回utf-8
