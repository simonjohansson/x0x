import math
import unittest

from x0x import body808, retrigger808 as retrigger


class Retrigger808Tests(unittest.TestCase):
    def test_polarity_capacitor_charge_and_both_envelope_edges(self):
        self.assertAlmostEqual(retrigger.TAU, .033)
        fall = body808.ATTACK_SAMPLES
        actual = retrigger.reference(48000)
        self.assertEqual(actual[0], .71)
        before = .71 * math.exp(-fall / (48000*.033))
        self.assertAlmostEqual(actual[fall-1], .71*math.exp(-(fall-1)/(48000*.033)), places=12)
        # The charged capacitor makes a large negative companion pulse, not a positive clip.
        self.assertAlmostEqual(actual[fall], before-15, places=12)
        self.assertLess(actual[fall], -14)
        for n in (fall+1, 2400, 4800, 23999):
            expected = (before-15) * math.exp(-(n-fall)/(48000*.033))
            self.assertAlmostEqual(actual[n], expected, places=12)
        self.assertLess(abs(actual[-1]), 1e-10)
        self.assertLessEqual(max(actual), .71)

    def test_unclipped_small_signal_has_the_linear_highpass_response(self):
        actual = retrigger.filter_reference([.25]*100 + [0.0]*200)
        for n, value in enumerate(actual):
            expected = .25*math.exp(-n/(48000*.033))
            if n >= 100:
                expected -= .25*math.exp(-(n-100)/(48000*.033))
            self.assertAlmostEqual(value, expected, places=13)

    def test_rate_change_preserves_physical_edge_times_and_RC_decay(self):
        a = retrigger.filter_reference([15.0]*288 + [0.0]*4512, 48000)
        b = retrigger.filter_reference([15.0]*576 + [0.0]*9024, 96000)
        self.assertLess(max(abs(x-y) for x,y in zip(a,b[::2])), 1e-11)

    def test_a_later_small_trigger_retains_charge_history(self):
        first = [.25]*100 + [0.0]*100
        combined = retrigger.filter_reference(first + [.25]*32)
        fresh = retrigger.filter_reference([.25]*32)
        self.assertNotEqual(combined[200:], fresh)
        expected = fresh[0] + retrigger.filter_reference(first+[0.0])[200]
        self.assertAlmostEqual(combined[200], expected, places=13)

    def test_invalid_inputs_do_not_become_valid_reference_samples(self):
        for rate in (0, -1, True, 48000.5):
            with self.assertRaises(ValueError): retrigger.filter_reference([0],rate)
        for sample in (float('nan'),float('inf'),-float('inf')):
            with self.assertRaises(ValueError): retrigger.filter_reference([0,sample])
        for frames in (-1,True,32.5):
            with self.assertRaises(ValueError): retrigger.reference(frames)
