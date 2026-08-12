#!/usr/bin/env python3
"""RSS 订阅下载模块 - 下载每日 UDI 数据到 inbox 目录"""

import logging
import os
from datetime import datetime
from typing import List, Optional

import feedparser
import requests

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def fetch_rss(url: str):
    try:
        response = requests.get(url, timeout=30, headers=HEADERS)
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        if feed.entries:
            logger.info(f"RSS 获取成功，共 {len(feed.entries)} 个条目")
            return feed
        logger.warning("RSS 中没有条目")
    except Exception as e:
        logger.error(f"RSS 获取失败: {e}")
    return None


def download_latest(config) -> Optional[str]:
    """下载最新每日数据到 inbox，文件已存在则跳过。"""
    feed = fetch_rss(config.rss_daily_url)
    if feed is None:
        return None

    entry = feed.entries[0]
    title = (entry.get("title") or "").strip()
    filename = title if title.endswith(".zip") else datetime.now().strftime("UDID_DAILY_%Y%m%d.zip")
    filepath = os.path.join(config.inbox_dir, filename)

    if os.path.exists(filepath):
        logger.info(f"文件已存在，跳过下载: {filepath}")
        return filepath

    try:
        response = requests.get(entry.get("link"), stream=True, timeout=300, headers=HEADERS)
        response.raise_for_status()
        with open(filepath, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        logger.info(f"下载完成: {filepath} ({os.path.getsize(filepath) / 1024 / 1024:.1f}MB)")
        return filepath
    except Exception as e:
        logger.error(f"下载失败: {e}")
        if os.path.exists(filepath):
            os.remove(filepath)
        return None


def list_inbox_files(config) -> List[dict]:
    """列出 inbox 目录中的 ZIP 文件，按文件名倒序。"""
    if not os.path.isdir(config.inbox_dir):
        return []
    return [
        {"filename": name, "path": os.path.join(config.inbox_dir, name)}
        for name in sorted(os.listdir(config.inbox_dir), reverse=True)
        if name.endswith(".zip")
    ]
