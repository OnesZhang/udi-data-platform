#!/usr/bin/env python3
"""Application configuration loaded from environment variables."""

import os
import re
from pathlib import Path

from dotenv import load_dotenv

DATABASE_NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")
RSS_BASE_URL = "https://udi.nmpa.gov.cn/rss/download.html?files="


class Config:
    def __init__(self, require_database: bool = True):
        load_dotenv()

        self.db_host = os.getenv("DB_HOST")
        self.db_port = int(os.getenv("DB_PORT", "3306"))
        self.db_name = os.getenv("DB_NAME")
        self.db_user = os.getenv("DB_USER")
        self.db_password = os.getenv("DB_PASSWORD")

        self.rss_urls = {
            "daily": os.getenv("RSS_DAILY_URL", RSS_BASE_URL + "daily"),
            "weekly": os.getenv("RSS_WEEKLY_URL", RSS_BASE_URL + "weekly"),
            "monthly": os.getenv("RSS_MONTHLY_URL", RSS_BASE_URL + "monthly"),
            "full": os.getenv("RSS_FULL_URL", RSS_BASE_URL + "full"),
        }

        self.inbox_dir = Path(os.getenv("INBOX_DIR", "inbox")).resolve()
        self.archive_dir = Path(os.getenv("ARCHIVE_DIR", "archive")).resolve()
        self.failed_dir = Path(os.getenv("FAILED_DIR", "failed")).resolve()
        self.processing_dir = self.inbox_dir / ".processing"

        self.poll_seconds = int(os.getenv("IMPORT_POLL_SECONDS", "60"))
        self.download_interval_hours = int(os.getenv("DOWNLOAD_INTERVAL_HOURS", "24"))

        if require_database:
            self._validate_database()

        for directory in (
            self.inbox_dir,
            self.archive_dir,
            self.failed_dir,
            self.processing_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def _validate_database(self) -> None:
        required = {
            "DB_HOST": self.db_host,
            "DB_NAME": self.db_name,
            "DB_USER": self.db_user,
            "DB_PASSWORD": self.db_password,
        }
        missing = [name for name, value in required.items() if value is None]
        if missing:
            raise ValueError(f"缺少数据库配置: {', '.join(missing)}")
        if not DATABASE_NAME_RE.fullmatch(self.db_name or ""):
            raise ValueError("DB_NAME 仅允许英文字母、数字和下划线")

    def rss_url(self, feed: str) -> str:
        try:
            return self.rss_urls[feed]
        except KeyError as error:
            raise ValueError(f"不支持的 RSS 类型: {feed}") from error
