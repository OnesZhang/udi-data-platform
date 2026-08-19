import io
import os
import tempfile
import unittest
import zipfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from config import Config
from downloader import download_feed
from file_store import is_complete_zip, list_ready_files
from importer import _accepted_records
from parser import parse_zip_file


def official_xml(key: str, text: str, invalid: bool = False) -> str:
    if invalid:
        text = text.replace("-", "\x02", 1)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<udid><header frequency=\"daily\" type=\"DAILY\"/>"
        "<devices><device>"
        f"<deviceRecordKey>{key}</deviceRecordKey>"
        f"<cpmctymc>{text}</cpmctymc>"
        "<packingList><packing><bzcpbs>P1</bzcpbs></packing></packingList>"
        "</device></devices></udid>"
    )


class FakeResponse:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        yield self.content

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.env = patch.dict(
            os.environ,
            {
                "INBOX_DIR": str(root / "inbox"),
                "ARCHIVE_DIR": str(root / "archive"),
                "FAILED_DIR": str(root / "failed"),
            },
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp_dir.cleanup()

    def test_parser_removes_invalid_control_character_and_reads_nested_list(self):
        archive_path = Path(self.temp_dir.name) / "sample.zip"
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr("part2.xml", official_xml("B", "second"))
            archive.writestr("part1.xml", official_xml("A", "first-invalid", invalid=True))

        records = list(parse_zip_file(str(archive_path)))
        self.assertEqual([record["deviceRecordKey"] for record in records], ["A", "B"])
        self.assertEqual(records[0]["packing_list"][0]["bzcpbs"], "P1")

    def test_complete_zip_is_seen_by_inbox_scanner(self):
        archive_path = Path(self.temp_dir.name) / "sample.zip"
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr("part1.xml", official_xml("A", "normal"))
        config = Config(require_database=False)
        archive_path.replace(config.inbox_dir / "sample.zip")
        self.assertTrue(is_complete_zip(config.inbox_dir / "sample.zip"))
        self.assertEqual([path.name for path in list_ready_files(config)], ["sample.zip"])

    def test_downloader_writes_complete_zip_and_skips_same_name(self):
        binary_zip = io.BytesIO()
        with zipfile.ZipFile(binary_zip, "w") as archive:
            archive.writestr("part1.xml", official_xml("A", "normal"))
        rss = (
            b"<?xml version=\"1.0\"?><rss><channel><item>"
            b"<title>UDID_DAILY_TEST.zip</title>"
            b"<link>https://example.test/file.zip</link>"
            b"</item></channel></rss>"
        )
        config = Config(require_database=False)

        with patch(
            "downloader.requests.get",
            side_effect=[FakeResponse(rss), FakeResponse(binary_zip.getvalue())],
        ):
            result = download_feed(config, "https://example.test/rss", "daily")
        self.assertEqual(result, ["UDID_DAILY_TEST.zip"])
        self.assertTrue((config.inbox_dir / "UDID_DAILY_TEST.zip").is_file())

        with patch("downloader.requests.get", return_value=FakeResponse(rss)) as get:
            self.assertEqual(download_feed(config, "https://example.test/rss", "daily"), [])
        self.assertEqual(get.call_count, 1)

    def test_version_cache_only_accepts_newer_record(self):
        existing = {"A": (2, 0, datetime(2026, 8, 1), None)}
        records = [
            {"deviceRecordKey": "A", "versionNumber": "1", "correctionNumber": "9"},
            {"deviceRecordKey": "B", "versionNumber": "1", "correctionNumber": "0"},
            {"deviceRecordKey": "A", "versionNumber": "3", "correctionNumber": "0"},
        ]
        accepted = _accepted_records(None, records, existing)
        self.assertEqual(
            [(record["deviceRecordKey"], record["versionNumber"]) for record in accepted],
            [("A", "3"), ("B", "1")],
        )


if __name__ == "__main__":
    unittest.main()
