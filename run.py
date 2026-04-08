#!/usr/bin/env python3
"""
Driver API Doc Agent 运行脚本

便捷命令行入口

用法:
    python run.py --input input_file/ --output output_file/
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.main import main

if __name__ == '__main__':
    main()
