import unittest

from x0x.analysis import analyze
from x0x.pulse808 import main_reference as reference
from x0x.body808 import FREQUENCY, ATTACK_FREQUENCY, ATTACK_SAMPLES, GAIN, SAMPLE_RATE, TAU


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
    def test_lower_curve_corrects_interiors_and_preserves_all_upper_words(self):
        import math
        from x0x.body808 import decay_tau, retention, RETENTION_DEFAULT, RETENTION_MAX
        for raw, tau in ((0, .0333), (4096, .04786953125),
                         (8192, .08129375), (12288, .11814609375), (16384, .143)):
            self.assertAlmostEqual(decay_tau(raw), tau, delta=1e-12)
        for raw in range(16384, 32513):
            previous = RETENTION_DEFAULT + (RETENTION_MAX-RETENTION_DEFAULT)*(raw-16384)/16128
            self.assertEqual(retention(raw), previous)
        for raw in (0, 16384, 32512):
            self.assertTrue(math.isfinite(retention(raw)))

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
        expected = baseline[n]*(retention(32512)/retention(0))**(n+1-switch)
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

    def test_live_interior_changes_keep_the_existing_phase_and_state_policy(self):
        from x0x.body808 import retention
        switch = 3200
        for before, after in ((4096, 8193), (12288, 24576), (24576, 8191)):
            actual = reference(6400, before, {switch: after})
            baseline = reference(6400, before)
            self.assertEqual(actual[:switch], baseline[:switch])
            n = switch + 200
            expected = baseline[n]*(retention(after)/retention(before))**(n+1-switch)
            self.assertAlmostEqual(actual[n], expected, places=11)


class Excitation808Tests(unittest.TestCase):
    def test_switch_conserves_both_capacitor_voltages_without_an_output_jump(self):
        import math
        from x0x.body808 import retention, switch_coordinates
        high, low = 2*math.pi*ATTACK_FREQUENCY, 2*math.pi*FREQUENCY
        a = 1/(1e6*15e-9)
        for raw in (0,1,16383,16384,16385,32511,32512):
            sigma = -SAMPLE_RATE*math.log(retention(raw))
            alpha, beta = switch_coordinates(raw)
            for x,y in ((.2,-.1),(-.2,.1),(0,.25)):
                new_y = alpha*y+beta*x
                c41 = -a*(sigma*x+high*y)/(sigma*sigma+high*high)
                after = -a*(sigma*x+low*new_y)/(sigma*sigma+low*low)
                self.assertAlmostEqual(after,c41,places=14)
                self.assertAlmostEqual(-x-after,-x-c41,places=14)
            self.assertLess(abs(alpha)+abs(beta),1)  # No increase in the state bound.
