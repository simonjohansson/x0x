"""Host validation does not import or require either emulator."""
import unittest

from x0x.sharc_callback import input_words, negative_immediate_shifts, validate_layout


class CallbackFixtureTests(unittest.TestCase):
    def test_slot_and_delivered_value_boundaries(self):
        for slot in [0, 15]:
            self.assertEqual(len(input_words(slot, 0xFFFF, 1, [32512] * 40)), 84)
        for slot in [-1, 16, True]:
            with self.assertRaises(ValueError):
                input_words(slot, 0, 0, [0] * 40)
        for params in [[0] * 39, [32513] * 40, [True] * 40]:
            with self.assertRaises(ValueError):
                input_words(0, 0, 0, params)
        for pitch, flags in [(-1, 0), (0x10000, 0), (True, 0), (0, 2), (0, True)]:
            with self.assertRaises(ValueError):
                input_words(0, pitch, flags, [0] * 40)

    def test_type6b_shift_sign_extension_has_an_independent_check(self):
        good = bytes.fromhex("3e0200002210 3e02007822f0")
        bad = bytes.fromhex("3e02000022f0")
        self.assertEqual(negative_immediate_shifts(good), [])
        self.assertEqual(negative_immediate_shifts(bad), [0])

    def test_callback_layout_tracks_private_bounds_and_read_ahead_guard(self):
        layout = dict(code_pc16=0xBC8400, code_bytes=8192,
                      data_address=0x20092800, data_bytes=5120)
        validate_layout(layout, bytes(8128), 0xBC8400)
        for change, size, entry in [({}, 8130, 0xBC8400), ({}, 10, 0xBC8401),
                                    ({"data_address": 0x20092804}, 10, 0xBC8400),
                                    ({"data_bytes": 124}, 10, 0xBC8400)]:
            with self.subTest(change=change, size=size, entry=entry), self.assertRaises(AssertionError):
                validate_layout({**layout, **change}, bytes(size), entry)


if __name__ == "__main__":
    unittest.main()
