#!/usr/bin/env python3
"""Batch import parsed UDI records into MySQL."""

import logging
import re
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import mysql.connector

from parser import parse_zip_file

logger = logging.getLogger(__name__)
BATCH_SIZE = 2_000
INTEGER_RE = re.compile(r"^\d+$")


def _clean(value: Any) -> Optional[str]:
    text = "" if value is None else str(value).strip()
    return text or None


def _integer(value: Any) -> Optional[int]:
    text = _clean(value)
    return int(text) if text and INTEGER_RE.fullmatch(text) else None


def _datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())

    text = _clean(value)
    if not text:
        return None
    text = text.replace("T", " ").removesuffix("Z")
    for pattern in (
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
    ):
        try:
            return datetime.strptime(text, pattern)
        except ValueError:
            continue
    return None


def _date(value: Any) -> Optional[date]:
    parsed = _datetime(value)
    return parsed.date() if parsed else None


# XML tag, database column, converter
DEVICE_SPECS = [
    ("deviceRecordKey", "device_record_key", _clean),
    ("zxxsdycpbs", "zxxsdycpbs", _clean),
    ("cpbsbmtxmc", "cpbsbmtxmc", _clean),
    ("cpbsfbrq", "cpbsfbrq", _date),
    ("cpbsfbrq", "cpbsfbrq_raw", _clean),
    ("zxxsdyzsydydsl", "zxxsdyzsydydsl", _integer),
    ("sydycpbs", "sydycpbs", _clean),
    ("bszt", "bszt", _clean),
    ("sfyzcbayz", "sfyzcbayz", _clean),
    ("zcbacpbs", "zcbacpbs", _clean),
    ("sfybtzjbs", "sfybtzjbs", _clean),
    ("btcpbsyzxxsdycpbssfyz", "btcpbsyzxxsdycpbssfyz", _clean),
    ("btcpbs", "btcpbs", _clean),
    ("cpmctymc", "cpmctymc", _clean),
    ("spmc", "spmc", _clean),
    ("ggxh", "ggxh", _clean),
    ("sfwblztlcp", "sfwblztlcp", _clean),
    ("cpms", "cpms", _clean),
    ("cphhhbh", "cphhhbh", _clean),
    ("yflbm", "yflbm", _clean),
    ("qxlb", "qxlb", _clean),
    ("flbm", "flbm", _clean),
    ("tyshxydm", "tyshxydm", _clean),
    ("zczbhhzbapzbh", "zczbhhzbapzbh", _clean),
    ("ylqxzcrbarmc", "ylqxzcrbarmc", _clean),
    ("ylqxzcrbarywmc", "ylqxzcrbarywmc", _clean),
    ("ybbm", "ybbm", _clean),
    ("cplb", "cplb", _clean),
    ("cgzmraqxgxx", "cgzmraqxgxx", _clean),
    ("sfbjwycxsy", "sfbjwycxsy", _clean),
    ("zdcfsycs", "zdcfsycs", _integer),
    ("sfwwjbz", "sfwwjbz", _clean),
    ("syqsfxyjxmj", "syqsfxyjxmj", _clean),
    ("mjfs", "mjfs", _clean),
    ("qtxxdwzlj", "qtxxdwzlj", _clean),
    ("tsrq", "tsrq", _date),
    ("tsrq", "tsrq_raw", _clean),
    ("scbssfbhph", "scbssfbhph", _clean),
    ("scbssfbhxlh", "scbssfbhxlh", _clean),
    ("scbssfbhscrq", "scbssfbhscrq", _clean),
    ("scbssfbhsxrq", "scbssfbhsxrq", _clean),
    ("tscchcztj", "tscchcztj", _clean),
    ("tsccsm", "tsccsm", _clean),
    ("versionNumber", "version_number", _integer),
    ("versionTime", "version_time", _datetime),
    ("versionTime", "version_time_raw", _clean),
    ("versionStauts", "version_status", _clean),
    ("correctionNumber", "correction_number", _integer),
    ("correctionRemark", "correction_remark", _clean),
    ("correctionTime", "correction_time", _datetime),
    ("correctionTime", "correction_time_raw", _clean),
]
FLAG_COLUMNS = ("has_packing_list", "has_storage_list", "has_clinical_list")
DEVICE_COLUMNS = [column for _, column, _ in DEVICE_SPECS] + list(FLAG_COLUMNS)

INSERT_DEVICE_SQL = (
    f"INSERT INTO udi_devices ({', '.join(DEVICE_COLUMNS)}) VALUES "
    f"({', '.join(['%s'] * len(DEVICE_COLUMNS))}) ON DUPLICATE KEY UPDATE "
    + ", ".join(
        f"{column}=VALUES({column})"
        for column in DEVICE_COLUMNS
        if column != "device_record_key"
    )
)
INSERT_DETAIL_SQL = {
    "udi_packing_list": (
        "INSERT INTO udi_packing_list "
        "(device_record_key,item_no,bzcpbs,cpbzjb,bznhxyjcpbssl,bznhxyjbzcpbs) "
        "VALUES (%s,%s,%s,%s,%s,%s)"
    ),
    "udi_storage_list": (
        "INSERT INTO udi_storage_list "
        "(device_record_key,item_no,cchcztj,zdz,zgz,jldw) "
        "VALUES (%s,%s,%s,%s,%s,%s)"
    ),
    "udi_clinical_list": (
        "INSERT INTO udi_clinical_list "
        "(device_record_key,item_no,lcsycclx,ccz,ccdw) "
        "VALUES (%s,%s,%s,%s,%s)"
    ),
    "udi_contacts": (
        "INSERT INTO udi_contacts "
        "(device_record_key,item_no,qylxrcz,qylxryx,qylxrdh) "
        "VALUES (%s,%s,%s,%s,%s)"
    ),
}
DETAIL_TABLES = tuple(INSERT_DETAIL_SQL)


def _connect(config):
    return mysql.connector.connect(
        host=config.db_host,
        port=config.db_port,
        database=config.db_name,
        user=config.db_user,
        password=config.db_password,
        autocommit=False,
        connection_timeout=30,
        read_timeout=600,
        write_timeout=600,
    )


def _version_key(record: Dict[str, Any]) -> tuple:
    version = _integer(record.get("versionNumber"))
    correction = _integer(record.get("correctionNumber"))
    return (
        version if version is not None else -1,
        correction if correction is not None else -1,
        _datetime(record.get("versionTime")) or datetime.min,
        _datetime(record.get("correctionTime")) or datetime.min,
    )


def _is_newer(record: Dict[str, Any], old: Sequence[Any]) -> bool:
    incoming = _version_key(record)
    old_key = (
        old[0] if old[0] is not None else -1,
        old[1] if old[1] is not None else -1,
        _datetime(old[2]) or datetime.min,
        _datetime(old[3]) or datetime.min,
    )
    return incoming > old_key


def _version_values(record: Dict[str, Any]) -> tuple:
    return (
        _integer(record.get("versionNumber")),
        _integer(record.get("correctionNumber")),
        _datetime(record.get("versionTime")),
        _datetime(record.get("correctionTime")),
    )


def _latest_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    for record in records:
        key = record["deviceRecordKey"]
        if key not in latest or _version_key(record) >= _version_key(latest[key]):
            latest[key] = record
    return list(latest.values())


def _load_existing_versions(conn) -> Dict[str, tuple]:
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT device_record_key,version_number,correction_number,version_time,correction_time "
            "FROM udi_devices"
        )
        return {row[0]: row[1:] for row in cursor.fetchall()}
    finally:
        cursor.close()


def _accepted_records(
    cursor,
    records: List[Dict[str, Any]],
    existing: Optional[Dict[str, tuple]] = None,
) -> List[Dict[str, Any]]:
    records = _latest_records(records)
    if not records:
        return []

    if existing is None:
        keys = [record["deviceRecordKey"] for record in records]
        placeholders = ",".join(["%s"] * len(keys))
        cursor.execute(
            "SELECT device_record_key,version_number,correction_number,version_time,correction_time "
            f"FROM udi_devices WHERE device_record_key IN ({placeholders})",
            keys,
        )
        existing = {row[0]: row[1:] for row in cursor.fetchall()}
    return [
        record
        for record in records
        if record["deviceRecordKey"] not in existing
        or _is_newer(record, existing[record["deviceRecordKey"]])
    ]


def _device_row(record: Dict[str, Any]) -> List[Any]:
    row = [converter(record.get(tag)) for tag, _, converter in DEVICE_SPECS]
    row.extend(int(bool(record.get(flag))) for flag in FLAG_COLUMNS)
    return row


def _detail_rows(record: Dict[str, Any]) -> Dict[str, List[tuple]]:
    key = record["deviceRecordKey"]
    return {
        "udi_packing_list": [
            (
                key,
                number,
                _clean(item.get("bzcpbs")),
                _clean(item.get("cpbzjb")),
                _integer(item.get("bznhxyjcpbssl")),
                _clean(item.get("bznhxyjbzcpbs")),
            )
            for number, item in enumerate(record.get("packing_list", []), 1)
        ],
        "udi_storage_list": [
            (
                key,
                number,
                _clean(item.get("cchcztj")),
                _clean(item.get("zdz")),
                _clean(item.get("zgz")),
                _clean(item.get("jldw")),
            )
            for number, item in enumerate(record.get("storage_list", []), 1)
        ],
        "udi_clinical_list": [
            (
                key,
                number,
                _clean(item.get("lcsycclx")),
                _clean(item.get("ccz")),
                _clean(item.get("ccdw")),
            )
            for number, item in enumerate(record.get("clinical_list", []), 1)
        ],
        "udi_contacts": [
            (
                key,
                number,
                _clean(item.get("qylxrcz")),
                _clean(item.get("qylxryx")),
                _clean(item.get("qylxrdh")),
            )
            for number, item in enumerate(record.get("contact_list", []), 1)
        ],
    }


def _import_batch(
    conn,
    records: List[Dict[str, Any]],
    existing: Optional[Dict[str, tuple]] = None,
) -> List[Dict[str, Any]]:
    cursor = conn.cursor()
    try:
        records = _accepted_records(cursor, records, existing)
        if not records:
            return []

        cursor.executemany(INSERT_DEVICE_SQL, [_device_row(record) for record in records])
        keys = [record["deviceRecordKey"] for record in records]
        placeholders = ",".join(["%s"] * len(keys))
        details = [_detail_rows(record) for record in records]

        for table in DETAIL_TABLES:
            cursor.execute(
                f"DELETE FROM {table} WHERE device_record_key IN ({placeholders})",
                keys,
            )
            rows = [row for detail in details for row in detail[table]]
            if rows:
                cursor.executemany(INSERT_DETAIL_SQL[table], rows)
        return records
    finally:
        cursor.close()


def _log_import(
    conn,
    file_name: str,
    status: str,
    total: int,
    success: int,
    failed: int,
    error: Optional[str],
    duration: float,
) -> None:
    try:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO import_logs "
                "(file_name,status,total_records,success_records,failed_records,error_message,duration_seconds) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (file_name, status, total, success, failed, error, int(duration)),
            )
            conn.commit()
        finally:
            cursor.close()
    except mysql.connector.Error as log_error:
        logger.warning("写入导入日志失败: %s", log_error)


def import_zip_file(
    config,
    path: Path,
    preload_existing: bool = False,
) -> Dict[str, Any]:
    """Parse and import one ZIP. Database/parser errors are raised to the caller."""
    started = time.monotonic()
    total = 0
    updated = 0
    conn = _connect(config)
    try:
        existing = _load_existing_versions(conn) if preload_existing else None
        if existing is not None:
            logger.info("已加载 %s 条现有记录的版本信息", len(existing))
        batch: List[Dict[str, Any]] = []
        for record in parse_zip_file(str(path)):
            total += 1
            batch.append(record)
            if len(batch) >= BATCH_SIZE:
                accepted = _import_batch(conn, batch, existing)
                conn.commit()
                updated += len(accepted)
                if existing is not None:
                    existing.update(
                        (record["deviceRecordKey"], _version_values(record))
                        for record in accepted
                    )
                batch.clear()
                if total % 100_000 == 0:
                    logger.info("导入进度 %s: %s 条", path.name, total)

        if batch:
            accepted = _import_batch(conn, batch, existing)
            conn.commit()
            updated += len(accepted)
            if existing is not None:
                existing.update(
                    (record["deviceRecordKey"], _version_values(record))
                    for record in accepted
                )

        duration = time.monotonic() - started
        _log_import(conn, path.name, "completed", total, total, 0, None, duration)
        logger.info(
            "导入完成: %s，解析 %s 条，新增或更新 %s 条，耗时 %.1f 秒",
            path.name,
            total,
            updated,
            duration,
        )
        return {
            "status": "completed",
            "total_records": total,
            "success_records": total,
            "updated_records": updated,
            "failed_records": 0,
        }
    except Exception as error:
        conn.rollback()
        duration = time.monotonic() - started
        _log_import(
            conn,
            path.name,
            "failed",
            total,
            updated,
            max(0, total - updated),
            str(error),
            duration,
        )
        raise
    finally:
        conn.close()
