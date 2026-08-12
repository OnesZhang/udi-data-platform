#!/usr/bin/env python3
"""配置管理模块"""

import logging
import os

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class Config:
    def __init__(self):
        load_dotenv()

        self.db_host = os.getenv("DB_HOST")
        self.db_port = os.getenv("DB_PORT")
        self.db_name = os.getenv("DB_NAME")
        self.db_user = os.getenv("DB_USER")
        self.db_password = os.getenv("DB_PASSWORD")
        self.rss_daily_url = os.getenv(
            "RSS_DAILY_URL", "https://udi.nmpa.gov.cn/rss/download.html?files=daily"
        )
        self.inbox_dir = os.getenv("INBOX_DIR", "inbox")

        self._validate()
        self.db_port = int(self.db_port)
        os.makedirs(self.inbox_dir, exist_ok=True)
        logger.info("配置加载完成")

    def _validate(self):
        required = {
            "DB_HOST": self.db_host,
            "DB_PORT": self.db_port,
            "DB_NAME": self.db_name,
            "DB_USER": self.db_user,
            "DB_PASSWORD": self.db_password,
        }
        missing = [
            name for name, value in required.items() if not value
        ]
        if missing:
            raise ValueError(f"缺少必填配置: {', '.join(missing)}，请在 .env 中配置")
