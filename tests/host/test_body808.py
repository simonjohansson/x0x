import unittest

from x0x.analysis import analyze
from x0x.body808 import FREQUENCY, GAIN, SAMPLE_RATE, TAU, reference


class Body808Tests(unittest.TestCase):
    def test_analytic_body_has_the_declared_pitch_decay_and_scale(self):
        samples = reference(SAMPLE_RATE)
        report = analyze(samples, SAMPLE_RATE)
        self.assertAlmostEqual(report['frequency']['median_hz'], FREQUENCY, delta=.001)
        for side in ('positive', 'negative'):
            fit = report['decay_' + side]
            self.assertTrue(fit['applicable'])
            self.assertAlmostEqual(fit['time_constant_s'], TAU, delta=1e-5)
        self.assertEqual(report['onset_sample'], 0)
        self.assertGreater(report['peak_fs'], GAIN * .98)
        self.assertLess(report['peak_fs'], GAIN)
        self.assertLess(abs(report['dc_fs']), .001)


class Decay808Tests(unittest.TestCase):
    def test_feedback_positions_give_monotonic_decay_without_changing_pitch(self):
        from x0x.body808 import decay_tau
        lengths = []
        for raw in (0, 16384, 32512):
            measured = analyze(reference(SAMPLE_RATE // 2, raw), SAMPLE_RATE)
            tau = measured['decay_positive']['time_constant_s']
            self.assertAlmostEqual(tau, decay_tau(raw), delta=1e-5)
            self.assertAlmostEqual(measured['frequency']['median_hz'], FREQUENCY, delta=.001)
            lengths.append(tau)
        self.assertLess(lengths[0], lengths[1])
        self.assertLess(lengths[1], lengths[2])
        self.assertAlmostEqual(lengths[1], TAU, places=8)
        self.assertAlmostEqual(lengths[2], 1, places=8)

    def test_live_decay_change_preserves_phase_and_accumulated_attenuation(self):
        from x0x.body808 import retention
        switch = 3200
        actual = reference(6400, 0, {switch: 32512})
        baseline = reference(6400, 0)
        self.assertEqual(actual[:switch], baseline[:switch])
        import math
        n = switch + 200
        expected = (GAIN * retention(0)**switch * retention(32512)**(n + 1 - switch)
                    * math.sin(2 * math.pi * FREQUENCY * (n + 1) / SAMPLE_RATE))
        self.assertAlmostEqual(actual[n], expected, places=11)
        self.assertGreater(abs(actual[n]), abs(baseline[n]))

    def test_fractional_decay_is_not_quantized_to_the_displayed_integer(self):
        from x0x.body808 import retention
        self.assertLess(retention(16384), retention(16385))
        for raw in (-1, 32513, True, 64.5):
            with self.assertRaises(ValueError):
                retention(raw)
