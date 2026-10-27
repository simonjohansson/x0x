"""Host adapter-report decoding imports no emulator or stock image."""
import struct
import unittest

from x0x.digitakt_adapter import decode_observation


class DigitaktAdapterReportTests(unittest.TestCase):
    def test_signed_native_metadata_and_fraction_are_retained(self):
        raw = struct.pack(">4IiI2i3I32i", 1, 1, 7, 1, -123, 12345, -7, -0x1234567,
                          1, 16257, 32512, *([-0x1234567] * 32))
        result = decode_observation(raw)
        self.assertEqual((result["track"], result["note"], result["velocity"]), (7, -123, 12345))
        self.assertEqual((result["amp_phase"], result["amp_level"]), (-7, -0x1234567))
        self.assertEqual((result["numerator"], result["denominator"]), (16257, 32512))
        self.assertEqual(result["output_q31"], [-0x1234567] * 32)

    def test_truncated_or_overlong_observations_fail(self):
        for size in (0, 171, 173):
            with self.subTest(size=size), self.assertRaises(ValueError):
                decode_observation(bytes(size))


if __name__ == "__main__":
    unittest.main()
