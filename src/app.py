#!/usr/bin/env python3
"""Command-line entry point for the independent downloader/importer services."""

import argparse
import logging
import signal
import sys
import threading
from typing import Dict

import mysql.connector

from config import Config
from db_initializer import initialize_database, reset_database
from downloader import download_feed
from file_store import archive, list_ready_files, recover_processing, release_for_retry, reserve
from importer import import_zip_file
from parser import XMLParseError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
STOP = threading.Event()


def _stop(signum, frame) -> None:
    logger.info("收到停止信号，等待当前步骤结束")
    STOP.set()


def _wait(seconds: int) -> None:
    STOP.wait(max(1, seconds))


def run_downloader_once(config: Config, feed: str) -> int:
    files = download_feed(config, config.rss_url(feed), feed)
    logger.info("%s RSS 本次下载 %s 个文件", feed, len(files))
    return len(files)


def run_downloader_daemon(config: Config) -> None:
    while not STOP.is_set():
        run_downloader_once(config, "daily")
        _wait(config.download_interval_hours * 3600)


def process_inbox(config: Config, preload_existing: bool = False) -> Dict[str, int]:
    """Import every complete ZIP currently in inbox, regardless of its source."""
    outcomes = {"completed": 0, "failed": 0, "retry": 0}
    for ready_path in list_ready_files(config):
        if STOP.is_set():
            break

        processing_path = reserve(config, ready_path)
        if processing_path is None:
            continue

        try:
            result = import_zip_file(
                config,
                processing_path,
                preload_existing=preload_existing,
            )
        except mysql.connector.Error as error:
            logger.error("数据库暂不可用，文件留在 inbox 等待重试: %s", error)
            release_for_retry(config, processing_path)
            outcomes["retry"] += 1
            break
        except (XMLParseError, OSError, ValueError) as error:
            logger.exception("文件解析失败，移入 failed: %s", error)
            archive(config, processing_path, failed=True)
            outcomes["failed"] += 1
            continue
        except Exception as error:
            logger.exception("文件导入失败，移入 failed: %s", error)
            archive(config, processing_path, failed=True)
            outcomes["failed"] += 1
            continue

        archive(config, processing_path)
        outcomes["completed"] += 1
        logger.info("文件已归档: %s (%s)", processing_path.name, result)
    return outcomes


def _prepare_database(config: Config, reset: bool = False) -> None:
    if reset and not reset_database(config):
        raise RuntimeError("测试数据库重置失败")
    if not initialize_database(config):
        raise RuntimeError("数据库初始化失败")


def run_importer_once(config: Config, reset: bool = False) -> Dict[str, int]:
    _prepare_database(config, reset)
    recover_processing(config)
    return process_inbox(config, preload_existing=True)


def run_importer_daemon(config: Config) -> None:
    _prepare_database(config)
    recover_processing(config)
    while not STOP.is_set():
        outcomes = process_inbox(config)
        if any(outcomes.values()):
            logger.info("本轮处理结果: %s", outcomes)
        _wait(config.poll_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="UDI 下载与导入服务")
    parser.add_argument(
        "--mode",
        choices=("download-daemon", "download-once", "import-daemon", "import-once"),
        default="import-daemon",
    )
    parser.add_argument(
        "--feed",
        choices=("daily", "weekly", "monthly", "full"),
        default="daily",
        help="download-once 使用的 RSS 类型",
    )
    parser.add_argument(
        "--reset-db",
        action="store_true",
        help="删除并重建配置中的测试数据库，仅用于 import-once",
    )
    args = parser.parse_args()

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    download_mode = args.mode.startswith("download")
    if args.reset_db and args.mode != "import-once":
        parser.error("--reset-db 仅可用于 import-once")

    config = Config(require_database=not download_mode)
    if args.mode == "download-daemon":
        run_downloader_daemon(config)
    elif args.mode == "download-once":
        run_downloader_once(config, args.feed)
    elif args.mode == "import-daemon":
        run_importer_daemon(config)
    else:
        logger.info("本次处理结果: %s", run_importer_once(config, args.reset_db))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        logger.exception("服务异常退出: %s", error)
        sys.exit(1)
