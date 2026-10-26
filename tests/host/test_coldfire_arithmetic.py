"""Independent arithmetic expectations; importing these tests needs no emulator."""
import contextlib
import io
import json
import unittest
from unittest.mock import patch

from x0z import coldfire_arithmetic as arithmetic
from x0z.cpu import Unavailable


class FixedPointReferenceTests(unittest.TestCase):
    def test_signed_nearest_even_and_truncation(self):
        for numerator, expected in [(1, 0), (3, 2), (5, 2), (-1, 0), (-3, -2), (-5, -2)]:
            with self.subTest(numerator=numerator):
                self.assertEqual(arithmetic.rounded_shift(numerator, 1, True), expected)
                self.assertEqual(arithmetic.rounded_shift(numerator, 1, False), numerator // 2)

    def test_explicit_manual_arithmetic_vectors(self):
        for name, state, excitation, coefficient, level, mode, expected_state in arithmetic.CASES:
            with self.subTest(name=name):
                self.assertEqual(arithmetic.reference_step(state, excitation, coefficient, level, mode)[0], expected_state)

    def test_saturated_edges_and_output_gain(self):
        minimum, maximum, half = arithmetic.MINIMUM, arithmetic.MAXIMUM, arithmetic.HALF
        self.assertEqual(arithmetic.reference_step(minimum, minimum, maximum, half), (minimum, -half))
        self.assertEqual(arithmetic.reference_step(minimum, 0, minimum, half), (maximum, half))
        self.assertEqual(arithmetic.reference_step(half, 0, half, half), (1 << 29, 1 << 28))

    def test_long_positive_tail_rounds_to_quiescence(self):
        state = arithmetic.HALF
        for _ in range(32):
            state, _ = arithmetic.reference_step(state, 0, arithmetic.HALF, arithmetic.HALF)
        self.assertEqual(state, 0)
        state, _ = arithmetic.reference_step(-1, 0, arithmetic.HALF, arithmetic.HALF, arithmetic.TRUNCATE)
        self.assertEqual(state, -1)  # The documented truncating one-LSB limit cycle.

    def test_invalid_private_words_and_modes_fail(self):
        for state in [True, 0.5, 1 << 31, -(1 << 31) - 1]:
            with self.subTest(state=state), self.assertRaises(ValueError):
                arithmetic.reference_step(state, 0, arithmetic.HALF, arithmetic.HALF)
        for mode in [0, 160.0, True]:
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                arithmetic.reference_step(0, 0, arithmetic.HALF, arithmetic.HALF, mode)

    def test_unavailable_emulator_is_not_a_passing_command(self):
        output = io.StringIO()
        with patch.object(arithmetic, "diagnose", side_effect=Unavailable("emulator missing")):
            with contextlib.redirect_stdout(output):
                self.assertEqual(arithmetic.main([]), 77)
        self.assertEqual(json.loads(output.getvalue())["status"], "unavailable")

    def test_bad_instruction_evidence_is_a_failure(self):
        output = io.StringIO()
        with patch.object(arithmetic, "diagnose", side_effect=AssertionError("EMAC context")):
            with contextlib.redirect_stdout(output):
                self.assertEqual(arithmetic.main([]), 1)
        self.assertEqual(json.loads(output.getvalue())["status"], "failed")


if __name__ == "__main__":
    unittest.main()
