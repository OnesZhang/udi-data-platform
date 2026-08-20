import sys
import tempfile
import unittest
import zipfile
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

    def _write_zip(self, members):
        path = Path(self.temp_dir.name, "data.zip")
        with zipfile.ZipFile(path, "w") as archive:
            for name, content in members.items():
                archive.writestr(name, content)
        return path

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


if __name__ == "__main__":
    unittest.main()
