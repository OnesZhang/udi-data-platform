"""Small helpers for the inbox/archive file lifecycle."""

import re
import shutil
import time
import zipfile
from pathlib import Path
from typing import Optional


def safe_zip_filename(title: str, fallback: str) -> str:
    """Return a basename that is safe to place directly in inbox/."""
    name = Path(title).name.strip()
    name = re.sub(r"[\x00-\x1f\x7f/\\]+", "_", name)
    if not name.lower().endswith(".zip"):
        return fallback
    stem = name[:-4].rstrip(" .")
    return (stem[:220] + ".zip") if stem else fallback


def is_complete_zip(path: Path) -> bool:
    """Check that the ZIP central directory and every member checksum are readable."""
    try:
        with zipfile.ZipFile(path) as archive:
            if not any(name.lower().endswith(".xml") for name in archive.namelist()):
                return False
            return archive.testzip() is None
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile):
        return False


def list_ready_files(config):
    return sorted(
        (
            path
            for path in config.inbox_dir.glob("*.zip")
            if path.is_file() and is_complete_zip(path)
        ),
        key=lambda path: (path.stat().st_mtime, path.name),
    )


def reserve(config, path: Path) -> Optional[Path]:
    target = config.processing_dir / path.name
    try:
        path.replace(target)
    except FileNotFoundError:
        return None
    return target


def release_for_retry(config, path: Path) -> Path:
    target = config.inbox_dir / path.name
    if target.exists():
        target = config.inbox_dir / f"{path.stem}.retry-{time.time_ns()}{path.suffix}"
    path.replace(target)
    return target


def recover_processing(config) -> None:
    """Put files left by a stopped importer back into the normal inbox."""
    for path in config.processing_dir.glob("*.zip"):
        release_for_retry(config, path)


def archive(config, path: Path, failed: bool = False) -> Path:
    directory = config.failed_dir if failed else config.archive_dir
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / path.name
    if target.exists():
        target = directory / f"{path.stem}-{time.time_ns()}{path.suffix}"
    shutil.move(str(path), str(target))
    return target


def already_seen(config, file_name: str) -> bool:
    """Avoid downloading a file that is already waiting, processing, or archived."""
    locations = (
        config.inbox_dir / file_name,
        config.processing_dir / file_name,
        config.archive_dir / file_name,
        config.failed_dir / file_name,
    )
    return any(path.exists() for path in locations)
