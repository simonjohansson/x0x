import copy
import hashlib
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from elekloader import formats
from x0x import firmware, cpu
from x0x.firmware import ROOT, load_json


class LatestFirmwareTests(unittest.TestCase):
    def test_dirty_dependency_is_rejected_even_at_the_expected_revision(self):
        with patch.object(cpu, 'command', return_value=' M sdk/build.py'):
            with self.assertRaisesRegex(ValueError, 'Modified dependency'):
                firmware.baseline()

    def test_input_hashes_follow_source_edits_not_just_commit_ids(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(cpu, 'ROOT', Path(tmp)):
            root = Path(tmp)
            (root/'firmware').mkdir()
            (root/'firmware/manifest.json').write_text('{}')
            (root/'mise.toml').write_text('')
            (root/'machines').mkdir()
            source = root/'machines/adapter.c'
            source.write_text('old')
            before = cpu.source_hashes()
            source.write_text('new')
            after = cpu.source_hashes()
            self.assertNotEqual(before['machines/adapter.c'], after['machines/adapter.c'])
            self.assertEqual(before['firmware/manifest.json'], after['firmware/manifest.json'])

    def test_wrong_sdk_pin_and_duplicate_device_baseline_are_rejected(self):
        manifest = load_json(ROOT / "firmware/manifest.json")
        changed = copy.deepcopy(manifest)
        changed["elekloader_revision"] = "wrong"
        with patch.object(firmware, "load_json", return_value=changed):
            with self.assertRaisesRegex(ValueError, "pin"):
                firmware.baseline()
        changed = copy.deepcopy(manifest)
        changed["entries"][1] = changed["entries"][0]
        with patch.object(firmware, "load_json", return_value=changed):
            with self.assertRaisesRegex(ValueError, "exactly one"):
                firmware.baseline()

    def test_changed_image_cannot_reach_the_sdk_builder(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stock.syx"
            path.write_bytes(b"changed")
            entry = dict(image=dict(path=path.name, bytes=7, sha256="wrong"))
            with self.assertRaisesRegex(ValueError, "latest-only"):
                firmware.verify_entry(entry, Path(directory), "test-sdk")

    def test_an_older_release_is_not_a_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stock.syx"
            raw = b"synthetic input for the version-policy test"
            path.write_bytes(raw)
            entry = dict(device="digitakt-mk1", version="1.54",
                         image=dict(path=path.name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
            with patch.object(formats, "load", return_value=(None, SimpleNamespace(key="digitakt-mk1"), SimpleNamespace(version="1.53"))):
                with self.assertRaisesRegex(ValueError, "device/version"):
                    firmware.verify_entry(entry, Path(directory), "test-sdk")


if __name__ == "__main__":
    unittest.main()
