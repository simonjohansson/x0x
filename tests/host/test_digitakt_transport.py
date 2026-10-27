import struct
import unittest

from x0x.digitakt_transport import GUARDS, decode_record


class DigitaktTransportRecordTests(unittest.TestCase):
    def record(self):
        observation = struct.pack(">4IiI2i3I32i", 1, 1, 7, 1, -65536, 32512,
                                  -1, -2, 1, 12345, 32512, *([12345 << 16] * 32))
        return struct.pack(">2I", 153, GUARDS[0]) + observation + struct.pack(">I", GUARDS[1])

    def test_signed_native_metadata_and_fraction_survive(self):
        record = decode_record(self.record())
        self.assertEqual((record["block"], record["track"], record["note"]), (153, 7, -65536))
        self.assertEqual((record["amp_phase"], record["amp_level"]), (-1, -2))
        self.assertEqual(record["numerator"], 12345)

    def test_truncated_extended_or_corrupt_guards_are_rejected(self):
        raw = self.record()
        for changed in (raw[:-1], raw + b"\0"):
            with self.assertRaises(ValueError):
                decode_record(changed)
        for offset in (4, len(raw) - 1):
            changed = bytearray(raw)
            changed[offset] ^= 1
            with self.assertRaises(AssertionError):
                decode_record(changed)


if __name__ == "__main__":
    unittest.main()
