#!/usr/bin/env python3
"""RSS downloader. It only downloads ZIP files into inbox/."""

import logging
import os
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List

import requests

from file_store import already_seen, is_complete_zip, safe_zip_filename

logger = logging.getLogger(__name__)
HEADERS = {"User-Agent": "UDI-data-downloader/1.0"}


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child_text(element: ET.Element, name: str) -> str:
    for child in element:
        if _local_name(child.tag) == name:
            return (child.text or "").strip()
    return ""


def fetch_rss(url: str):
    try:
        response = requests.get(url, timeout=30, headers=HEADERS)
        response.raise_for_status()
        root = ET.fromstring(response.content)
    except (requests.RequestException, ET.ParseError) as error:
        logger.error("RSS 获取失败: %s", error)
        return []

    entries = []
    for element in root.iter():
        if _local_name(element.tag) not in ("item", "entry"):
            continue
        link = _child_text(element, "link")
        if not link:
            for child in element:
                if _local_name(child.tag) == "link":
                    link = child.attrib.get("href", "").strip()
                    break
        entries.append({"title": _child_text(element, "title"), "link": link})
    logger.info("RSS 获取成功，共 %s 个条目", len(entries))
    return entries


def download_feed(config, url: str, source_name: str) -> List[str]:
    """Download every RSS entry that is not already present in the file store."""
    downloaded = []
    for index, entry in enumerate(fetch_rss(url), 1):
        link = entry["link"]
        if not link:
            continue

        fallback = f"UDI_{source_name.upper()}_{datetime.now():%Y%m%d}_{index}.zip"
        file_name = safe_zip_filename(entry["title"], fallback)
        if already_seen(config, file_name):
            logger.info("文件已存在，跳过下载: %s", file_name)
            continue

        target = config.inbox_dir / file_name
        part = config.inbox_dir / f".{file_name}.{uuid.uuid4().hex}.part"
        try:
            with requests.get(
                link,
                stream=True,
                timeout=(30, 600),
                headers=HEADERS,
            ) as response:
                response.raise_for_status()
                with part.open("xb") as output:
                    for chunk in response.iter_content(1024 * 1024):
                        if chunk:
                            output.write(chunk)

            if not is_complete_zip(part):
                raise ValueError("下载结果不是完整的 XML ZIP 文件")
            os.replace(part, target)
            downloaded.append(file_name)
            logger.info("下载完成，已投递 inbox: %s", file_name)
        except (OSError, ValueError, requests.RequestException) as error:
            part.unlink(missing_ok=True)
            logger.error("下载失败 %s: %s", file_name, error)
    return downloaded
