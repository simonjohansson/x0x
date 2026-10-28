import unittest

from x0x import fit808, tone_factor808


class ToneFactor808Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy as np
            import scipy
        except ImportError:
            raise unittest.SkipTest('requires the pinned 808 research environment')
        cls.np = np
        cls.parameters = np.array([17e-6, 200e-6, 40e-6, .14, .7])

    def direct(self, source, pole):
        result, state = [], 0.
        for sample in source:
            state = pole * state + (1 - pole) * sample
            result.append(state)
        return self.np.array(result)

    def test_relative_transfer_matches_two_independent_direct_filters(self):
        np = self.np
        source = np.random.default_rng(83).normal(0, .05, 4096)
        high = float(tone_factor808.poles(self.parameters, 1))
        canonical = self.direct(source, high)
        for raw in (0, 63 * 256 + 128, 127 * 256):
            pole = float(tone_factor808.poles(self.parameters, fit808.native_coordinate(raw)))
            expected = self.direct(source, pole)
            actual = tone_factor808.transfer(canonical, self.parameters, raw)
            np.testing.assert_allclose(actual, expected, atol=1e-14)

    def test_all_native_fractional_words_have_stable_monotone_poles(self):
        np = self.np
        positions = [fit808.native_coordinate(raw) for raw in range(32513)]
        values = tone_factor808.poles(self.parameters, positions)
        self.assertTrue(np.all(np.diff(values) <= 0))
        self.assertGreater(values.min(), 0)
        self.assertLess(values.max(), 1)

    def test_canonical_tone_is_identity_without_alignment_or_gain_fitting(self):
        np = self.np
        source = np.random.default_rng(84).normal(0, .02, 3000)
        np.testing.assert_allclose(tone_factor808.transfer(source, self.parameters, 127 * 256), source, atol=1e-15)
        impulse = np.zeros(3000)
        impulse[0] = 1
        response = tone_factor808.transfer(impulse, self.parameters, 0)
        self.assertAlmostEqual(float(response.sum()), 1)

    def test_relative_filter_has_an_equivalent_single_state_recurrence(self):
        np = self.np
        source = np.random.default_rng(87).normal(0, .03, 2048)
        pole = float(tone_factor808.poles(self.parameters, fit808.native_coordinate(68 * 256)))
        zero = float(tone_factor808.poles(self.parameters, 1))
        gain = (1 - pole) / (1 - zero)
        state, values = 0., []
        for sample in source:
            output = gain * sample + state
            state = pole * output - gain * zero * sample
            values.append(output)
        np.testing.assert_allclose(values, tone_factor808.transfer(source, self.parameters, 68 * 256), atol=1e-14)

    def test_shared_fit_recovers_unfitted_synthetic_control_positions(self):
        np = self.np
        excitation = np.random.default_rng(85).normal(0, .03, 2048)
        source = self.direct(excitation, float(tone_factor808.poles(self.parameters, 1)))
        tones = [0, 17, 34, 68, 102, 119]
        targets = [tone_factor808.transfer(source, self.parameters, t * 256) for t in tones]
        fitted, evidence = tone_factor808.fit_parameters(source, targets, tones)
        self.assertTrue(evidence['converged'])
        for tone in (.5, 50.5, 127):
            expected = tone_factor808.transfer(source, self.parameters, tone * 256)
            actual = tone_factor808.transfer(source, fitted, tone * 256)
            self.assertLess(np.linalg.norm(actual - expected) / np.linalg.norm(expected), 1e-5)

    def test_float32_parameters_preserve_the_reference_filter(self):
        np = self.np
        source = np.random.default_rng(86).normal(0, .03, 3000)
        for raw in (0, 63 * 256 + 128, 127 * 256):
            expected = tone_factor808.transfer(source, self.parameters, raw)
            actual = tone_factor808.transfer(source, self.parameters.astype('float32'), raw)
            self.assertLess(float(np.max(abs(actual - expected))), 1e-7)

    def test_invalid_coefficients_controls_and_samples_fail(self):
        np = self.np
        for values in ([1e-6, 1, 1, 1, 1], [1e-4, -1, 1, 1, 1], [1e-4, 1, 1, 0, 1], [float('nan')] * 5):
            with self.assertRaises(ValueError):
                tone_factor808.poles(values, .5)
        for raw in (-1, 32513, float('nan')):
            with self.assertRaises(ValueError):
                tone_factor808.transfer([0, 1], self.parameters, raw)
        for source in ([[0, 1]], [0, float('nan')]):
            with self.assertRaises(ValueError):
                tone_factor808.transfer(source, self.parameters, 0)
        with self.assertRaises(ValueError):
            tone_factor808.fit_parameters(np.zeros(10), np.zeros((1, 10)), [0])
