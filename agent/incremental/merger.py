"""文档合并器

合并新旧文档，保留手动编辑区域
"""

from typing import Dict, Optional
from .diff_detector import DiffResult
from .region_parser import RegionParser, wrap_in_auto_region, ParsedDocument


class DocumentMerger:
    """文档合并器

    合并新旧文档，保留手动编辑区域，更新自动生成区域
    """

    def __init__(self):
        self.parser = RegionParser()

    def merge(self, old_document: Optional[str], new_content: str,
              diff: Optional[DiffResult] = None) -> str:
        """
        合并新旧文档

        Args:
            old_document: 旧文档内容（如果是首次生成则为 None）
            new_content: 新生成的内容
            diff: 差异检测结果（可选，用于日志）

        Returns:
            合并后的文档
        """
        # 如果没有旧文档，直接返回新内容
        if old_document is None:
            return new_content

        # 检查旧文档是否有标记
        if not self.parser.has_markers(old_document):
            # 旧文档没有标记，直接用新内容覆盖
            # 但可以选择保留整个旧文档，或者直接覆盖
            return new_content

        # 解析旧文档
        old_parsed = self.parser.parse(old_document)

        # 解析新文档（如果新文档有标记）
        if self.parser.has_markers(new_content):
            new_parsed = self.parser.parse(new_content)
        else:
            # 新文档没有标记，直接使用新内容
            return new_content

        # 合并文档
        return self._merge_documents(old_parsed, new_parsed)

    def _merge_documents(self, old_parsed: ParsedDocument,
                         new_parsed: ParsedDocument) -> str:
        """
        合并两个解析后的文档

        策略：
        1. 保留旧文档的手动编辑区域
        2. 用新文档的自动生成区域替换旧文档的
        3. 新增的区域直接添加
        """
        result_parts = []

        # 添加前言（使用新的）
        if new_parsed.preamble:
            result_parts.append(new_parsed.preamble)

        # 合并区域（保持新文档的区域顺序）
        # 先按新文档顺序遍历，再添加仅存在于旧文档的手动区域
        seen_names = set()

        for name in new_parsed.regions:
            seen_names.add(name)
            old_region = old_parsed.regions.get(name)
            new_region = new_parsed.regions.get(name)

            if old_region and new_region:
                # 两边都有这个区域
                if old_region.region_type == 'manual':
                    # 保留手动编辑区域
                    result_parts.append(
                        f"<!-- MANUAL-EDIT-START:{name} -->\n"
                        f"{old_region.content}\n"
                        f"<!-- MANUAL-EDIT-END:{name} -->"
                    )
                else:
                    # 使用新的自动生成区域
                    result_parts.append(
                        f"<!-- AUTO-GENERATED-START:{name} -->\n"
                        f"{new_region.content}\n"
                        f"<!-- AUTO-GENERATED-END:{name} -->"
                    )
            elif new_region:
                # 只有新文档有这个区域（新增）
                result_parts.append(
                    f"<!-- AUTO-GENERATED-START:{name} -->\n"
                    f"{new_region.content}\n"
                    f"<!-- AUTO-GENERATED-END:{name} -->"
                )

        # 保留仅存在于旧文档的手动编辑区域
        for name in old_parsed.regions:
            if name not in seen_names:
                old_region = old_parsed.regions[name]
                if old_region.region_type == 'manual':
                    result_parts.append(
                        f"<!-- MANUAL-EDIT-START:{name} -->\n"
                        f"{old_region.content}\n"
                        f"<!-- MANUAL-EDIT-END:{name} -->"
                    )

        # 添加后语（使用新的）
        if new_parsed.postamble:
            result_parts.append(new_parsed.postamble)

        return '\n\n'.join(result_parts)

    def extract_manual_content(self, document: str) -> Dict[str, str]:
        """
        提取文档中的手动编辑区域

        Args:
            document: 文档内容

        Returns:
            区域名 -> 内容 的映射
        """
        return self.parser.extract_manual_regions(document)
