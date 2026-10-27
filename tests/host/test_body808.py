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
