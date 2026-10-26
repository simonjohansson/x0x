"""Selector fixture/trace checks require no emulator or target toolchain."""
import unittest

from x0z.sharc_selector import cases, parse_reference, raw_words
from x0z import sharc_callback as callback


class SelectorTraceTests(unittest.TestCase):
    def test_raw_bad_words_reach_the_emulator_fixture(self):
        inputs = cases()
        invalid = next(row for row in inputs if row["label"] == "invalid-parameter-15-5-4294967295")
        words = raw_words(invalid)
        self.assertEqual(words[callback.INPUT + 4], 15)
        self.assertEqual(words[callback.PARAM + 5 * 4], 0xffffffff)
        self.assertEqual(words[callback.PARAM + 3 * 4], 0xffffffff)
        self.assertEqual(words[callback.PARAM + 4 * 4], 0xffffffff)
        null = next(row for row in inputs if row["label"] == "invalid-params_present-False")
        self.assertEqual(raw_words(null)[callback.INPUT + 16], 0)

    def test_every_slot_exercises_both_sides_of_the_threshold(self):
        inputs = cases()
        for slot in range(16):
            thresholds = {row["params"][5] for row in inputs
                          if row["slot"] == slot and row["label"].startswith("threshold-")}
            self.assertEqual(thresholds, {0, 16383, 16384, 32512})
            inactive = next(row for row in inputs if row["label"] == f"inactive-{slot}")
            self.assertEqual(inactive["flags"], 0)
        self.assertEqual(len({row["label"] for row in inputs}), len(inputs))

    def test_truncated_extra_or_corrupt_c_rows_cannot_pass(self):
        words = [1, 1, 3, 1, 0, 1, 12345] + [0, 0] * 16
        text = " ".join(map(str, words))
        self.assertEqual(parse_reference(text, 1)[0]["numerator"], 12345)
        for changed, count in ((text, 2), (text + "\n" + text, 1),
                               (" ".join(map(str, words[:-1])), 1)):
            with self.assertRaises(ValueError):
                parse_reference(changed, count)
        for index, value in ((0, 2), (2, 4), (8, 3), (7, -1)):
            corrupt = words.copy()
            corrupt[index] = value
            with self.subTest(index=index), self.assertRaises(ValueError):
                parse_reference(" ".join(map(str, corrupt)), 1)


if __name__ == "__main__":
    unittest.main()
