#!/usr/bin/env python3
"""UDI 医疗器械数据平台 - 主入口（每日定时下载 + 导入）"""

import logging
import signal
import sys
import time
from datetime import datetime, timedelta

from config import Config
from db_initializer import initialize_database
from downloader import download_latest
from inbox_worker import FILE_STABLE_SECONDS, InboxWorker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

RSS_INTERVAL_HOURS = 24
INBOX_POLL_SECONDS = 15
shutdown_flag = False


def signal_handler(signum, frame):
    global shutdown_flag
    logger.info("收到停止信号，正在关闭...")
    shutdown_flag = True


def _wait_for_next_scan(seconds):
    """Sleep in short intervals so SIGTERM is handled promptly."""
    end_time = time.monotonic() + seconds
    while not shutdown_flag:
        remaining = end_time - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(1, remaining))


def run_loop(config, inbox_worker):
    """Poll inbox frequently while checking the RSS feed once per day."""
    next_rss_run = datetime.now()
    while not shutdown_flag:
        try:
            inbox_worker.process_ready_files()

            now = datetime.now()
            if now >= next_rss_run:
                if download_latest(config):
                    logger.info("最新 RSS 文件下载完成，等待收件箱处理")
                next_rss_run = now + timedelta(hours=RSS_INTERVAL_HOURS)
                logger.info(f"下次 RSS 检查时间: {next_rss_run.strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception as e:
            logger.error(f"任务执行异常: {e}")

        _wait_for_next_scan(INBOX_POLL_SECONDS)


def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    logger.info("UDI 医疗器械数据平台启动")

    try:
        config = Config()
        if not initialize_database(config):
            sys.exit("数据库初始化失败")

        inbox_worker = InboxWorker(config)
        logger.info(
            "进入运行模式：每 %s 秒检查 inbox，文件稳定 %s 秒后导入；RSS 每 %s 小时检查一次",
            INBOX_POLL_SECONDS,
            FILE_STABLE_SECONDS,
            RSS_INTERVAL_HOURS,
        )
        run_loop(config, inbox_worker)
    except Exception as e:
        logger.error(f"系统异常退出: {e}")
        sys.exit(1)
    finally:
        logger.info("系统已停止")


if __name__ == "__main__":
    main()
