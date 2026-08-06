#!/usr/bin/env python3
"""
配置管理模块
"""

import os
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class Config:
    def __init__(self):
        load_dotenv()
        
        # 数据库配置 - 必须配置，不配置则报错
        self.db_host = os.getenv('DB_HOST')
        self.db_port = os.getenv('DB_PORT')
        self.db_name = os.getenv('DB_NAME')
        self.db_user = os.getenv('DB_USER')
        self.db_password = os.getenv('DB_PASSWORD')
        
        # RSS配置
        self.rss_daily_url = os.getenv('RSS_DAILY_URL', 'https://udi.nmpa.gov.cn/rss/download.html?files=daily')
        self.rss_weekly_url = os.getenv('RSS_WEEKLY_URL', 'https://udi.nmpa.gov.cn/rss/download.html?files=weekly')
        self.rss_monthly_url = os.getenv('RSS_MONTHLY_URL', 'https://udi.nmpa.gov.cn/rss/download.html?files=monthly')
        self.rss_full_url = os.getenv('RSS_FULL_URL', 'https://udi.nmpa.gov.cn/rss/download.html?files=full')
        
        # 文件目录配置 - 统一使用inbox目录
        self.inbox_dir = os.getenv('INBOX_DIR', 'inbox')
        
        # 验证必填配置
        self._validate_config()
        
        # 转换端口为整数
        if self.db_port:
            self.db_port = int(self.db_port)
        
        # 确保inbox目录存在
        os.makedirs(self.inbox_dir, exist_ok=True)
        
        logger.info("配置加载完成")
    
    def _validate_config(self):
        """验证必填配置"""
        required_fields = {
            'DB_HOST': self.db_host,
            'DB_PORT': self.db_port,
            'DB_NAME': self.db_name,
            'DB_USER': self.db_user,
            'DB_PASSWORD': self.db_password
        }
        
        missing_fields = [name for name, value in required_fields.items() if not value]
        
        if missing_fields:
            error_msg = f"缺少必填配置: {', '.join(missing_fields)}\n请在 .env 文件中配置这些字段"
            logger.error(error_msg)
            raise ValueError(error_msg)
    
    def get_db_config(self):
        """获取数据库配置字典"""
        return {
            'host': self.db_host,
            'port': self.db_port,
            'database': self.db_name,
            'user': self.db_user,
            'password': self.db_password
        }
