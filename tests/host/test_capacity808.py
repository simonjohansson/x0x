import json
import unittest

from x0x import capacity808, fit808


class Capacity808Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy as np
            import scipy
        except ImportError:
            raise unittest.SkipTest('requires the pinned numpy/scipy research environment')
        cls.np = np
        cls.config, cls.events = fit808.protocol()

    def parameters(self):
        np = self.np
        return np.array([47.65, 45, np.log(.0015), 10, np.log(.04),
                         np.log(.001), np.log(.02), np.log(.001)])

    def test_capacity_subset_contains_only_distinct_fitting_settings(self):
        experiment = json.loads((fit808.FIXTURES / 'capacity.json').read_text())
        pairs = {tuple(p) for p in experiment['pairs']}
        training = {(e['tone_cc'], e['decay_cc']) for e in self.events if e['partition'] == 'train'}
        self.assertEqual(len(pairs), 16)
        self.assertLessEqual(pairs, training)
        self.assertTrue({(0, 0), (0, 127), (127, 0), (127, 127), (68, 68)} <= pairs)

    def test_closed_form_recovers_an_independent_constant_frequency_exponential(self):
        np = self.np
        p = self.parameters()
        p[1] = p[3] = 0
        t = np.arange(fit808.FRAMES) / fit808.RATE
        tau = np.exp(p[5]) + np.exp(p[6])
        actual = capacity808.columns(p, t) @ [.07, 0, 0, 0, 0]
        expected = .07 * np.exp(-t / tau) * np.sin(2 * np.pi * 47.65 * t)
        np.testing.assert_allclose(actual, expected, atol=1e-15)

    def test_pitch_derivative_and_harmonic_are_the_declared_processes(self):
        np = self.np
        p = self.parameters()
        t = np.linspace(0, .5, 20000)
        matrix = capacity808.columns(np.r_[p, np.log(.01)], t, True)
        fast, slow = np.exp(p[5]), np.exp(p[5]) + np.exp(p[6])
        phase = np.unwrap(np.arctan2(matrix[:, 0] * np.exp(t / slow), matrix[:, 1] * np.exp(t / slow)))
        frequency = np.diff(phase) / np.diff(t) / (2 * np.pi)
        mid = (t[1:] + t[:-1]) / 2
        expected = p[0] + p[1] * np.exp(-mid / np.exp(p[2])) + p[3] * np.exp(-mid / (np.exp(p[2]) + np.exp(p[4])))
        np.testing.assert_allclose(frequency, expected, rtol=2e-5)
        np.testing.assert_allclose(matrix[:, 5], np.exp(-t / .01) * np.sin(2 * phase), atol=1e-14)
        np.testing.assert_allclose(matrix[:, 2], np.exp(-t / fast) * np.sin(phase), atol=1e-14)

    def test_objective_samples_cover_full_slot_with_finite_positive_weights(self):
        np = self.np
        t = np.arange(fit808.FRAMES) / fit808.RATE
        reference = .05 * np.exp(-t / .1) * np.sin(2 * np.pi * 50 * t)
        indices, weight = capacity808.sample_objective(reference, self.config)
        self.assertEqual(indices[0], 0)
        self.assertGreater(indices[-1], fit808.FRAMES - 129)
        self.assertTrue(np.all(np.diff(indices) > 0))
        self.assertTrue(np.isfinite(weight).all() and (weight > 0).all())
        self.assertTrue(set(range(288)) <= set(indices))

    def test_optimizer_recovers_a_synthetic_waveform_without_time_or_gain_correction(self):
        np = self.np
        t = np.arange(fit808.FRAMES) / fit808.RATE
        reference = capacity808.columns(self.parameters(), t) @ [.06, .004, -.02, -.002, .001]
        prediction, fit = capacity808.fit_one(reference, self.config, {'starts': 1, 'max_nfev': 150})
        error = np.linalg.norm(prediction - reference) / np.linalg.norm(reference)
        self.assertLess(error, 1e-7)
        self.assertTrue(fit['runs'][0]['converged'])
        self.assertGreater(fit['runs'][0]['residual_calls'], fit['runs'][0]['nfev'])
