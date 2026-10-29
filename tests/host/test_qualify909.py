"""Qualification rejects invalid output instead of issuing a passing receipt."""
import unittest

import numpy as np
from x0x import qualify909


class QualificationTests(unittest.TestCase):
    def test_port_gate_rejects_nonfinite_or_excessive_error(self):
        expected = np.ones(96000)
        self.assertEqual(qualify909.port_error(expected, expected), 0)
        for bad in (float('nan'), float('inf'), -float('inf')):
            actual = expected.copy()
            actual[100] = bad
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    qualify909.port_error(actual, expected)
                with self.assertRaises(ValueError):
                    qualify909.port_error(expected, actual)
                with self.assertRaises(ValueError):
                    qualify909.measure(actual, expected)
        with self.assertRaises(AssertionError):
            qualify909.port_error(expected + .001, expected)
