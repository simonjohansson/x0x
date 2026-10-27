"""Reference archives must be available and verified before their code is built."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from x0x import cpu, plaits_reference


class ReferenceArchiveTests(unittest.TestCase):
    def test_missing_and_modified_archive_never_reach_compiler(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            research = root / "research"
            research.mkdir()
            (research / "manifest.json").write_text(json.dumps([
                dict(id=sid, path=sid+".tar.gz", sha256="0"*64) for sid in ("S47","S48")
            ]))
            with patch.object(plaits_reference,"ROOT",root), patch.object(cpu,"command") as command:
                with self.assertRaises(cpu.Unavailable):
                    plaits_reference.run()
                (research / "S47.tar.gz").write_bytes(b"modified source")
                with self.assertRaisesRegex(ValueError,"archive hash mismatch"):
                    plaits_reference.run()
                command.assert_not_called()
