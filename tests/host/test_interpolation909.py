import itertools
import unittest

from x0x.interpolation909 import cycle_times, experiments, interpolate, summarize, weights


class Interpolation909Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy as np
        except ImportError:
            raise unittest.SkipTest('requires the existing numpy research environment')
        cls.np = np

    def test_linear_recovers_multilinear_surface_at_uneven_coordinates(self):
        np = self.np
        knots = ([0, 2, 7], [0, 3, 9], [0, 4, 8])
        target = ([1, 5], [1, 6], [2, 7])
        def truth(coords):
            t, a, d = np.meshgrid(*coords, indexing='ij')
            return (3 + t + 2*a + d + t*a + a*d + t*a*d)[..., None]
        np.testing.assert_allclose(interpolate(truth(knots), knots, target, 'linear'), truth(target), atol=1e-12)

    def test_cubic_recovers_polynomial_and_preserves_exact_knots(self):
        np = self.np
        knots = [0, 2, 5, 7, 10]
        w = weights(knots, [1, 4, 8], 'cubic')
        np.testing.assert_allclose(w @ (np.asarray(knots)**3), [1, 64, 512], atol=1e-12)
        np.testing.assert_array_equal(weights(knots, knots, 'cubic'), np.eye(5))

    def test_missing_unused_nodes_do_not_poison_predictions(self):
        np = self.np
        values = np.array([1., 2., 3., np.nan]).reshape(4, 1, 1, 1)
        values = np.broadcast_to(values, (4, 2, 2, 1))
        result = interpolate(values, ([0, 1, 2, 3], [0, 1], [0, 1]), ([.5, 2.5], [0], [0]), 'linear')
        self.assertEqual(result[0, 0, 0, 0], 1.5)
        self.assertTrue(np.isnan(result[1, 0, 0, 0]))

    def test_invalid_or_extrapolated_requests_are_rejected(self):
        for knots, target, method in [([0, 1], [-1], 'linear'), ([0, 1], [2], 'linear'),
                                       ([0, 0], [0], 'linear'), ([0, 1], [.5], 'cubic'),
                                       ([0, float('nan')], [0], 'linear'), ([0, 1], [.5], 'other')]:
            with self.assertRaises(ValueError):
                weights(knots, target, method)

    def test_every_experiment_excludes_target_settings_from_calibration(self):
        rows = list(experiments())
        self.assertEqual(len(rows), 45)
        for row in rows:
            train, target = set(itertools.product(*row['training'])), set(itertools.product(*row['targets']))
            self.assertFalse(train & target)
            self.assertEqual(len(target), 64 if row['kind'] == 'common64' else 81)
        self.assertEqual(rows[0]['targets'], rows[1]['targets'])

    def test_summary_retains_three_takes_and_excludes_missing_features(self):
        np = self.np
        predicted = np.array([[2.], [np.nan]])
        actual = np.array([[[1.], [2.], [3.]], [[1.], [1.], [1.]]])
        result = summarize(predicted, actual, [(0, 0, 0), (1, 1, 1)])
        self.assertEqual(result['rmse_by_take'], [1, 0, 1])
        self.assertEqual(result['settings'], 1)
        self.assertEqual(result['excluded_settings'], 1)

    def test_cycle_times_preserve_scheduled_time_and_reject_unresolved_audio(self):
        np = self.np
        t = np.arange(24000) / 48000
        crossings = cycle_times(np.sin(2*np.pi*50*t))
        np.testing.assert_allclose(crossings, np.arange(1, 14) / 50, atol=1e-12)
        with self.assertRaises(ValueError):
            cycle_times(np.zeros(24000))


if __name__ == '__main__':
    unittest.main()
