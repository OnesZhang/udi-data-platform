#!/usr/bin/env python3
"""Streaming parser for the official UDI XML ZIP files."""

import io
import logging
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import Any, Dict, Generator, Optional

logger = logging.getLogger(__name__)

DEVICE_FIELDS = [
    "zxxsdycpbs", "cpbsbmtxmc", "cpbsfbrq", "zxxsdyzsydydsl", "sydycpbs",
    "bszt", "sfyzcbayz", "zcbacpbs", "sfybtzjbs", "btcpbsyzxxsdycpbssfyz",
    "btcpbs", "cpmctymc", "spmc", "ggxh", "sfwblztlcp", "cpms", "cphhhbh",
    "yflbm", "qxlb", "flbm", "tyshxydm", "zczbhhzbapzbh", "ylqxzcrbarmc",
    "ylqxzcrbarywmc", "ybbm", "cplb", "cgzmraqxgxx", "sfbjwycxsy",
    "zdcfsycs", "sfwwjbz", "syqsfxyjxmj", "mjfs", "qtxxdwzlj", "tsrq",
    "scbssfbhph", "scbssfbhxlh", "scbssfbhscrq", "scbssfbhsxrq", "tscchcztj",
    "tsccsm", "deviceRecordKey", "versionNumber", "versionTime", "versionStauts",
    "correctionNumber", "correctionRemark", "correctionTime",
]

NESTED_LISTS = {
    "packingList": ("packing", ["bzcpbs", "cpbzjb", "bznhxyjcpbssl", "bznhxyjbzcpbs"], "packing_list"),
    "storageList": ("storage", ["cchcztj", "zdz", "zgz", "jldw"], "storage_list"),
    "clinicalList": ("clinical", ["lcsycclx", "ccz", "ccdw"], "clinical_list"),
    "contactList": ("contact", ["qylxrcz", "qylxryx", "qylxrdh"], "contact_list"),
}
DEVICE_FIELD_SET = set(DEVICE_FIELDS)

INVALID_XML_RE = re.compile(
    r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F\uFDD0-\uFDEF\uFFFE\uFFFF]"
)
BARE_AMPERSAND_RE = re.compile(
    r"&(?!#\d+;|#(?:x|X)[0-9A-Fa-f]+;|amp;|lt;|gt;|quot;|apos;)"
)
XML_DECLARATION_RE = re.compile(r"^\s*<\?xml[^>]*\?>", re.IGNORECASE)


class XMLParseError(ValueError):
    """The XML could not be parsed after the small official-data cleanup."""


def _clean_xml(content: str) -> str:
    content = INVALID_XML_RE.sub("", content)
    content = BARE_AMPERSAND_RE.sub("&amp;", content)
    return XML_DECLARATION_RE.sub("", content, count=1)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(element: ET.Element, name: str):
    return (child for child in element if _local_name(child.tag) == name)


def _extract_device(device: ET.Element) -> Optional[Dict[str, Any]]:
    record = {field: None for field in DEVICE_FIELDS}
    for child in device:
        field = _local_name(child.tag)
        if field in DEVICE_FIELD_SET:
            text = (child.text or "").strip()
            record[field] = text or None

    for parent_name, (item_name, fields, result_name) in NESTED_LISTS.items():
        parent = next(_children(device, parent_name), None)
        items = []
        if parent is not None:
            for item in _children(parent, item_name):
                values = {field: None for field in fields}
                for child in item:
                    field = _local_name(child.tag)
                    if field in values:
                        text = (child.text or "").strip()
                        values[field] = text or None
                items.append(values)
        record[result_name] = items

    record["has_packing_list"] = bool(record["packing_list"])
    record["has_storage_list"] = bool(record["storage_list"])
    record["has_clinical_list"] = bool(record["clinical_list"])
    return record if record.get("deviceRecordKey") else None


def _xml_sort_key(name: str):
    match = re.search(r"PART(\d+)", name, re.IGNORECASE)
    return (int(match.group(1)) if match else 0, name)


def _parse_xml(content: str) -> Generator[Dict[str, Any], None, None]:
    try:
        for _, element in ET.iterparse(io.StringIO(content), events=("end",)):
            if _local_name(element.tag) != "device":
                continue
            record = _extract_device(element)
            element.clear()
            if record:
                yield record
    except ET.ParseError as error:
        raise XMLParseError(str(error)) from error


def parse_zip_file(zip_path: str) -> Generator[Dict[str, Any], None, None]:
    """Yield device records from every XML member in a ZIP, in part order."""
    total = 0
    try:
        archive = zipfile.ZipFile(zip_path)
    except (OSError, zipfile.BadZipFile) as error:
        raise XMLParseError(f"无法打开 ZIP: {zip_path}") from error

    with archive:
        names = sorted(
            (name for name in archive.namelist() if name.lower().endswith(".xml")),
            key=_xml_sort_key,
        )
        if not names:
            raise XMLParseError("ZIP 中没有 XML 文件")
        logger.info("解析 %s，共 %s 个 XML 文件", zip_path, len(names))

        for name in names:
            raw = archive.read(name).decode("utf-8", errors="replace")
            for record in _parse_xml(_clean_xml(raw)):
                total += 1
                yield record

    logger.info("解析完成，共 %s 条记录", total)
