#!/usr/bin/env python3
"""
MySQL 导入模块

策略：
- 设备主表按批次 UPSERT（有则更新，无则插入）
- 明细表（包装/储存/临床/联系人）按批次先删旧数据，再批量插入
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional, Tuple

import mysql.connector

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000

# (XML 标签, 数据库列名)
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

_device_columns = [col for _, col in DEVICE_FIELDS] + FLAG_COLUMNS
INSERT_DEVICE_SQL = (
    "INSERT INTO udi_devices (" + ", ".join(_device_columns) + ") VALUES ("
    + ", ".join(["%s"] * len(_device_columns)) + ") ON DUPLICATE KEY UPDATE "
    + ", ".join(f"{col} = VALUES({col})" for col in _device_columns if col != "device_record_key")
)


def _clean(value: Any) -> Optional[str]:
    """空值统一转 None，避免空字符串触发 MySQL 严格模式报错。"""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_date(value: Any) -> Optional[str]:
    text = _clean(value)
    if text is None:
        return None
    # correctionTime 官方数据可能带时间戳，统一只取日期部分
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    logger.warning(f"无法解析日期，置空: {text}")
    return None


def _parse_int(value: Any) -> Optional[int]:
    text = _clean(value)
    if text is None:
        return None
    try:
        return int(text)
    except ValueError:
        logger.warning(f"无法解析整数，置空: {text}")
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
            (key, _clean(p.get("bzcpbs")), _clean(p.get("cpbzjb")),
             _parse_int(p.get("bznhxyjcpbssl")), _clean(p.get("bznhxyjbzcpbs")))
            for p in record.get("packing_list", [])
        ],
        "udi_storage_list": [
            (key, _clean(s.get("cchcztj")), _clean(s.get("zdz")), _clean(s.get("zgz")), _clean(s.get("jldw")))
            for s in record.get("storage_list", [])
        ],
        "udi_clinical_list": [
            (key, _clean(c.get("lcsycclx")), _clean(c.get("ccz")), _clean(c.get("ccdw")))
            for c in record.get("clinical_list", [])
        ],
        "udi_contacts": [
            (key, _clean(c.get("qylxrcz")), _clean(c.get("qylxryx")), _clean(c.get("qylxrdh")))
            for c in record.get("contact_list", [])
        ],
    }


def _import_batch(conn, records: List[Dict[str, Any]]) -> None:
    """导入一批记录：UPSERT 设备 + 删除旧明细 + 插入新明细。"""
    device_rows = [_device_row(r) for r in records]
    keys = [row[0] for row in device_rows]
    placeholders = ", ".join(["%s"] * len(keys))

    cursor = conn.cursor()
    try:
        cursor.executemany(INSERT_DEVICE_SQL, device_rows)
        for table in DETAIL_TABLES:
            cursor.execute(f"DELETE FROM {table} WHERE device_record_key IN ({placeholders})", keys)
        details = [_detail_rows(r) for r in records]
        for table in DETAIL_TABLES:
            rows = [row for d in details for row in d[table]]
            if rows:
                cursor.executemany(INSERT_DETAIL_SQL[table], rows)
    finally:
        cursor.close()


def _flush(conn, batch: List[Dict[str, Any]]) -> int:
    """导入一批并提交，失败则回滚；返回失败条数。"""
    try:
        _import_batch(conn, batch)
        conn.commit()
        return 0
    except Exception as e:
        conn.rollback()
        logger.error(f"批次导入失败（{len(batch)} 条）: {e}")
        return len(batch)


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
    except mysql.connector.Error as e:
        logger.error(f"数据库连接失败: {e}")
        return None


def _log_import(conn, file_name: str, total: int, success: int, failed: int,
                status: str, error: Optional[str], duration: float) -> None:
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO import_logs (file_name, total_records, success_records, failed_records, "
            "status, error_message, duration_seconds) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (file_name, total, success, failed, status, error, int(duration)),
        )
        conn.commit()
        cursor.close()
    except Exception as e:
        logger.warning(f"记录导入日志失败: {e}")


def import_records(config, file_name: str, record_generator: Generator) -> Dict[str, Any]:
    """从解析生成器导入数据，返回汇总结果。"""
    conn = _connect(config)
    if conn is None:
        return {"status": "failed", "error": "数据库连接失败"}

    start = time.time()
    total = success = failed = 0
    batch: List[Dict[str, Any]] = []

    try:
        for record in record_generator:
            total += 1
            batch.append(record)
            if len(batch) >= BATCH_SIZE:
                batch_failed = _flush(conn, batch)
                failed += batch_failed
                success += len(batch) - batch_failed
                batch = []

        if batch:
            batch_failed = _flush(conn, batch)
            failed += batch_failed
            success += len(batch) - batch_failed

        duration = time.time() - start
        status = "completed" if total > 0 and failed == 0 else "failed"
        _log_import(conn, file_name, total, success, failed, status, None, duration)
        logger.info(f"导入完成: {file_name} 共{total}条 成功{success} 失败{failed} 耗时{duration:.1f}s")
        return {
            "status": status,
            "total_records": total,
            "success_records": success,
            "failed_records": failed,
            "duration_seconds": round(duration, 2),
        }

    except Exception as e:
        conn.rollback()
        duration = time.time() - start
        logger.error(f"导入异常: {e}")
        _log_import(conn, file_name, total, success, failed, "failed", str(e), duration)
        return {
            "status": "failed",
            "error": str(e),
            "total_records": total,
            "success_records": success,
            "failed_records": failed,
        }

    finally:
        conn.close()
