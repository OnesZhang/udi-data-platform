import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from inbox_worker import InboxWorker


class Clock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value


class InboxWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.clock = Clock()
        self.config = SimpleNamespace(
            inbox_dir=self.temp_dir.name,
        )
        self.import_calls = []

    def _write_zip(self, name="device.zip"):
        path = Path(self.temp_dir.name, name)
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("device.xml", "<root />")
        return path

    def _worker(self, importer=None):
        return InboxWorker(
            self.config,
            clock=self.clock,
            parser=lambda path: iter(()),
            importer=importer or self._successful_import,
        )

    def _successful_import(self, config, file_name, records):
        self.import_calls.append(file_name)
        return {
            "status": "completed",
            "total_records": 1,
            "success_records": 1,
            "failed_records": 0,
        }

    def test_waits_for_stable_zip_then_imports_and_deletes_it(self):
        zip_path = self._write_zip()
        worker = self._worker()

        self.assertEqual(worker.process_ready_files(), 0)
        self.assertEqual(self.import_calls, [])

        self.clock.value = 59
        self.assertEqual(worker.process_ready_files(), 0)
        self.assertTrue(zip_path.exists())

        self.clock.value = 60
        self.assertEqual(worker.process_ready_files(), 1)
        self.assertEqual(self.import_calls, ["device.zip"])
        self.assertFalse(zip_path.exists())

    def test_incomplete_zip_is_left_untouched(self):
        zip_path = Path(self.temp_dir.name, "uploading.zip")
        zip_path.write_bytes(b"not a zip archive")
        worker = self._worker()

        worker.process_ready_files()
        self.clock.value = 60
        self.assertEqual(worker.process_ready_files(), 0)
        self.assertEqual(self.import_calls, [])
        self.assertTrue(zip_path.exists())

    def test_changed_file_is_not_deleted_after_import(self):
        zip_path = self._write_zip()

        def changing_importer(config, file_name, records):
            with zipfile.ZipFile(zip_path, "a") as archive:
                archive.writestr("new-device.xml", "<root />")
            return {"status": "completed", "failed_records": 0}

        worker = self._worker(importer=changing_importer)
        worker.process_ready_files()
        self.clock.value = 60

        self.assertEqual(worker.process_ready_files(), 0)
        self.assertTrue(zip_path.exists())

    def test_deletes_file_after_row_level_errors_are_recorded(self):
        zip_path = self._write_zip("partial.zip")

        def partially_completed_import(config, file_name, records):
            return {
                "status": "completed_with_errors",
                "total_records": 10,
                "success_records": 9,
                "failed_records": 1,
            }

        worker = self._worker(importer=partially_completed_import)
        worker.process_ready_files()
        self.clock.value = 60

        self.assertEqual(worker.process_ready_files(), 1)
        self.assertFalse(zip_path.exists())


if __name__ == "__main__":
    unittest.main()
