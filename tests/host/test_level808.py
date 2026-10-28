import math
import unittest

from x0x import level808


class Level808Tests(unittest.TestCase):
    def test_scheduled_windows_keep_distinct_attack_body_and_tail_levels(self):
        samples = [.125] * 1200 + [.25] * 6000 + [.0625] * 16800
        self.assertEqual(level808.levels(samples),
                         dict(peak=.25, attack=.125, body=.25, tail_body=.0625))

    def test_known_common_gain_is_recovered_without_individual_factors(self):
        target = 1.5
        errors = [level808.error_db(x, target * x) for x in (.01, .1, .2)]
        self.assertEqual(level808.fit_factor(errors, .2), target)
        self.assertAlmostEqual(level808.error_db(2, 1), 6.020599913279624)

    def test_incompatible_envelopes_cannot_be_passed_by_one_gain(self):
        errors = [-8., 4.]
        gain = level808.fit_factor(errors, .2)
        adjusted = [x + 20 * math.log10(gain) for x in errors]
        self.assertTrue(any(abs(x) > level808.LIMIT_DB for x in adjusted))
        self.assertAlmostEqual(sum(adjusted), 0., places=5)

    def test_headroom_caps_the_factor_without_clipping(self):
        gain = level808.fit_factor([-12.], .4)
        self.assertLess(gain * .4, .5)

    def test_silence_is_unresolved_and_invalid_input_is_rejected(self):
        self.assertIsNone(level808.error_db(0., .1))
        self.assertIsNone(level808.error_db(0., 0.))
        for bad in (-1., float('inf'), float('nan')):
            with self.assertRaises(ValueError): level808.error_db(bad, .1)
        for errors, peak in (([], .2), ([float('nan')], .2), ([0.], 0.)):
            with self.assertRaises(ValueError): level808.fit_factor(errors, peak)
        for samples in ([0.] * 23999, [float('nan')] * 24000):
            with self.assertRaises(ValueError): level808.levels(samples)
