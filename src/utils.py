#!/usr/bin/env python3
"""
通用工具函数
"""

import os
import logging

def ensure_dir(dir_path):
    """确保目录存在"""
    os.makedirs(dir_path, exist_ok=True)
    return dir_path

def setup_logging(level=logging.INFO):
    """设置日志（可选，主要日志配置在config.py中）"""
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
