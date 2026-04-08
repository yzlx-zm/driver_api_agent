"""增量更新模块

提供文档增量更新功能
"""

from .diff_detector import DiffDetector, DiffResult
from .region_parser import RegionParser, DocumentRegion, ParsedDocument, wrap_in_auto_region, wrap_in_manual_region
from .merger import DocumentMerger

__all__ = [
    'DiffDetector',
    'DiffResult',
    'RegionParser',
    'DocumentRegion',
    'ParsedDocument',
    'DocumentMerger',
    'wrap_in_auto_region',
    'wrap_in_manual_region',
]
