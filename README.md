# Driver API Doc Agent

> 智能化驱动API文档生成工具

## 简介

Driver API Doc Agent 是一个自动化工具，用于从C语言驱动代码（`.c`/`.h`）生成规范的API接口文档（Markdown格式）。

### 核心功能

- ✅ 解析C语言头文件和源文件
- ✅ 提取函数声明、结构体、枚举、宏定义
- ✅ 自动校验声明-定义一致性
- ✅ 生成规范的Markdown API文档
- ✅ LLM智能描述生成（支持 Claude/OpenAI/DeepSeek）
- ✅ 增量更新（保留手动编辑内容）
- ✅ 响应缓存（避免重复API调用）

## 快速开始

### 环境要求

- Python 3.10+
- pip

### 安装

**方式1: pip 安装（推荐）**

```bash
# 进入项目目录
cd driver_api_agent

# 安装为全局命令
pip install -e .

# 验证安装
driver-doc --help
```

**方式2: 直接运行**

```bash
# 安装依赖
pip install -r requirements.txt

# 运行
python -m agent.main --help
```

## 使用方法

### 基础命令

```bash
# 基础用法 - 处理单个文件
python -m agent.main --input input_file/driver.h --output output_file/

# 处理整个目录
python -m agent.main --input input_file/ --output output_file/

# 使用简写参数
python -m agent.main -i input_file/ -o output_file/
```

### 启用 LLM 增强

```bash
# PowerShell - 启用 LLM 并设置 API Key
$env:LLM_API_KEY="your-api-key"
python -m agent.main -i input_file/ -o output_file/ --llm

# CMD - 启用 LLM
set LLM_API_KEY=your-api-key
python -m agent.main -i input_file/ -o output_file/ --llm

# Linux/Mac - 启用 LLM
export LLM_API_KEY=your-api-key
python -m agent.main -i input_file/ -o output_file/ --llm
```

### 详细输出模式

```bash
# 启用详细日志
python -m agent.main -i input_file/ -o output_file/ -v

# 完整示例
python -m agent.main --input input_file/ --output output_file/ --llm --verbose
```

### 指定配置文件

```bash
python -m agent.main -i input_file/ -o output_file/ -c config/custom.yaml
```

## LLM 配置

### 支持的 LLM 提供商

| 提供商 | provider | 默认模型 |
|--------|----------|----------|
| DeepSeek | `deepseek` | deepseek-chat |
| Claude | `claude` | claude-sonnet-4-6 |
| OpenAI | `openai` | gpt-4o-mini |

### 配置方式

**方式1: 环境变量（推荐）**

```powershell
# PowerShell
$env:LLM_API_KEY="sk-xxxxx"
$env:LLM_ENABLED="true"
```

**方式2: 配置文件**

编辑 `config/default.yaml`：

```yaml
llm:
  enabled: true
  provider: deepseek
  api_key: "your-api-key"
  model: deepseek-chat
  base_url: "https://api.deepseek.com"
```

### 费用说明

- 响应结果会缓存到 `.cache/llm/responses.json`
- 第二次运行时命中缓存，不产生API调用费用
- 删除 `.cache/llm/` 目录可强制重新生成

## 项目结构

```
driver_api_agent/
├── agent/               # 核心代码
│   ├── parser/          # 解析器（函数、结构体、枚举、宏）
│   ├── validator/       # 校验器（签名、注释、命名、覆盖率）
│   ├── generator/       # 文档生成器
│   ├── llm/             # LLM集成（Claude/OpenAI/DeepSeek）
│   ├── incremental/     # 增量更新
│   ├── models/          # 数据模型
│   └── utils/           # 工具函数
├── config/              # 配置文件
├── input_file/          # 输入源码
├── output_file/         # 输出文档
├── docs/                # 项目文档
└── tests/               # 测试用例
```

## 配置说明

配置文件位于 `config/default.yaml`：

```yaml
# 输入配置
input:
  encoding: utf-8
  extensions: [.h, .c]
  exclude_patterns: ["*_test.c", "*_test.h"]

# 输出配置
output:
  format: markdown
  encoding: utf-8
  filename_template: "{module}_API_Document.md"

# 校验配置
validator:
  enabled: true
  level: normal
  check_signature: true
  check_struct_comments: true
  check_coverage: true

# LLM配置
llm:
  enabled: false
  provider: deepseek
  model: deepseek-chat
  base_url: "https://api.deepseek.com"
  cache_enabled: true

# 增量更新
incremental:
  enabled: true
  preserve_manual: true
```

## 文档

- [整体规划方案](docs/01_智能化文档生成方案_规划.md)
- [Phase 1 实施计划](docs/02_Phase1_实施计划_MVP.md)
- [Phase 2 实施计划](docs/03_Phase2_实施计划_增强.md)

## 开发状态

| Phase | 状态 | 说明 |
|-------|------|------|
| Phase 1: MVP | ✅ 已完成 | 核心解析 + 基础文档生成 |
| Phase 2: 校验 | ✅ 已完成 | 完整校验体系 + 增量更新 |
| Phase 3: LLM | ✅ 已完成 | Claude/OpenAI/DeepSeek 集成 |
| Phase 4: 扩展 | 📋 计划中 | 设计文档 + 多格式输出 |

## 许可证

MIT License
