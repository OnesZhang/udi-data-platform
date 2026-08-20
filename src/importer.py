#!/usr/bin/env python3
"""Import parsed UDI records into MySQL."""

import logging
import re
import time
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

import mysql.connector

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000

# These errors identify a value that cannot fit or be converted for one row.
# Connection, server, and SQL-programming errors must still fail the file.
ROW_DATA_ERROR_CODES = frozenset({1048, 1264, 1292, 1366, 1406, 1411, 1525, 3819})
COLUMN_ERROR_RE = re.compile(r"column\s+['`\"]([^'`\"]+)['`\"]", re.IGNORECASE)

# (XML tag, database column)
DEVICE_FIELDS = [
    ("deviceRecordKey", "device_record_key"),
    ("zxxsdycpbs", "zxxsdycpbs"),
    ("cpbsbmtxmc", "cpbsbmtxmc"),
    ("cpbsfbrq", "cpbsfbrq"),
    ("zxxsdyzsydydsl", "zxxsdyzsydydsl"),
    ("sydycpbs", "sydycpbs"),
    ("bszt", "bszt"),
    ("sfyzcbayz", "sfyzcbayz"),
    ("zcbacpbs", "zcbacpbs"),
    ("sfybtzjbs", "sfybtzjbs"),
    ("btcpbsyzxxsdycpbssfyz", "btcpbsyzxxsdycpbssfyz"),
    ("btcpbs", "btcpbs"),
    ("cpmctymc", "cpmctymc"),
    ("spmc", "spmc"),
    ("ggxh", "ggxh"),
    ("sfwblztlcp", "sfwblztlcp"),
    ("cpms", "cpms"),
    ("cphhhbh", "cphhhbh"),
    ("yflbm", "yflbm"),
    ("qxlb", "qxlb"),
    ("flbm", "flbm"),
    ("tyshxydm", "tyshxydm"),
    ("zczbhhzbapzbh", "zczbhhzbapzbh"),
    ("ylqxzcrbarmc", "ylqxzcrbarmc"),
    ("ylqxzcrbarywmc", "ylqxzcrbarywmc"),
    ("ybbm", "ybbm"),
    ("cplb", "cplb"),
    ("cgzmraqxgxx", "cgzmraqxgxx"),
    ("sfbjwycxsy", "sfbjwycxsy"),
    ("zdcfsycs", "zdcfsycs"),
    ("sfwwjbz", "sfwwjbz"),
    ("syqsfxyjxmj", "syqsfxyjxmj"),
    ("mjfs", "mjfs"),
    ("qtxxdwzlj", "qtxxdwzlj"),
    ("tsrq", "tsrq"),
    ("scbssfbhph", "scbssfbhph"),
    ("scbssfbhxlh", "scbssfbhxlh"),
    ("scbssfbhscrq", "scbssfbhscrq"),
    ("scbssfbhsxrq", "scbssfbhsxrq"),
    ("tscchcztj", "tscchcztj"),
    ("tsccsm", "tsccsm"),
    ("versionNumber", "version_number"),
    ("versionTime", "version_time"),
    ("versionStauts", "version_status"),
    ("correctionNumber", "correction_number"),
    ("correctionRemark", "correction_remark"),
    ("correctionTime", "correction_time"),
]

DATE_FIELDS = {"cpbsfbrq", "tsrq", "version_time", "correction_time"}
INT_FIELDS = {"zxxsdyzsydydsl", "version_number", "correction_number"}
FLAG_COLUMNS = ["has_packing_list", "has_storage_list", "has_clinical_list"]
DETAIL_TABLES = ("udi_packing_list", "udi_storage_list", "udi_clinical_list", "udi_contacts")

INSERT_DETAIL_SQL = {
    "udi_packing_list": (
        "INSERT INTO udi_packing_list (device_record_key, bzcpbs, cpbzjb, bznhxyjcpbssl, bznhxyjbzcpbs) "
        "VALUES (%s, %s, %s, %s, %s)"
    ),
    "udi_storage_list": (
        "INSERT INTO udi_storage_list (device_record_key, cchcztj, zdz, zgz, jldw) "
        "VALUES (%s, %s, %s, %s, %s)"
    ),
    "udi_clinical_list": (
        "INSERT INTO udi_clinical_list (device_record_key, lcsycclx, ccz, ccdw) "
        "VALUES (%s, %s, %s, %s)"
    ),
    "udi_contacts": (
        "INSERT INTO udi_contacts (device_record_key, qylxrcz, qylxryx, qylxrdh) "
        "VALUES (%s, %s, %s, %s)"
    ),
}

_device_columns = [column for _, column in DEVICE_FIELDS] + FLAG_COLUMNS
INSERT_DEVICE_SQL = (
    "INSERT INTO udi_devices (" + ", ".join(_device_columns) + ") VALUES ("
    + ", ".join(["%s"] * len(_device_columns)) + ") ON DUPLICATE KEY UPDATE "
    + ", ".join(f"{column} = VALUES({column})" for column in _device_columns if column != "device_record_key")
)


def _clean(value: Any) -> Optional[str]:
    """Convert empty values to NULL without truncating source text."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_date(value: Any) -> Optional[str]:
    text = _clean(value)
    if text is None:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    logger.warning("无法解析日期，置空: %s", text)
    return None


def _parse_int(value: Any) -> Optional[int]:
    text = _clean(value)
    if text is None:
        return None
    try:
        return int(text)
    except ValueError:
        logger.warning("无法解析整数，置空: %s", text)
        return None


def _device_row(record: Dict[str, Any]) -> List[Any]:
    row = []
    for tag, column in DEVICE_FIELDS:
        value = record.get(tag)
        if column in DATE_FIELDS:
            row.append(_parse_date(value))
        elif column in INT_FIELDS:
            row.append(_parse_int(value))
        else:
            row.append(_clean(value))
    row.extend(1 if record.get(flag) else 0 for flag in FLAG_COLUMNS)
    return row


def _detail_rows(record: Dict[str, Any]) -> Dict[str, List[Tuple[Any, ...]]]:
    key = record.get("deviceRecordKey")
    return {
        "udi_packing_list": [
            (key, _clean(item.get("bzcpbs")), _clean(item.get("cpbzjb")),
             _parse_int(item.get("bznhxyjcpbssl")), _clean(item.get("bznhxyjbzcpbs")))
            for item in record.get("packing_list", [])
        ],
        "udi_storage_list": [
            (key, _clean(item.get("cchcztj")), _clean(item.get("zdz")),
             _clean(item.get("zgz")), _clean(item.get("jldw")))
            for item in record.get("storage_list", [])
        ],
        "udi_clinical_list": [
            (key, _clean(item.get("lcsycclx")), _clean(item.get("ccz")), _clean(item.get("ccdw")))
            for item in record.get("clinical_list", [])
        ],
        "udi_contacts": [
            (key, _clean(item.get("qylxrcz")), _clean(item.get("qylxryx")), _clean(item.get("qylxrdh")))
            for item in record.get("contact_list", [])
        ],
    }


def _import_batch(conn, records: List[Dict[str, Any]]) -> None:
    """Import one transaction: device UPSERT and replacement detail rows."""
    device_rows = [_device_row(record) for record in records]
    keys = [row[0] for row in device_rows]
    placeholders = ", ".join(["%s"] * len(keys))

    cursor = conn.cursor()
    try:
        cursor.executemany(INSERT_DEVICE_SQL, device_rows)
        for table in DETAIL_TABLES:
            cursor.execute(f"DELETE FROM {table} WHERE device_record_key IN ({placeholders})", keys)
        details = [_detail_rows(record) for record in records]
        for table in DETAIL_TABLES:
            rows = [row for detail in details for row in detail[table]]
            if rows:
                cursor.executemany(INSERT_DETAIL_SQL[table], rows)
    finally:
        cursor.close()


def _error_code(error: Exception) -> Optional[int]:
    code = getattr(error, "errno", None)
    try:
        return int(code) if code is not None else None
    except (TypeError, ValueError):
        return None


def _is_row_data_error(error: Exception) -> bool:
    return _error_code(error) in ROW_DATA_ERROR_CODES


def _affected_column(error: Exception) -> Optional[str]:
    match = COLUMN_ERROR_RE.search(str(error))
    return match.group(1) if match else None


def _record_failure(record: Dict[str, Any], error: Exception) -> Dict[str, Any]:
    return {
        "device_record_key": _clean(record.get("deviceRecordKey")),
        "error_code": _error_code(error),
        "affected_column": _affected_column(error),
        "error_message": str(error),
    }


def _flush(
    conn,
    batch: List[Dict[str, Any]],
) -> Tuple[int, List[Dict[str, Any]]]:
    """Commit valid rows and recursively isolate row-level data errors."""
    try:
        _import_batch(conn, batch)
        conn.commit()
        return len(batch), []
    except Exception as error:
        conn.rollback()
        if not _is_row_data_error(error):
            raise

        if len(batch) == 1:
            failure = _record_failure(batch[0], error)
            logger.error(
                "单条记录导入失败: deviceRecordKey=%s column=%s code=%s error=%s",
                failure["device_record_key"],
                failure["affected_column"],
                failure["error_code"],
                failure["error_message"],
            )
            return 0, [failure]

        midpoint = len(batch) // 2
        logger.warning("批次包含数据错误，拆分定位：%s 条", len(batch))
        left_success, left_failures = _flush(conn, batch[:midpoint])
        right_success, right_failures = _flush(conn, batch[midpoint:])
        return left_success + right_success, left_failures + right_failures


def _connect(config):
    try:
        return mysql.connector.connect(
            host=config.db_host,
            port=config.db_port,
            database=config.db_name,
            user=config.db_user,
            password=config.db_password,
            autocommit=False,
            connection_timeout=30,
        )
    except mysql.connector.Error as error:
        logger.error("数据库连接失败: %s", error)
        return None


def _log_record_errors(conn, file_name: str, failures: List[Dict[str, Any]]) -> bool:
    if not failures:
        return True
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.executemany(
            "INSERT INTO import_error_records "
            "(file_name, device_record_key, error_code, affected_column, error_message) "
            "VALUES (%s, %s, %s, %s, %s)",
            [
                (
                    file_name,
                    failure["device_record_key"],
                    failure["error_code"],
                    failure["affected_column"],
                    failure["error_message"],
                )
                for failure in failures
            ],
        )
        conn.commit()
        return True
    except Exception as error:
        conn.rollback()
        logger.warning("记录逐条导入错误失败: %s", error)
        return False
    finally:
        if cursor is not None:
            cursor.close()


def _log_import(
    conn,
    file_name: str,
    total: int,
    success: int,
    failed: int,
    status: str,
    error: Optional[str],
    duration: float,
) -> None:
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO import_logs (file_name, total_records, success_records, failed_records, "
            "status, error_message, duration_seconds) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (file_name, total, success, failed, status, error, int(duration)),
        )
        conn.commit()
    except Exception as exc:
        logger.warning("记录导入日志失败: %s", exc)
    finally:
        if cursor is not None:
            cursor.close()


def import_records(config, file_name: str, record_generator: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Import records and return a file-level result for inbox cleanup."""
    conn = _connect(config)
    if conn is None:
        return {"status": "failed", "error": "数据库连接失败"}

    start = time.time()
    total = success = failed = 0
    batch: List[Dict[str, Any]] = []
    row_failures: List[Dict[str, Any]] = []

    try:
        for record in record_generator:
            total += 1
            batch.append(record)
            if len(batch) >= BATCH_SIZE:
                committed, failures = _flush(conn, batch)
                success += committed
                row_failures.extend(failures)
                failed += len(failures)
                batch = []

        if batch:
            committed, failures = _flush(conn, batch)
            success += committed
            row_failures.extend(failures)
            failed += len(failures)

        duration = time.time() - start
        error_log_ok = _log_record_errors(conn, file_name, row_failures)
        if total == 0:
            status = "failed"
            error = "未解析到任何记录"
        elif row_failures and not error_log_ok:
            status = "failed"
            error = "部分记录导入失败且无法写入异常记录表"
        elif row_failures:
            status = "completed_with_errors"
            error = f"{failed} 条记录未导入，详见 import_error_records"
        else:
            status = "completed"
            error = None

        _log_import(conn, file_name, total, success, failed, status, error, duration)
        logger.info(
            "导入完成: %s 共%s条 成功%s 失败%s 状态%s 耗时%.1fs",
            file_name,
            total,
            success,
            failed,
            status,
            duration,
        )
        return {
            "status": status,
            "total_records": total,
            "success_records": success,
            "failed_records": failed,
            "duration_seconds": round(duration, 2),
        }

    except Exception as error:
        conn.rollback()
        duration = time.time() - start
        logger.error("导入异常: %s", error)
        _log_record_errors(conn, file_name, row_failures)
        _log_import(conn, file_name, total, success, failed, "failed", str(error), duration)
        return {
            "status": "failed",
            "error": str(error),
            "total_records": total,
            "success_records": success,
            "failed_records": failed,
        }

    finally:
        conn.close()
