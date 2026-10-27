"""Host checks of diagnostic boundaries; real instruction runs are separate tasks."""
import contextlib
import io
import json
import struct
import unittest
from unittest.mock import patch

from x0x import cpu


class DiagnosticBoundaryTests(unittest.TestCase):
    def test_missing_assembler_is_unavailable(self):
        with patch.object(cpu.shutil, "which", return_value=None):
            with self.assertRaises(cpu.Unavailable):
                cpu.require_program("missing-assembler")

    def test_unavailable_is_not_a_passing_cli(self):
        output = io.StringIO()
        with patch.object(cpu, "diagnose", side_effect=cpu.Unavailable("not installed")):
            with contextlib.redirect_stdout(output):
                code = cpu.main(["coldfire"])
        self.assertEqual(code, 77)
        self.assertEqual(json.loads(output.getvalue())["status"], "unavailable")

    def test_failed_instruction_check_is_not_unavailable(self):
        with patch.object(cpu, "diagnose", side_effect=AssertionError("guard corruption")):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cpu.main(["sharc"]), 1)

    def test_truncated_or_wrong_elf_is_rejected(self):
        for data in (b"", b"\x7fELF", bytes(52)):
            with self.subTest(size=len(data)), self.assertRaises(ValueError):
                cpu.sharc_code(data)

    def test_own_section_is_extracted_with_loader_parcel_order(self):
        header = struct.pack("<16sHHIIIIIHHHHHH", b"\x7fELF\x01\x01\x01" + bytes(9),
                             2, 0x85, 1, 0xBC8400, 0, 52, 0, 52, 0, 0, 40, 2, 0)
        null = bytes(40)
        section = struct.pack("<10I", 0, 1, 7, 0xBC8400, 132, 4, 0, 0, 2, 0)
        code, entry = cpu.sharc_code(header + null + section + bytes.fromhex("c204c002"))
        self.assertEqual(code, bytes.fromhex("04c202c0"))
        self.assertEqual(entry, 0xBC8400)
        with self.assertRaisesRegex(ValueError, "section"):
            cpu.sharc_code(header + null + section + b"\xc2")


if __name__ == "__main__":
    unittest.main()
