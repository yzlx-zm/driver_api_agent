"""
Driver API Doc Agent 主入口

用法:
    python -m agent.main --input input_file/ --output output_file/
"""

import argparse
import sys
import os
from pathlib import Path
from typing import Optional, List

from .utils.config import get_config, ConfigManager
from .utils.logger import init_logger, get_logger, log_info, log_error, log_warning
from .utils.file_utils import read_file, write_file, get_file_list

from .parser import (
    FunctionParser, StructParser, EnumParser,
    MacroParser, CommentParser
)
from .validator import ValidationRunner
from .generator import MarkdownGenerator, DesignGenerator
from .models.ir import ModuleIR, Function, Struct, Enum, Macro
from .llm.description_generator import create_llm_client, DescriptionGenerator
from .incremental import DiffDetector, RegionParser, DocumentMerger


class DriverAPIDocAgent:
    """Driver API Doc Agent 主类"""

    def __init__(self, config_path: Optional[str] = None):
        # 加载配置
        self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.all

        # 初始化日志
        init_logger(self.config)
        self.logger = get_logger()

        log_info("Driver API Doc Agent 初始化...")

        # 初始化解析器
        self.func_parser = FunctionParser({'category_keywords': self.config.parser_category_keywords})
        self.struct_parser = StructParser()
        self.enum_parser = EnumParser()
        self.macro_parser = MacroParser()
        self.comment_parser = CommentParser()

        # 初始化校验器
        self.validation_runner = ValidationRunner(self.config.__dict__)

        # 初始化生成器
        self.generator = MarkdownGenerator({
            'template_language': self.config.template_language,
            'template_include_toc': self.config.template_include_toc,
        })

        # 初始化设计文档生成器
        self.design_generator = DesignGenerator({
            'template_language': self.config.template_language,
        })

    def process(self, input_path: str, output_path: str, generate_design: bool = False) -> bool:
        """
        处理输入文件，生成文档

        Args:
            input_path: 输入文件或目录路径
            output_path: 输出文件或目录路径
            generate_design: 是否生成设计文档

        Returns:
            是否成功
        """
        log_info(f"开始处理: {input_path}")

        # 1. 获取输入文件列表
        input_files = self._get_input_files(input_path)
        if not input_files:
            log_error(f"未找到输入文件: {input_path}")
            return False

        log_info(f"找到 {len(input_files)} 个输入文件")

        # 2. 解析文件
        ir = self._parse_files(input_files)
        if not ir:
            log_error("解析失败")
            return False

        # 3. 校验
        if self.config.validator_enabled:
            log_info("执行校验...")
            validation_report = self._validate(ir)
            if validation_report.has_errors():
                log_error("校验发现错误，请先修复")
                print(validation_report.get_summary())
                if self.config.validator_level == "strict":
                    return False
        else:
            validation_report = None

        # 3.5 LLM 描述增强（可选）
        if self.config.llm_enabled:
            log_info("LLM 描述增强...")
            self._enhance_with_llm(ir)

        # 4. 生成文档
        log_info("生成文档...")
        doc_content = self.generator.generate(ir, validation_report)

        # 4.5 增量合并（如果目标文件已存在且有区域标记）
        output_file = self._get_output_file(input_path, output_path, ir)
        if self.config.incremental_enabled:
            doc_content = self._try_incremental_merge(output_file, doc_content)

        # 5. 写入文件
        if not write_file(output_file, doc_content, self.config.output_encoding):
            log_error(f"写入文件失败: {output_file}")
            return False

        log_info(f"文档生成完成: {output_file}")

        # 6. 生成设计文档（可选）
        if generate_design:
            log_info("生成设计文档...")
            design_content = self.design_generator.generate(ir)

            # 设计文档输出路径
            design_file = self._get_design_output_file(output_path, ir)
            if not write_file(design_file, design_content, self.config.output_encoding):
                log_error(f"写入设计文档失败: {design_file}")
            else:
                log_info(f"设计文档生成完成: {design_file}")

        # 7. 输出统计
        stats = ir.get_stats()
        log_info(f"统计: {stats}")

        return True

    def _get_input_files(self, input_path: str) -> List[str]:
        """获取输入文件列表"""
        path = Path(input_path)

        if path.is_file():
            return [str(path)]
        elif path.is_dir():
            return get_file_list(
                str(path),
                extensions=self.config.input_extensions,
                exclude_patterns=self.config.input_exclude_patterns,
                recursive=True
            )
        else:
            return []

    def _parse_files(self, input_files: List[str]) -> Optional[ModuleIR]:
        """解析所有文件"""
        ir = ModuleIR()

        # 分离.h和.c文件
        header_files = [f for f in input_files if f.endswith('.h')]
        source_files = [f for f in input_files if f.endswith('.c')]

        # 解析头文件（声明）
        declarations = {'functions': [], 'structs': [], 'enums': [], 'macros': []}
        for header_file in header_files:
            log_info(f"解析头文件: {header_file}")
            content, success = read_file(header_file, self.config.input_encoding)
            if not success:
                log_warning(f"无法读取文件: {header_file}")
                continue

            # 解析注释（每个文件独立解析，保证行号正确）
            comments = self.comment_parser.parse(content, header_file)

            # 解析各元素
            functions = self.func_parser.parse(content, header_file)
            structs = self.struct_parser.parse(content, header_file)
            enums = self.enum_parser.parse(content, header_file)
            macros = self.macro_parser.parse(content, header_file)

            # 将注释关联到各元素
            self.comment_parser.attach_comments_to_functions(functions, content)
            self.comment_parser.attach_comments_to_structs(structs)
            self.comment_parser.attach_comments_to_enums(enums)
            self.comment_parser.attach_comments_to_macros(macros)

            declarations['functions'].extend(functions)
            declarations['structs'].extend(structs)
            declarations['enums'].extend(enums)
            declarations['macros'].extend(macros)

            if header_file:
                ir.header_file = header_file
                ir.name = self._extract_module_name(header_file)

        # 解析源文件（定义）— 提取函数实现的签名
        definitions = {'functions': []}
        for source_file in source_files:
            log_info(f"解析源文件: {source_file}")
            content, success = read_file(source_file, self.config.input_encoding)
            if not success:
                log_warning(f"无法读取文件: {source_file}")
                continue

            # 使用 parse_definitions 提取函数定义（带函数体）的签名
            functions = self.func_parser.parse_definitions(content, source_file)

            # 将注释关联到函数
            self.comment_parser.attach_comments_to_functions(functions, content)

            definitions['functions'].extend(functions)

            if source_files and not ir.source_file:
                ir.source_file = source_file

        # 合并结果到IR（去重：同名函数优先取声明中的注释 + 定义中的实现信息）
        ir.functions = self._merge_functions(
            declarations['functions'], definitions['functions']
        )
        ir.structs = declarations['structs']
        ir.enums = declarations['enums']
        ir.macros = declarations['macros']

        # 存储声明和定义用于校验
        ir._declarations = declarations['functions']
        ir._definitions = definitions['functions']

        return ir

    def _validate(self, ir: ModuleIR) -> 'ValidationReport':
        """执行校验"""
        # 准备额外参数（用于签名校验器）
        kwargs = {
            'declarations': getattr(ir, '_declarations', []),
            'definitions': getattr(ir, '_definitions', [])
        }
        report = self.validation_runner.run_all(ir, **kwargs)
        return report

    def _try_incremental_merge(self, output_file: str, new_content: str) -> str:
        """
        尝试增量合并：如果已有文档含区域标记，保留手动编辑区域

        Args:
            output_file: 输出文件路径
            new_content: 新生成的文档内容

        Returns:
            最终写入的文档内容
        """
        old_content, success = read_file(output_file, self.config.output_encoding)
        if not success:
            log_info("首次生成文档，跳过增量合并")
            return new_content

        merger = DocumentMerger()
        merged = merger.merge(old_content, new_content)

        if merged != new_content:
            log_info("增量合并完成，已保留手动编辑区域")
        else:
            log_info("增量合并完成（无手动编辑区域需保留）")

        return merged

    def _merge_functions(self, declarations: list, definitions: list) -> list:
        """
        合并 .h 声明和 .c 定义，去重并保留最完整信息

        策略：
        - 同名函数：优先用声明（含 Doxygen 注释），补充定义中的 source_file
        - 仅在 .c 中存在的函数（static 或未在 .h 声明）：直接加入
        """
        result = []
        seen = {}  # name -> index in result

        # 先添加声明（通常有完整的注释）
        for func in declarations:
            result.append(func)
            seen[func.name] = len(result) - 1

        # 合并定义
        for func_def in definitions:
            if func_def.name in seen:
                # 同名：补充定义信息到已有声明
                idx = seen[func_def.name]
                existing = result[idx]
                # 补充 .c 文件信息
                if not existing.source_file:
                    existing.source_file = func_def.source_file
                if not existing.implementation_line:
                    existing.implementation_line = func_def.implementation_line
            else:
                # 仅在 .c 中存在（static 函数等）
                result.append(func_def)
                seen[func_def.name] = len(result) - 1

        return result

    def _get_output_file(self, input_path: str, output_path: str, ir: ModuleIR) -> str:
        """确定输出文件路径"""
        output_dir = Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)

        module_name = ir.name or "module"
        filename = self.config.output_filename_template.format(module=module_name, date="")

        return str(output_dir / filename)

    def _get_design_output_file(self, output_path: str, ir: ModuleIR) -> str:
        """确定设计文档输出文件路径"""
        output_dir = Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)

        module_name = ir.name or "module"
        filename = f"{module_name.upper()}_Design_Document.md"

        return str(output_dir / filename)

    def _extract_module_name(self, header_file: str) -> str:
        """从头文件名提取模块名"""
        basename = Path(header_file).stem
        # 移除常见后缀
        for suffix in ['_driver', '_hal', '_api', '_drv']:
            if basename.endswith(suffix):
                basename = basename[:-len(suffix)]
        return basename.upper()

    def _enhance_with_llm(self, ir: ModuleIR) -> None:
        """
        使用 LLM 为缺少描述的元素生成描述

        Args:
            ir: 模块中间表示
        """
        try:
            # 检查是否启用自动描述生成
            if not self.config.llm_auto_generate_desc:
                log_info("LLM 自动描述生成已禁用 (llm_auto_generate_desc=false)")
                return

            client = create_llm_client(self.config.__dict__)
            if not client or not client.is_available():
                # 尝试 fallback provider
                fallback = self.config.llm_fallback_provider
                if fallback:
                    fallback_config = {**self.config.__dict__, 'llm_provider': fallback}
                    client = create_llm_client(fallback_config)
                if not client or not client.is_available():
                    log_warning("LLM 客户端不可用，跳过描述增强")
                    return
                log_info(f"使用 fallback provider: {client.name}")

            # 初始化缓存和追踪器
            cache = None
            tracker = None
            if self.config.llm_cache_enabled:
                from .llm.response_cache import ResponseCache
                cache = ResponseCache(self.config.llm_cache_dir)
            if self.config.llm_track_usage:
                from .llm.usage_tracker import UsageTracker
                tracker = UsageTracker()

            generator = DescriptionGenerator(
                client,
                {'max_description_length': self.config.llm_max_desc_length},
                cache=cache,
                tracker=tracker,
            )

            def needs_desc(desc: str) -> bool:
                """检查描述是否需要生成"""
                return not desc or generator._is_placeholder(desc)

            # 为函数生成描述 + 参数 + 返回值
            for func in ir.functions:
                if needs_desc(func.description):
                    func.description = generator.generate_function_description(func)
                    func.brief = func.description
                # 参数描述
                for param in func.params:
                    if needs_desc(param.description):
                        param.description = generator.generate_param_description(func, param)
                # 返回值描述
                if needs_desc(func.return_desc) and func.return_type != "void":
                    func.return_desc = generator.generate_return_description(func)

            # 为结构体生成描述 + 字段描述
            for struct in ir.structs:
                if needs_desc(struct.description):
                    struct.description = generator.generate_struct_description(struct)
                for fld in struct.fields:
                    if needs_desc(fld.description):
                        fld.description = generator.generate_struct_field_description(struct, fld)

            # 为枚举生成描述 + 枚举值描述
            for enum in ir.enums:
                if needs_desc(enum.description):
                    enum.description = generator.generate_enum_description(enum)
                for val in enum.values:
                    if needs_desc(val.description):
                        val.description = generator.generate_enum_value_description(enum, val)

            # 为宏生成描述
            for macro in ir.macros:
                if needs_desc(macro.description):
                    macro.description = generator.generate_macro_description(macro)

            # 打印使用报告
            if tracker:
                log_info(tracker.print_report())
            if cache:
                stats = cache.stats()
                log_info(f"缓存统计: {stats['entries']} 条, 命中 {stats['hits']}, 未命中 {stats['misses']}")

            log_info("LLM 描述增强完成")

        except Exception as e:
            log_warning(f"LLM 增强失败: {e}，继续使用原始描述")


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description='Driver API Doc Agent - 自动生成驱动API文档',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 单文件处理
  python -m agent.main --input driver.h --output docs/

  # 目录处理
  python -m agent.main --input src/ --output docs/ --config config/custom.yaml

  # 启用LLM增强（需配置API Key）
  LLM_API_KEY=your_key python -m agent.main --input src/ --output docs/ --llm
        """
    )

    parser.add_argument(
        '--input', '-i',
        required=True,
        help='输入文件或目录路径'
    )

    parser.add_argument(
        '--output', '-o',
        required=True,
        help='输出文件或目录路径'
    )

    parser.add_argument(
        '--config', '-c',
        help='配置文件路径'
    )

    parser.add_argument(
        '--llm',
        action='store_true',
        help='启用LLM增强（需要配置API Key）'
    )

    parser.add_argument(
        '--design',
        action='store_true',
        help='生成设计文档（包含架构图、时序图等）'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='详细输出'
    )

    args = parser.parse_args()

    # 设置日志级别
    if args.verbose:
        os.environ['LOG_LEVEL'] = 'DEBUG'

    # LLM开关
    if args.llm:
        os.environ['LLM_ENABLED'] = 'true'

    # 创建agent并运行
    agent = DriverAPIDocAgent(args.config)

    success = agent.process(args.input, args.output, generate_design=args.design)

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
