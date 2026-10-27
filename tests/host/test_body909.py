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


class Decay909Tests(unittest.TestCase):
    def test_unloaded_RC_values_and_fractional_control(self):
        self.assertAlmostEqual(body.decay_tau(0),.01551)
        self.assertAlmostEqual(body.decay_tau(32512),.34551)
        self.assertAlmostEqual(body.decay_tau(16384),.1818092125984252)
        self.assertLess(body.decay_tau(16384),body.decay_tau(16385))
        for raw in (-1,32513,True,64.5):
            with self.assertRaises(ValueError): body.decay_tau(raw)

    def test_live_decay_preserves_phase_and_accumulated_envelope(self):
        switch=1024
        baseline=body.reference(4096,0)
        actual=body.reference(4096,0,{switch:32512})
        self.assertEqual(actual[:switch],baseline[:switch])
        n=2048
        expected=body.GAIN*math.exp(-switch/(48000*body.decay_tau(0))
            -(n+1-switch)/(48000*body.decay_tau(32512)))*body.triangle(50*(n+1)/48000)
        self.assertAlmostEqual(actual[n],expected,places=12)
        self.assertGreater(abs(actual[n]),abs(baseline[n]))
