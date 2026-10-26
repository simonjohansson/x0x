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

    def lock(self, apply):
        target, bits, smooth, kit = bytes(0xa40), bytes(8 * 12), bytes(720 * 4), bytes(0x2c + 4 * 326)
        if not apply:
            marked = bytearray(bits)
            struct.pack_into(">I", marked, 12 * machine.LOCK_VOICE, 1 << machine.LOCK_SLOT)
            bits = bytes(marked)
        after, bits_after, smooth_after = bytearray(target), bytearray(bits), bytearray(smooth)
        value = machine.LOCK_VALUE if apply else machine.RESTORE_VALUE
        struct.pack_into(">h", after, 18 + 158 * machine.LOCK_VOICE + 2 * machine.LOCK_SLOT, value)
        struct.pack_into(">I", bits_after, 12 * machine.LOCK_VOICE, (1 << machine.LOCK_SLOT) if apply else 0)
        struct.pack_into(">I", smooth_after, 4 * (9 + 79 * machine.LOCK_VOICE + machine.LOCK_SLOT), value << 16)
        return [target, after, bits, bits_after, smooth, smooth_after, kit, kit, apply]

    def test_native_lock_apply_and_restore_change_only_one_lane(self):
        for apply in (True, False):
            with self.subTest(apply=apply):
                machine.validate_lock_transition(*self.lock(apply))

    def test_lock_omission_wrong_lane_and_kit_write_are_rejected(self):
        for apply in (True, False):
            for after_index in (1, 3, 5):
                args = self.lock(apply)
                args[after_index] = args[after_index - 1]
                with self.subTest(apply=apply, missing=after_index), self.assertRaises(AssertionError):
                    machine.validate_lock_transition(*args)
            args = self.lock(apply)
            wrong = bytearray(args[1]); wrong[18 + 158 * 2 + 2 * machine.LOCK_SLOT] ^= 1
            args[1] = wrong
            with self.subTest(apply=apply, wrong_lane=True), self.assertRaises(AssertionError):
                machine.validate_lock_transition(*args)
            args = self.lock(apply)
            changed = bytearray(args[7]); changed[0] = 1; args[7] = changed
            with self.subTest(apply=apply, kit_write=True), self.assertRaises(AssertionError):
                machine.validate_lock_transition(*args)

    def test_host_import_requires_no_firmware_or_emulator(self):
        with patch.dict(sys.modules, {"elekloader": None, "emu": None, "unicorn": None}):
            importlib.reload(machine)


if __name__ == "__main__":
    unittest.main()
