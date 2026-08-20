import sys
import tempfile
import unittest
import zipfile
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from parser import XMLParseError, parse_zip_file


def _xml(record_key="key-1", body="<cpms>plain</cpms>"):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<udid><header><numberRkeyecordXML>1</numberRkeyecordXML></header>"
        f"<devices><device>{body}<deviceRecordKey>{record_key}</deviceRecordKey></device></devices>"
        "</udid>"
    )


class ParserTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

    def _write_zip(self, members, name="data.zip"):
        path = Path(self.temp_dir.name, name)
        with zipfile.ZipFile(path, "w") as archive:
            for name, content in members.items():
                archive.writestr(name, content)
        return path

    @staticmethod
    def _zip_bytes(members):
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for name, content in members.items():
                archive.writestr(name, content)
        return buffer.getvalue()

    def test_removes_only_xml_invalid_characters_and_preserves_entities(self):
        body = "<cpms>A & B&#10;C\x01D</cpms>"
        path = self._write_zip({"UDID_FULL_DOWNLOAD_PART1.xml": _xml(body=body)})

        records = list(parse_zip_file(str(path)))

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["cpms"], "A & B\nCD")

    def test_validates_all_members_before_emitting_records(self):
        malformed = (
            "<udid><header><numberRkeyecordXML>1</numberRkeyecordXML></header>"
            "<devices><device>"
        )
        path = self._write_zip(
            {
                "UDID_FULL_DOWNLOAD_PART1.xml": _xml(),
                "UDID_FULL_DOWNLOAD_PART2.xml": malformed,
            }
        )
        records = parse_zip_file(str(path))

        with self.assertRaises(XMLParseError):
            next(records)

    def test_parses_xml_from_nested_daily_zip_files_in_name_order(self):
        day_10 = self._zip_bytes(
            {"UDID_INCREMENTAL_DOWNLOAD_PART1_Of_1_2026-08-10.xml": _xml("day-10")}
        )
        day_11 = self._zip_bytes(
            {"UDID_INCREMENTAL_DOWNLOAD_PART1_Of_1_2026-08-11.xml": _xml("day-11")}
        )
        path = self._write_zip(
            {
                "UDID_DAY_UPDATE_20260811.zip": day_11,
                "UDID_DAY_UPDATE_20260810.zip": day_10,
            }
        )

        records = list(parse_zip_file(str(path)))

        self.assertEqual([record["deviceRecordKey"] for record in records], ["day-10", "day-11"])

    def test_parses_xml_from_monthly_weekly_daily_nested_zip(self):
        daily_zip = self._zip_bytes({"device.xml": _xml("nested")})
        weekly_zip = self._zip_bytes({"UDID_DAY_UPDATE_20260810.zip": daily_zip})
        path = self._write_zip(
            {"UDID_WEEKLY_UPDATE_20260810_20260816.zip": weekly_zip},
            name="UDID_MONTHLY_UPDATE_20260801_20260831.zip",
        )

        records = list(parse_zip_file(str(path)))

        self.assertEqual([record["deviceRecordKey"] for record in records], ["nested"])

    def test_invalid_nested_zip_prevents_records_from_being_emitted(self):
        path = self._write_zip(
            {
                "device.xml": _xml("valid"),
                "nested.zip": b"not a ZIP archive",
            }
        )
        records = parse_zip_file(str(path))

        with self.assertRaisesRegex(XMLParseError, "无法打开嵌套 ZIP"):
            next(records)


if __name__ == "__main__":
    unittest.main()
