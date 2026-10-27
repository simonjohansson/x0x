import unittest

from x0x.analysis import analyze
from x0x.body808 import FREQUENCY, ATTACK_FREQUENCY, ATTACK_SAMPLES, GAIN, SAMPLE_RATE, TAU, reference


def impulse_phase(n, k):
    import math
    return 2*math.pi/SAMPLE_RATE * (ATTACK_FREQUENCY*(min(n+1, ATTACK_SAMPLES)-k)
                                   + FREQUENCY*max(n+1-ATTACK_SAMPLES, 0))


class Body808Tests(unittest.TestCase):
    def test_analytic_body_has_the_declared_pitch_decay_and_scale(self):
        samples = reference(SAMPLE_RATE)
        report = analyze(samples, SAMPLE_RATE)
        self.assertAlmostEqual(report['frequency']['median_hz'], 47.65, delta=.001)
        for side in ('positive', 'negative'):
            fit = report['decay_' + side]
            self.assertTrue(fit['applicable'])
            self.assertAlmostEqual(fit['time_constant_s'], TAU, delta=1e-5)
        self.assertEqual(report['onset_sample'], 0)
        self.assertLess(report['peak_fs'], GAIN)
        self.assertLess(abs(report['dc_fs']), .001)


class Decay808Tests(unittest.TestCase):
    def test_feedback_positions_give_monotonic_decay_without_changing_pitch(self):
        from x0x.body808 import decay_tau
        lengths = []
        for raw, target in ((0, .0333), (16384, .143), (32512, .366)):
            measured = analyze(reference(SAMPLE_RATE // 2, raw), SAMPLE_RATE)
            tau = measured['decay_positive']['time_constant_s']
            self.assertAlmostEqual(tau, decay_tau(raw), delta=1e-5)
            self.assertAlmostEqual(tau, target, delta=1e-5)
            self.assertAlmostEqual(measured['frequency']['median_hz'], FREQUENCY, delta=.001)
            lengths.append(tau)
        self.assertLess(lengths[0], lengths[1])
        self.assertLess(lengths[1], lengths[2])
        self.assertAlmostEqual(lengths[1], TAU, places=8)
        self.assertAlmostEqual(lengths[2], .366, places=8)

    def test_live_decay_change_preserves_phase_and_accumulated_attenuation(self):
        from x0x.body808 import retention
        switch = 3200
        actual = reference(6400, 0, {switch: 32512})
        baseline = reference(6400, 0)
        self.assertEqual(actual[:switch], baseline[:switch])
        import math
        n = switch + 200
        expected = sum(GAIN/48 * retention(0)**(switch-k) * retention(32512)**(n+1-switch)
                       * math.sin(impulse_phase(n,k)) for k in range(48))
        self.assertAlmostEqual(actual[n], expected, places=11)
        self.assertGreater(abs(actual[n]), abs(baseline[n]))

    def test_fractional_decay_is_not_quantized_to_the_displayed_integer(self):
        from x0x.body808 import retention
        self.assertLess(retention(16384), retention(16385))
        positions = [retention(raw) for raw in range(32513)]
        self.assertTrue(all(a < b < 1 for a, b in zip(positions, positions[1:])))
        for raw in (-1, 32513, True, 64.5):
            with self.assertRaises(ValueError):
                retention(raw)


class Excitation808Tests(unittest.TestCase):
    def test_finite_pulse_matches_direct_convolution_at_callback_boundaries(self):
        import math
        from x0x.body808 import PULSE_SAMPLES, PULSE_GAIN, retention
        self.assertEqual(PULSE_SAMPLES,48)
        self.assertEqual(PULSE_SAMPLES/SAMPLE_RATE,.001)
        self.assertEqual(ATTACK_SAMPLES/SAMPLE_RATE,.006)
        for raw in (0,16384,32512):
            samples=reference(2001,raw)
            for n in (0,31,32,47,48,63,64,255,256,287,288,289,319,320,2000):
                expected=sum(PULSE_GAIN*retention(raw)**(n+1-k)
                    * math.sin(impulse_phase(n,k))
                    for k in range(min(n+1,PULSE_SAMPLES)))
                self.assertAlmostEqual(samples[n],expected,places=12)
            self.assertAlmostEqual(samples[0],PULSE_GAIN*retention(raw)*math.sin(2*math.pi*ATTACK_FREQUENCY/SAMPLE_RATE),places=14)
