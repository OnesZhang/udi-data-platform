#!/usr/bin/env python3
"""Parse official UDI XML files from a ZIP archive."""

import io
import logging
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import Any, Dict, Generator, Optional, Tuple

logger = logging.getLogger(__name__)

# Device fields use the spelling from the official XML schema.
DEVICE_FIELDS = [
    "zxxsdycpbs", "cpbsbmtxmc", "cpbsfbrq", "zxxsdyzsydydsl", "sydycpbs",
    "bszt", "sfyzcbayz", "zcbacpbs", "sfybtzjbs", "btcpbsyzxxsdycpbssfyz",
    "btcpbs", "cpmctymc", "spmc", "ggxh", "sfwblztlcp", "cpms", "cphhhbh",
    "yflbm", "qxlb", "flbm", "tyshxydm", "zczbhhzbapzbh", "ylqxzcrbarmc",
    "ylqxzcrbarywmc", "ybbm", "cplb", "cgzmraqxgxx", "sfbjwycxsy",
    "zdcfsycs", "sfwwjbz", "syqsfxyjxmj", "mjfs", "qtxxdwzlj", "tsrq",
    "scbssfbhph", "scbssfbhxlh", "scbssfbhscrq", "scbssfbhsxrq",
    "tscchcztj", "tsccsm", "deviceRecordKey", "versionNumber", "versionTime",
    "versionStauts", "correctionNumber", "correctionRemark", "correctionTime",
]
DEVICE_FIELD_SET = set(DEVICE_FIELDS)

# Parent tag -> (item tag, item fields, output key).
NESTED_LISTS = {
    "packingList": ("packing", ["bzcpbs", "cpbzjb", "bznhxyjcpbssl", "bznhxyjbzcpbs"], "packing_list"),
    "storageList": ("storage", ["cchcztj", "zdz", "zgz", "jldw"], "storage_list"),
    "clinicalList": ("clinical", ["lcsycclx", "ccz", "ccdw"], "clinical_list"),
    "contactList": ("contact", ["qylxrcz", "qylxryx", "qylxrdh"], "contact_list"),
}

HEADER_RECORD_COUNT_TAG = "numberRkeyecordXML"

# XML 1.0 permits only tab, LF, and CR below U+0020. Keep U+007F-U+009F;
# they are legal XML characters and removing them would alter source data.
INVALID_XML10_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\uD800-\uDFFF\uFFFE\uFFFF]")
BARE_AMPERSAND_RE = re.compile(
    r"&(?!amp;|lt;|gt;|quot;|apos;|#(?:[0-9]+|[xX][0-9A-Fa-f]+);)"
)
NUMERIC_ENTITY_RE = re.compile(r"&#(?:[0-9]+|[xX][0-9A-Fa-f]+);")
CDATA_RE = re.compile(r"(<!\[CDATA\[.*?\]\]>)", re.DOTALL)
XML_DECLARATION_RE = re.compile(r"^\s*<\?xml[^>]*\?>", re.IGNORECASE)
PART_NUMBER_RE = re.compile(r"PART(\d+)", re.IGNORECASE)
MAX_NESTED_ZIP_DEPTH = 8


class XMLParseError(ValueError):
    """Raised when an XML member cannot be safely normalized or validated."""


def _local_name(tag: Any) -> str:
    """Return a tag name without an optional XML namespace."""
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


def _text_value(element: ET.Element) -> Optional[str]:
    text = "".join(element.itertext()).strip()
    return text or None


def _children(element: ET.Element, name: str):
    for child in element:
        if _local_name(child.tag) == name:
            yield child


def _escape_bare_ampersands(content: str) -> str:
    """Escape only ampersands that are not valid XML entity references."""
    parts = CDATA_RE.split(content)
    for index in range(0, len(parts), 2):
        parts[index] = BARE_AMPERSAND_RE.sub("&amp;", parts[index])
    return "".join(parts)


def _is_valid_xml10_codepoint(value: int) -> bool:
    return (
        value in (0x9, 0xA, 0xD)
        or 0x20 <= value <= 0xD7FF
        or 0xE000 <= value <= 0xFFFD
        or 0x10000 <= value <= 0x10FFFF
    )


def _remove_invalid_numeric_entities(content: str) -> str:
    """Remove numeric references to characters XML 1.0 cannot represent."""
    def replace(match: re.Match) -> str:
        token = match.group(0)[2:-1]
        base = 16 if token[:1].lower() == "x" else 10
        digits = token[1:] if base == 16 else token
        try:
            value = int(digits, base)
        except ValueError:
            return ""
        return match.group(0) if _is_valid_xml10_codepoint(value) else ""

    return NUMERIC_ENTITY_RE.sub(replace, content)


def _clean_xml(content: str) -> str:
    """Remove only XML 1.0-invalid code points and repair bare ampersands."""
    content = INVALID_XML10_RE.sub("", content)
    content = _remove_invalid_numeric_entities(content)
    content = _escape_bare_ampersands(content)
    # Parsing a Unicode string with an encoding declaration is interpreter
    # dependent; the declaration carries no data needed by the extractor.
    return XML_DECLARATION_RE.sub("", content, count=1)


def _normalize_xml(content: str):
    invalid_count = len(INVALID_XML10_RE.findall(content))
    return _clean_xml(content), invalid_count


def _read_normalized_xml(
    archive: zipfile.ZipFile,
    member: zipfile.ZipInfo,
    display_name: str,
    log_cleanup: bool,
) -> str:
    try:
        raw = archive.read(member)
    except (KeyError, OSError, RuntimeError, NotImplementedError, zipfile.BadZipFile) as error:
        raise XMLParseError(f"读取 XML 失败 {display_name}: {error}") from error

    try:
        content = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise XMLParseError(f"{display_name}: 不是有效的 UTF-8 XML: {error}") from error
    if content.startswith("\ufeff"):
        content = content[1:]

    normalized, invalid_count = _normalize_xml(content)
    if log_cleanup and invalid_count:
        logger.warning("%s: 已移除 %s 个 XML 1.0 非法字符", display_name, invalid_count)
    return normalized


def _validate_xml(content: str, name: str) -> int:
    """Validate one XML member before any records are emitted."""
    root_tag = None
    declared_count = None
    device_count = 0
    current_device_key = None
    in_device = False
    seen_keys = set()
    path = []

    try:
        context = ET.iterparse(io.StringIO(content), events=("start", "end"))
        for event, element in context:
            tag = _local_name(element.tag)
            if event == "start":
                path.append(tag)
                if root_tag is None:
                    root_tag = tag
                if tag == "device":
                    if len(path) < 2 or path[-2] != "devices":
                        raise XMLParseError(f"{name}: device 不在 devices 节点下")
                    if in_device:
                        raise XMLParseError(f"{name}: 发现嵌套 device 记录")
                    in_device = True
                    current_device_key = None
                continue

            if tag == HEADER_RECORD_COUNT_TAG:
                if len(path) < 2 or path[-2] != "header":
                    raise XMLParseError(f"{name}: {HEADER_RECORD_COUNT_TAG} 不在 header 节点下")
                value = _text_value(element)
                if value is None:
                    raise XMLParseError(f"{name}: {HEADER_RECORD_COUNT_TAG} 为空")
                try:
                    parsed_count = int(value)
                except ValueError as error:
                    raise XMLParseError(f"{name}: {HEADER_RECORD_COUNT_TAG} 不是整数: {value}") from error
                if parsed_count < 0:
                    raise XMLParseError(f"{name}: {HEADER_RECORD_COUNT_TAG} 不能为负数")
                if declared_count is not None and declared_count != parsed_count:
                    raise XMLParseError(f"{name}: {HEADER_RECORD_COUNT_TAG} 重复且数值不一致")
                declared_count = parsed_count
            elif tag == "deviceRecordKey" and in_device:
                if len(path) < 2 or path[-2] != "device":
                    raise XMLParseError(f"{name}: deviceRecordKey 不在 device 节点下")
                current_device_key = (_text_value(element) or "").strip()
            elif tag == "device":
                if not in_device:
                    raise XMLParseError(f"{name}: device 结构异常")
                device_count += 1
                if not current_device_key:
                    raise XMLParseError(f"{name}: 存在缺少 deviceRecordKey 的设备记录")
                if current_device_key in seen_keys:
                    raise XMLParseError(f"{name}: deviceRecordKey 重复: {current_device_key}")
                seen_keys.add(current_device_key)
                in_device = False
                current_device_key = None

            # The validation pass does not need field contents. Clearing each
            # completed element keeps memory bounded for large XML members.
            element.clear()
            path.pop()
    except XMLParseError:
        raise
    except ET.ParseError as error:
        raise XMLParseError(f"{name}: XML 解析失败: {error}") from error

    if root_tag != "udid":
        raise XMLParseError(f"{name}: 根节点不是 udid，而是 {root_tag!r}")
    if declared_count is None:
        raise XMLParseError(f"{name}: 缺少 {HEADER_RECORD_COUNT_TAG}")
    if device_count != declared_count:
        raise XMLParseError(
            f"{name}: XML 声明 {declared_count} 条，实际解析到 {device_count} 条"
        )
    return declared_count


def _field_text(element: ET.Element, tag: str) -> Optional[str]:
    child = next(_children(element, tag), None)
    return _text_value(child) if child is not None else None


def _extract_device(device: ET.Element) -> Optional[Dict[str, Any]]:
    record = {field: None for field in DEVICE_FIELDS}
    for child in device:
        field = _local_name(child.tag)
        if field in DEVICE_FIELD_SET:
            record[field] = _text_value(child)

    for parent_name, (item_name, fields, result_name) in NESTED_LISTS.items():
        parent = next(_children(device, parent_name), None)
        items = []
        if parent is not None:
            for item in _children(parent, item_name):
                items.append({field: _field_text(item, field) for field in fields})
        record[result_name] = items

    record["has_packing_list"] = bool(record["packing_list"])
    record["has_storage_list"] = bool(record["storage_list"])
    record["has_clinical_list"] = bool(record["clinical_list"])
    return record if record.get("deviceRecordKey") else None


def _extract_xml_records(content: str, name: str) -> Generator[Dict[str, Any], None, None]:
    try:
        for _, device in ET.iterparse(io.StringIO(content), events=("end",)):
            if _local_name(device.tag) != "device":
                continue
            record = _extract_device(device)
            device.clear()
            if record is None:
                raise XMLParseError(f"{name}: 设备记录缺少 deviceRecordKey")
            yield record
    except XMLParseError:
        raise
    except ET.ParseError as error:
        raise XMLParseError(f"{name}: XML 提取失败: {error}") from error


def _xml_sort_key(name: str):
    match = PART_NUMBER_RE.search(name)
    return (int(match.group(1)) if match else 0, name)


def _iter_xml_members(
    archive: zipfile.ZipFile,
    archive_name: str,
    depth: int = 0,
) -> Generator[Tuple[zipfile.ZipFile, zipfile.ZipInfo, str], None, None]:
    """Yield XML members from an archive and nested ZIP members in sort order."""
    members = sorted(
        (member for member in archive.infolist() if not member.is_dir()),
        key=lambda member: _xml_sort_key(member.filename),
    )
    for member in members:
        member_name = f"{archive_name}!{member.filename}"
        lower_name = member.filename.lower()
        if lower_name.endswith(".xml"):
            yield archive, member, member_name
            continue
        if not lower_name.endswith(".zip"):
            continue
        if depth >= MAX_NESTED_ZIP_DEPTH:
            raise XMLParseError(
                f"{member_name}: ZIP 嵌套层数超过 {MAX_NESTED_ZIP_DEPTH} 层"
            )

        try:
            nested_bytes = archive.read(member)
            nested_archive = zipfile.ZipFile(io.BytesIO(nested_bytes), "r")
        except (OSError, RuntimeError, NotImplementedError, zipfile.BadZipFile) as error:
            raise XMLParseError(f"无法打开嵌套 ZIP {member_name}: {error}") from error

        with nested_archive:
            yield from _iter_xml_members(nested_archive, member_name, depth + 1)


def parse_zip_file(zip_path: str) -> Generator[Dict[str, Any], None, None]:
    """Validate every XML in a ZIP tree, then yield each device exactly once."""
    try:
        archive = zipfile.ZipFile(zip_path, "r")
    except (OSError, zipfile.BadZipFile) as error:
        raise XMLParseError(f"无法打开 ZIP: {zip_path}: {error}") from error

    with archive:
        # The complete validation pass prevents a malformed later XML from
        # causing earlier records to be emitted and then emitted again on retry.
        expected_counts: Dict[str, int] = {}
        expected_total = 0
        for source_archive, member, name in _iter_xml_members(archive, zip_path):
            if name in expected_counts:
                raise XMLParseError("ZIP 中存在重复的 XML 文件名")
            content = _read_normalized_xml(source_archive, member, name, log_cleanup=True)
            declared_count = _validate_xml(content, name)
            expected_counts[name] = declared_count
            expected_total += declared_count

        if not expected_counts:
            raise XMLParseError("ZIP 中没有 XML 文件")

        logger.info("解析 %s，共 %s 个 XML 文件", zip_path, len(expected_counts))
        logger.info("XML 完整性校验通过，确认 %s 条记录", expected_total)

        total = 0
        extracted_names = set()
        for source_archive, member, name in _iter_xml_members(archive, zip_path):
            if name not in expected_counts or name in extracted_names:
                raise XMLParseError(f"{name}: XML 文件在提取阶段结构发生变化")
            extracted_names.add(name)
            content = _read_normalized_xml(source_archive, member, name, log_cleanup=False)
            extracted_count = 0
            for record in _extract_xml_records(content, name):
                extracted_count += 1
                total += 1
                yield record
            if extracted_count != expected_counts[name]:
                raise XMLParseError(
                    f"{name}: 校验阶段声明 {expected_counts[name]} 条，提取阶段得到 {extracted_count} 条"
                )

        if len(extracted_names) != len(expected_counts):
            raise XMLParseError("ZIP 中 XML 文件在提取阶段结构发生变化")
        if total != expected_total:
            raise XMLParseError(f"ZIP 记录数异常：校验 {expected_total} 条，提取 {total} 条")
        logger.info("解析完成，共 %s 条记录", total)
