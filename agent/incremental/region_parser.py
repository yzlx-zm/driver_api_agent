"""区域解析器

解析文档中的标记区域
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class DocumentRegion:
    """文档区域"""
    name: str                          # 区域名称
    region_type: str                   # 'auto' 或 'manual'
    start_line: int                    # 起始行号
    end_line: int                      # 结束行号
    content: str                       # 区域内容
    start_marker: str = ""             # 起始标记原文
    end_marker: str = ""               # 结束标记原文


@dataclass
class ParsedDocument:
    """解析后的文档"""
    regions: Dict[str, DocumentRegion] = field(default_factory=dict)
    preamble: str = ""                 # 文档开头（第一个标记之前的内容）
    postamble: str = ""                # 文档结尾（最后一个标记之后的内容）
    unmarked_sections: List[Tuple[int, int, str]] = field(default_factory=list)  # (start, end, content)


class RegionParser:
    """区域解析器

    解析文档中的标记区域：
    <!-- AUTO-GENERATED-START:name --> ... <!-- AUTO-GENERATED-END:name -->
    <!-- MANUAL-EDIT-START:name --> ... <!-- MANUAL-EDIT-END:name -->
    """

    # 标记模式
    AUTO_START_PATTERN = re.compile(
        r'<!--\s*AUTO-GENERATED-START\s*:\s*(\w+)\s*-->',
        re.IGNORECASE
    )
    AUTO_END_PATTERN = re.compile(
        r'<!--\s*AUTO-GENERATED-END\s*:\s*(\w+)\s*-->',
        re.IGNORECASE
    )
    MANUAL_START_PATTERN = re.compile(
        r'<!--\s*MANUAL-EDIT-START\s*:\s*(\w+)\s*-->',
        re.IGNORECASE
    )
    MANUAL_END_PATTERN = re.compile(
        r'<!--\s*MANUAL-EDIT-END\s*:\s*(\w+)\s*-->',
        re.IGNORECASE
    )

    def parse(self, document: str) -> ParsedDocument:
        """
        解析文档中的所有区域

        Args:
            document: 文档内容

        Returns:
            解析后的文档结构
        """
        result = ParsedDocument()
        lines = document.split('\n')

        # 找出所有标记
        markers = self._find_all_markers(lines)

        if not markers:
            # 没有标记，整个文档是未标记的
            result.preamble = document
            return result

        # 解析区域
        result.regions = self._parse_regions(lines, markers)

        # 提取前言和后语
        if markers:
            first_marker_line = min(m[1] for m in markers)
            last_marker_line = max(m[1] for m in markers)

            result.preamble = '\n'.join(lines[:first_marker_line])
            result.postamble = '\n'.join(lines[last_marker_line + 1:])

        return result

    def _find_all_markers(self, lines: List[str]) -> List[Tuple[str, int, str, str]]:
        """
        找出所有标记

        Returns:
            List of (marker_type, line_number, region_name, full_match)
        """
        markers = []

        for i, line in enumerate(lines):
            # AUTO 开始
            match = self.AUTO_START_PATTERN.search(line)
            if match:
                markers.append(('auto_start', i, match.group(1), match.group(0)))

            # AUTO 结束
            match = self.AUTO_END_PATTERN.search(line)
            if match:
                markers.append(('auto_end', i, match.group(1), match.group(0)))

            # MANUAL 开始
            match = self.MANUAL_START_PATTERN.search(line)
            if match:
                markers.append(('manual_start', i, match.group(1), match.group(0)))

            # MANUAL 结束
            match = self.MANUAL_END_PATTERN.search(line)
            if match:
                markers.append(('manual_end', i, match.group(1), match.group(0)))

        return markers

    def _parse_regions(self, lines: List[str], markers: List[Tuple]) -> Dict[str, DocumentRegion]:
        """解析区域"""
        regions = {}
        lines_count = len(lines)

        # 按区域名分组
        region_markers: Dict[str, List[Tuple]] = {}
        for marker in markers:
            region_name = marker[2]
            if region_name not in region_markers:
                region_markers[region_name] = []
            region_markers[region_name].append(marker)

        # 解析每个区域
        for region_name, region_marker_list in region_markers.items():
            # 找到开始和结束标记
            start_info = None
            end_info = None
            region_type = 'auto'  # 默认

            for marker in region_marker_list:
                marker_type = marker[0]
                if marker_type in ('auto_start', 'manual_start'):
                    start_info = marker
                    region_type = 'manual' if marker_type == 'manual_start' else 'auto'
                elif marker_type in ('auto_end', 'manual_end'):
                    end_info = marker

            if start_info and end_info:
                start_line = start_info[1]
                end_line = end_info[1]

                # 提取内容（不包括标记行）
                content_lines = lines[start_line + 1:end_line]
                content = '\n'.join(content_lines)

                regions[region_name] = DocumentRegion(
                    name=region_name,
                    region_type=region_type,
                    start_line=start_line,
                    end_line=end_line,
                    content=content,
                    start_marker=start_info[3],
                    end_marker=end_info[3]
                )

        return regions

    def extract_manual_regions(self, document: str) -> Dict[str, str]:
        """
        提取所有手动编辑区域的内容

        Args:
            document: 文档内容

        Returns:
            区域名 -> 内容 的映射
        """
        parsed = self.parse(document)
        return {
            name: region.content
            for name, region in parsed.regions.items()
            if region.region_type == 'manual'
        }

    def has_markers(self, document: str) -> bool:
        """检查文档是否有区域标记"""
        return bool(
            self.AUTO_START_PATTERN.search(document) or
            self.MANUAL_START_PATTERN.search(document)
        )


def wrap_in_auto_region(name: str, content: str) -> str:
    """
    将内容包装在自动生成区域标记中

    Args:
        name: 区域名称
        content: 内容

    Returns:
        带标记的内容
    """
    return f"<!-- AUTO-GENERATED-START:{name} -->\n{content}\n<!-- AUTO-GENERATED-END:{name} -->"


def wrap_in_manual_region(name: str, content: str) -> str:
    """
    将内容包装在手动编辑区域标记中

    Args:
        name: 区域名称
        content: 内容

    Returns:
        带标记的内容
    """
    return f"<!-- MANUAL-EDIT-START:{name} -->\n{content}\n<!-- MANUAL-EDIT-END:{name} -->"
