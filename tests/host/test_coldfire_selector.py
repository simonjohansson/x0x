"""Literal selector policy expectations, with no emulator/assembler imports."""
import contextlib
import io
import json
import unittest
from unittest.mock import patch

from x0z import coldfire_selector as selector
from x0z.cpu import Unavailable


def bank():
    return [(0, 99, 100 + lane) for lane in range(8)]


class SelectorReferenceTests(unittest.TestCase):
    def test_first_delivery_waits_until_trigger_then_initializes_one_lane(self):
        initial = bank()
        status, state, notice = selector.reference_step(initial, 3, 32512, 0, 1)
        self.assertEqual((status, state, notice), (selector.WAIT, initial, None))
        status, state, notice = selector.reference_step(initial, 3, 32512, 1, 1)
        self.assertEqual((status, state[3], notice), (selector.APPLY, (1, 1, 0), (1, 1, 0, 1)))
        self.assertEqual(state[:3] + state[4:], initial[:3] + initial[4:])
        self.assertEqual(initial, bank())

    def test_threshold_and_fractional_values_have_explicit_results(self):
        for raw, model in [(0, 0), (1, 0), (128, 0), (16383, 0), (16384, 1), (32512, 1)]:
            with self.subTest(raw=raw):
                status, state, notice = selector.reference_step(bank(), 7, raw, 1, 1)
                self.assertEqual((status, state[7], notice),
                                 (selector.APPLY, (1, model, 0), (model, 1, 0, 1)))

    def test_pending_model_waits_and_same_model_retrigger_keeps_tail(self):
        initial = [(1, lane % 2, 0xfedcba98 + lane) for lane in range(8)]
        status, state, notice = selector.reference_step(initial, 4, 32512, 0, 1)
        self.assertEqual((status, state, notice), (selector.APPLY, initial, (0, 0, 0, 0)))
        status, state, notice = selector.reference_step(initial, 4, 16383, 1, 1)
        self.assertEqual((status, state, notice), (selector.APPLY, initial, (0, 0, 0, 0)))
        status, state, notice = selector.reference_step(initial, 4, 16384, 1, 1)
        self.assertEqual((status, state[4], notice), (selector.APPLY, (1, 1, 0), (1, 0, 1, 1)))
        self.assertEqual(state[:4] + state[5:], initial[:4] + initial[5:])

    def test_invalid_and_caller_classified_missing_or_stale_are_atomic(self):
        initial = [(1, lane % 2, lane + 10) for lane in range(8)]
        for lane, raw, trigger, delivery, expected in [
            (-1, 0, 1, 1, selector.INVALID), (8, 0, 1, 1, selector.INVALID),
            (0, -1, 1, 1, selector.INVALID), (0, 32513, 1, 1, selector.INVALID),
            (0, 0, 2, 1, selector.INVALID), (0, 0, 1, 3, selector.INVALID),
            (0, 0, 1, 0, selector.MISSING), (0, 32512, 1, 2, selector.STALE),
        ]:
            with self.subTest(lane=lane, raw=raw, trigger=trigger, delivery=delivery):
                self.assertEqual(selector.reference_step(initial, lane, raw, trigger, delivery),
                                 (expected, initial, None))
        for corrupt in [(2, 0, 10), (1, 2, 10)]:
            initial[0] = corrupt
            self.assertEqual(selector.reference_step(initial, 0, 0, 1, 1),
                             (selector.INVALID, initial, None))

    def test_non_word_host_inputs_are_not_silently_encoded(self):
        for raw in [True, .5, None, 1 << 32]:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                selector.reference_step(bank(), 0, raw, 1, 1)
        with self.assertRaises(ValueError):
            selector.reference_step(bank()[:7], 0, 0, 1, 1)
        malformed = bank()
        malformed[0] = (0, 0, -1)
        with self.assertRaises(ValueError):
            selector.reference_step(malformed, 0, 0, 1, 1)

    def test_missing_emulator_and_failed_instruction_checks_are_not_green(self):
        for error, code, status in [(Unavailable("emulator missing"), 77, "unavailable"),
                                    (AssertionError("wrong lane"), 1, "failed")]:
            output = io.StringIO()
            with patch.object(selector, "diagnose", side_effect=error), contextlib.redirect_stdout(output):
                self.assertEqual(selector.main([]), code)
            self.assertEqual(json.loads(output.getvalue())["status"], status)


if __name__ == "__main__":
    unittest.main()
