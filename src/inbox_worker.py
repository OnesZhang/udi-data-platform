#!/usr/bin/env python3
"""Safely detect completed ZIP files in inbox and import them one at a time."""

import logging
import os
import time
import zipfile
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

RETRY_DELAY_SECONDS = 60
FILE_STABLE_SECONDS = 60


@dataclass(frozen=True)
class FileSnapshot:
    """The attributes used to tell whether an inbox file changed."""

    device: int
    inode: int
    size: int
    mtime_ns: int


@dataclass
class PendingFile:
    snapshot: FileSnapshot
    stable_since: float
    retry_after: float = 0.0
    incomplete_logged: bool = False


def _default_parser(zip_path: str):
    # Defer application imports so this file can be checked independently.
    from parser import parse_zip_file

    return parse_zip_file(zip_path)


def _default_importer(config, file_name: str, records):
    from importer import import_records

    return import_records(config, file_name, records)


class InboxWorker:
    """Import ZIP files only after their contents have stopped changing."""

    def __init__(
        self,
        config,
        clock: Optional[Callable[[], float]] = None,
        parser: Optional[Callable] = None,
        importer: Optional[Callable] = None,
        retry_delay_seconds: int = RETRY_DELAY_SECONDS,
    ):
        self.config = config
        self._clock = clock or time.monotonic
        self._parser = parser or _default_parser
        self._importer = importer or _default_importer
        self._retry_delay_seconds = retry_delay_seconds
        self._pending: Dict[str, PendingFile] = {}

    def process_ready_files(self) -> int:
        """Scan inbox once and import every completed, stable ZIP file."""
        now = self._clock()
        files = self._scan_files()
        active_paths = set()
        imported_count = 0

        for path, filename, snapshot in files:
            active_paths.add(path)
            pending = self._pending.get(path)

            if pending is None:
                self._pending[path] = PendingFile(snapshot=snapshot, stable_since=now)
                logger.info("发现 ZIP 文件，等待上传完成: %s", filename)
                continue

            if pending.snapshot != snapshot:
                self._pending[path] = PendingFile(snapshot=snapshot, stable_since=now)
                continue

            if now - pending.stable_since < FILE_STABLE_SECONDS:
                continue

            if now < pending.retry_after:
                continue

            if not self._is_complete_zip(path):
                if not pending.incomplete_logged:
                    logger.info("ZIP 文件尚未完整，继续等待: %s", filename)
                    pending.incomplete_logged = True
                continue

            pending.incomplete_logged = False
            if self._import_file(path, filename, pending, now):
                imported_count += 1

        for path in set(self._pending) - active_paths:
            self._pending.pop(path, None)

        return imported_count

    def _scan_files(self) -> List[Tuple[str, str, FileSnapshot]]:
        """Return ZIP files oldest first so a busy inbox is processed fairly."""
        if not os.path.isdir(self.config.inbox_dir):
            return []

        files = []
        try:
            with os.scandir(self.config.inbox_dir) as entries:
                for entry in entries:
                    if not entry.name.lower().endswith(".zip"):
                        continue
                    try:
                        if not entry.is_file(follow_symlinks=False):
                            continue
                        files.append((entry.path, entry.name, self._snapshot(entry.stat())))
                    except OSError:
                        # The uploader may have renamed or removed the file mid-scan.
                        continue
        except OSError as exc:
            logger.error("扫描 inbox 失败: %s", exc)
            return []

        return sorted(files, key=lambda item: (item[2].mtime_ns, item[1]))

    @staticmethod
    def _snapshot(stat_result) -> FileSnapshot:
        return FileSnapshot(
            device=stat_result.st_dev,
            inode=stat_result.st_ino,
            size=stat_result.st_size,
            mtime_ns=getattr(stat_result, "st_mtime_ns", int(stat_result.st_mtime * 1_000_000_000)),
        )

    def _snapshot_for_path(self, path: str) -> Optional[FileSnapshot]:
        try:
            return self._snapshot(os.stat(path))
        except OSError:
            return None

    @staticmethod
    def _is_complete_zip(path: str) -> bool:
        """Opening the central directory confirms that a ZIP upload has finished."""
        try:
            with zipfile.ZipFile(path, "r") as archive:
                archive.infolist()
            return True
        except (OSError, zipfile.BadZipFile):
            return False

    def _import_file(self, path: str, filename: str, pending: PendingFile, now: float) -> bool:
        # Do not start reading a file that changed after the readiness check.
        if self._snapshot_for_path(path) != pending.snapshot:
            return False

        logger.info("ZIP 文件已稳定，开始导入: %s", filename)
        try:
            result = self._importer(self.config, filename, self._parser(path))
        except Exception as exc:
            logger.error("导入异常，保留文件待重试: %s - %s", filename, exc)
            pending.retry_after = now + self._retry_delay_seconds
            return False

        status = result.get("status")
        counts_present = all(
            key in result for key in ("total_records", "success_records", "failed_records")
        )
        counts_consistent = not counts_present
        if counts_present:
            try:
                counts_consistent = (
                    result["total_records"] == result["success_records"] + result["failed_records"]
                )
            except TypeError:
                counts_consistent = False
        completed = status in {"completed", "completed_with_errors"} and counts_consistent
        if not completed:
            logger.error("导入未完成，保留文件待重试: %s - %s", filename, result)
            pending.retry_after = now + self._retry_delay_seconds
            return False

        if self._snapshot_for_path(path) != pending.snapshot:
            logger.warning("导入期间文件发生变化，保留文件等待下一轮处理: %s", filename)
            return False

        try:
            os.remove(path)
        except OSError as exc:
            logger.error("导入成功但删除文件失败，稍后重试: %s - %s", filename, exc)
            pending.retry_after = now + self._retry_delay_seconds
            return False

        self._pending.pop(path, None)
        if status == "completed_with_errors":
            logger.warning("导入完成但存在异常记录，已记录错误并删除文件: %s", filename)
        else:
            logger.info("导入成功，已删除文件: %s", filename)
        return True
