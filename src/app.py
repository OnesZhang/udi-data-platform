#!/usr/bin/env python3
"""UDI 医疗器械数据平台 - 主入口（每日定时下载 + 导入）"""

import logging
import os
import signal
import sys
import time
from datetime import datetime, timedelta

from config import Config
from db_initializer import initialize_database
from downloader import download_latest, list_inbox_files
from importer import import_records
from parser import parse_zip_file

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

INTERVAL_HOURS = 24
shutdown_flag = False


def signal_handler(signum, frame):
    global shutdown_flag
    logger.info("收到停止信号，正在关闭...")
    shutdown_flag = True


def run_once(config):
    """下载最新数据并处理 inbox 中的文件。"""
    if download_latest(config):
        logger.info("最新文件下载完成")
    process_inbox(config)


def process_inbox(config):
    files = list_inbox_files(config)
    if not files:
        logger.info("inbox 中没有 ZIP 文件")
        return

    for info in files:
        path, name = info["path"], info["filename"]
        logger.info(f"处理文件: {name}")
        result = import_records(config, name, parse_zip_file(path))
        if result.get("status") == "completed" and result.get("failed_records", 0) == 0:
            os.remove(path)
            logger.info(f"导入成功，已删除文件: {name}")
        else:
            logger.error(f"导入未完成，保留文件待下次重试: {result}")


def run_loop(config):
    while not shutdown_flag:
        try:
            run_once(config)
            next_run = datetime.now() + timedelta(hours=INTERVAL_HOURS)
            logger.info(f"下次执行时间: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception as e:
            logger.error(f"任务执行异常: {e}")

        for _ in range(INTERVAL_HOURS * 60):
            if shutdown_flag:
                break
            time.sleep(60)


def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    logger.info("UDI 医疗器械数据平台启动")

    try:
        config = Config()
        if not initialize_database(config):
            sys.exit("数据库初始化失败")

        run_once(config)
        logger.info(f"进入定时模式，每 {INTERVAL_HOURS} 小时执行一次")
        run_loop(config)
    except Exception as e:
        logger.error(f"系统异常退出: {e}")
        sys.exit(1)
    finally:
        logger.info("系统已停止")


if __name__ == "__main__":
    main()
