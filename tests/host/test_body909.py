import math
import unittest

from x0x import body909 as body
from x0x.analysis import analyze


class Body909Tests(unittest.TestCase):
    def test_triangle_frequency_scale_decay_and_reset_baseline(self):
        samples = body.reference(48000)
        report = analyze(samples,body.SAMPLE_RATE)
        self.assertAlmostEqual(report["frequency"]["median_hz"],body.FREQUENCY,delta=.001)
        self.assertAlmostEqual(report["decay_positive"]["time_constant_s"],body.TAU,delta=1e-5)
        self.assertGreater(report["peak_fs"],body.GAIN*.97)
        self.assertLess(report["peak_fs"],body.GAIN)
        self.assertEqual(body.reference(32),samples[:32])
        self.assertEqual(report["onset_sample"],0)
        self.assertGreater(samples[0],0)

    def test_triangle_has_odd_harmonics_distinct_from_the_808_sine(self):
        n=4800
        samples=[body.triangle(body.FREQUENCY*i/body.SAMPLE_RATE) for i in range(n)]
        def amplitude(harmonic):
            return 2*abs(sum(y*complex(math.cos(2*math.pi*harmonic*body.FREQUENCY*i/body.SAMPLE_RATE),
                                       math.sin(2*math.pi*harmonic*body.FREQUENCY*i/body.SAMPLE_RATE))
                             for i,y in enumerate(samples)))/n
        fundamental=amplitude(1)
        self.assertAlmostEqual(fundamental,8/math.pi**2,delta=1e-5)
        self.assertAlmostEqual(amplitude(3)/fundamental,1/9,delta=1e-5)
        self.assertAlmostEqual(amplitude(5)/fundamental,1/25,delta=1e-5)
        self.assertLess(amplitude(2),1e-12)
