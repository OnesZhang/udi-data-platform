#!/usr/bin/env python3
"""
UDI XML 解析器

将 ZIP 内的 XML 逐条解析为设备记录字典。字段名沿用官方 XML 标签
（含官方拼写 versionStauts），仅在直接解析失败时做一次清洗重试。
"""

import logging
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import Any, Dict, Generator, Optional

logger = logging.getLogger(__name__)

# 设备主表字段（与官方 XML 标签一致）
DEVICE_FIELDS = [
    "zxxsdycpbs", "cpbsbmtxmc", "cpbsfbrq", "zxxsdyzsydydsl", "sydycpbs",
    "bszt", "sfyzcbayz", "zcbacpbs", "sfybtzjbs", "btcpbsyzxxsdycpbssfyz",
    "btcpbs", "cpmctymc", "spmc", "ggxh", "sfwblztlcp", "cpms", "cphhhbh",
    "yflbm", "qxlb", "flbm", "tyshxydm", "zczbhhzbapzbh", "ylqxzcrbarmc",
    "ylqxzcrbarywmc", "ybbm", "cplb", "cgzmraqxgxx", "sfbjwycxsy",
    "zdcfsycs", "sfwwjbz", "syqsfxyjxmj", "mjfs", "qtxxdwzlj", "tsrq",
    "scbssfbhph", "scbssfbhxlh", "scbssfbhscrq", "scbssfbhsxrq",
    "tscchcztj", "tsccsm", "deviceRecordKey", "versionNumber", "versionTime",
    "versionStauts",  # 官方字段拼写如此，非笔误
    "correctionNumber", "correctionRemark", "correctionTime",
]

# 嵌套列表：父标签 -> (子元素标签, 字段列表, 记录键, 是否有标记)
NESTED_LISTS = {
    "packingList": ("packing", ["bzcpbs", "cpbzjb", "bznhxyjcpbssl", "bznhxyjbzcpbs"], "packing_list", "has_packing_list"),
    "storageList": ("storage", ["cchcztj", "zdz", "zgz", "jldw"], "storage_list", "has_storage_list"),
    "clinicalList": ("clinical", ["lcsycclx", "ccz", "ccdw"], "clinical_list", "has_clinical_list"),
    "contactList": ("contact", ["qylxrcz", "qylxryx", "qylxrdh"], "contact_list", None),
}

INVALID_CHARS_RE = re.compile(r"&#(?:13|10|9);|[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]")


def _clean_xml(content: str) -> str:
    """移除无效控制字符并修复裸 & 符号。"""
    content = INVALID_CHARS_RE.sub("", content)
    content = content.replace("&", "&amp;")
    for name in ("amp", "lt", "gt", "quot", "apos"):
        content = content.replace(f"&amp;{name};", f"&{name};")
    return content


def _parse_root(content: str) -> Optional[ET.Element]:
    try:
        return ET.fromstring(content)
    except ET.ParseError:
        logger.warning("XML 解析失败，尝试清洗后重试")
        try:
            return ET.fromstring(_clean_xml(content))
        except ET.ParseError as e:
            logger.error(f"清洗后仍解析失败: {e}")
            return None


def _records_from_root(root: ET.Element) -> Generator[Dict[str, Any], None, int]:
    """从已构建的根节点逐条产出设备记录，返回记录数。"""
    total = 0
    for device in root.findall(".//device"):
        record = _extract_device(device)
        if record:
            total += 1
            yield record
    return total


def _field_text(elem: ET.Element, tag: str) -> Optional[str]:
    child = elem.find(tag)
    return child.text.strip() if child is not None and child.text else None


def _extract_device(device: ET.Element) -> Optional[Dict[str, Any]]:
    record = {field: _field_text(device, field) for field in DEVICE_FIELDS}

    for parent, (element, fields, record_key, flag) in NESTED_LISTS.items():
        items = []
        list_elem = device.find(parent)
        if list_elem is not None:
            items = [
                {field: _field_text(item, field) for field in fields}
                for item in list_elem.findall(element)
            ]
        record[record_key] = items
        if flag:
            record[flag] = bool(items)

    if not record.get("deviceRecordKey"):
        logger.debug("缺少 deviceRecordKey，跳过记录")
        return None
    return record


def parse_zip_file(zip_path: str) -> Generator[Dict[str, Any], None, None]:
    """解析 ZIP 中的所有 XML，逐条产出设备记录。"""
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        xml_files = [name for name in zip_ref.namelist() if name.endswith(".xml")]
        logger.info(f"解析 {os.path.basename(zip_path)}，共 {len(xml_files)} 个 XML 文件")

        total = 0
        for xml_file in xml_files:
            try:
                with zip_ref.open(xml_file) as f:
                    # 流式解析：每处理完一条记录立即释放，控制内存峰值
                    for _, device in ET.iterparse(f, events=("end",)):
                        if device.tag != "device":
                            continue
                        record = _extract_device(device)
                        device.clear()
                        if record:
                            total += 1
                            yield record
            except ET.ParseError:
                # 流式解析失败时回退：整文件读取并清洗后重试
                logger.warning(f"流式解析失败，回退整文件清洗: {xml_file}")
                with zip_ref.open(xml_file) as f:
                    root = _parse_root(f.read().decode("utf-8", errors="replace"))
                if root is not None:
                    for record in _records_from_root(root):
                        total += 1
                        yield record
            except Exception as e:
                logger.error(f"处理 XML 失败 {xml_file}: {e}")
        logger.info(f"解析完成，共 {total} 条记录")
