import importlib
import struct
import sys
import unittest
from unittest.mock import patch

from x0z import digitone_machine as machine


class DigitoneMachineTests(unittest.TestCase):
    def case(self):
        expected = [2402, 2402, 32512, 3, 2, 1, 3, 60 << 16, 37, 1]
        return dict(slot=3, expected=expected, seen=list(expected), model=16384,
                    final_model=16384, output=[2402] * 32, target=12345)

    def test_native_fraction_and_companion_metadata(self):
        machine.validate_case(self.case())

    def test_targets_wrong_metadata_model_and_extent_are_rejected(self):
        for change in (dict(seen=[12345] * 10), dict(model=0), dict(output=[2402] * 33),
                       dict(slot=8), dict(target=2402)):
            case = self.case(); case.update(change)
            with self.subTest(change=change), self.assertRaises(AssertionError):
                machine.validate_case(case)
        for index in range(10):
            case = self.case(); case["seen"][index] += 1
            with self.subTest(index=index), self.assertRaises(AssertionError):
                machine.validate_case(case)

    def test_booleans_cannot_replace_native_words(self):
        case = self.case(); case["seen"][-1] = True
        with self.assertRaises(AssertionError):
            machine.validate_case(case)

    def edit(self):
        before, kit_before = bytes([0xa5]) * 0xa40, bytes([0x5a]) * (0x2c + 4 * 326)
        after, kit_after = bytearray(before), bytearray(kit_before)
        for lane in (2, 6):
            struct.pack_into(">h", after, 18 + 158 * lane + 54, 20001)
        struct.pack_into(">h", kit_after, 0x2c + 326 * 2 + 54, 20001)
        return before, after, kit_before, kit_after, [0, 1, 2, 3, 0, 1, 2, 3]

    def test_live_edit_updates_only_its_kit_word_and_two_track_voices(self):
        machine.validate_live_edit(*self.edit())

    def test_missing_live_store_wrong_track_and_adjacent_writes_fail(self):
        before, after, kit_before, kit_after, tracks = self.edit()
        for target, kit in ((before, kit_after), (after, kit_before)):
            with self.assertRaises(AssertionError):
                machine.validate_live_edit(before, target, kit_before, kit, tracks)
        for offset in (18 + 158 + 54, 18 + 158 * 2 + 56, 18 + 158 * 2):
            wrong = bytearray(after)
            wrong[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(AssertionError):
                machine.validate_live_edit(before, wrong, kit_before, kit_after, tracks)

    def test_host_import_requires_no_firmware_or_emulator(self):
        with patch.dict(sys.modules, {"elekloader": None, "emu": None, "unicorn": None}):
            importlib.reload(machine)


if __name__ == "__main__":
    unittest.main()
