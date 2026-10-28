import tempfile
import unittest
from collections import Counter
from pathlib import Path

from x0x import field808, fit808


class Field808Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy as np
            import scipy
        except ImportError:
            raise unittest.SkipTest('requires the pinned 808 research environment')
        cls.np = np

    def synthetic(self):
        np = self.np
        model = field808.geometry()
        model['tone'] = np.array([17e-6, 200e-6, 40e-6, .14, .7], dtype='float32')
        for i, width in enumerate((96, 40, 64, 99)):
            rank = (2, 4, 8, 8)[i]
            values = np.zeros((rank, width))
            if i == 3:
                values[0, :20] = 1
            field808.put_rows(model, 'block' + str(i), values)
            if i < 2:
                field808.put_rows(model, 'block' + str(i) + '_mix', np.zeros((rank, 8)))
        control = np.zeros((8, 19))
        control[0] = 1
        field808.put_rows(model, 'control', control)
        return model

    def test_quantized_rows_have_a_half_step_error_bound_and_safe_zero_rows(self):
        np = self.np
        values = np.random.default_rng(808).normal(0, .07, (4, 31))
        values[1] = 0
        model = {}
        field808.put_rows(model, 'x', values)
        actual = field808.decode_rows(model, 'x')
        self.assertEqual(model['x'].dtype, np.dtype('int16'))
        self.assertTrue(np.all(abs(actual - values) <= model['x_scale'][:, None] * .50001))
        np.testing.assert_array_equal(actual[1], 0)

    def test_spline_matches_an_independent_local_de_boor_evaluation(self):
        np = self.np
        breaks = np.array([0., .04, .1, .25, .7, 1.])
        knots = np.r_[np.repeat(0., 4), breaks[1:-1], np.repeat(1., 4)]
        values = np.random.default_rng(84).normal(size=len(breaks) + 2)
        def local(t):
            span = min(len(values) - 1, int(np.searchsorted(knots, t, side='right') - 1))
            work = [float(v) for v in values[span - 3:span + 1]]
            for order in range(1, 4):
                for j in range(3, order - 1, -1):
                    i = span - 3 + j
                    alpha = (t - knots[i]) / (knots[i + 4 - order] - knots[i])
                    work[j] = (1 - alpha) * work[j - 1] + alpha * work[j]
            return work[3]
        times = np.r_[0., np.linspace(.0001, .9999, 47), 1.]
        design = field808.spline(times, breaks)
        np.testing.assert_allclose(design @ values, [local(t) for t in times], atol=1e-14)
        np.testing.assert_allclose(design.sum(axis=1), 1., atol=1e-14)
        self.assertGreaterEqual(float(design.min()), 0)

    def test_dictionary_has_an_exact_zero_start_and_continuous_overlap(self):
        np = self.np
        model = field808.geometry()
        np.testing.assert_array_equal(field808.dictionary(model, [0.]), 0)
        coefficients = np.random.default_rng(86).normal(0, .01, 299)
        for time in (.020, .030):
            values = field808.dictionary(model, [time - 1e-10, time, time + 1e-10]) @ coefficients
            self.assertLess(float(np.max(abs(values - values[1]))), 1e-8)

    def test_standalone_render_matches_a_known_carrier_and_tone_recurrence(self):
        np = self.np
        model = self.synthetic()
        times = np.arange(3300) / fit808.RATE
        fade = np.clip((times - .020) / .010, 0, 1)
        expected = fade * fade * (3 - 2 * fade) * np.sin(2 * np.pi * float(model['carrier_hz'][0]) * times)
        actual = field808.render(model, 127 * 256, 63 * 256 + 128, len(times))
        np.testing.assert_allclose(actual, expected, atol=2e-9)
        from x0x import tone_factor808
        pole = float(tone_factor808.poles(model['tone'], 0.))
        zero = float(tone_factor808.poles(model['tone'], 1.))
        gain = (1 - pole) / (1 - zero)
        history, prior, output = 0., 0., []
        for value in expected:
            history = pole * history + gain * (value - zero * prior)
            output.append(history)
            prior = value
        np.testing.assert_allclose(field808.render(model, 0, 0, len(times)), output, atol=2e-9)

    def test_native_fractional_control_preserves_the_frozen_coordinate(self):
        np = self.np
        model = self.synthetic()
        breaks = np.linspace(0, 1, 17)
        knots = np.r_[np.repeat(0., 4), breaks[1:-1], np.repeat(1., 4)]
        maps = np.zeros((8, 19))
        maps[0] = [np.mean(knots[i + 1:i + 4]) for i in range(19)]
        field808.put_rows(model, 'control', maps)
        for raw in (0, 17 * 256, 63 * 256 + 128, 127 * 256):
            weights = field808.control_weights(model, raw)
            self.assertAlmostEqual(weights[0], fit808.native_coordinate(raw),
                                   delta=float(model['control_scale'][0]) * .50001)
            np.testing.assert_array_equal(weights[1:], 0)

    def test_encoded_model_round_trip_preserves_the_rendered_samples(self):
        np = self.np
        model = self.synthetic()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'model.npz'
            np.savez(path, **model)
            with np.load(path, allow_pickle=False) as saved:
                restored = {name: saved[name] for name in saved.files}
            np.testing.assert_array_equal(field808.render(model, 256, 3 * 256, 1800),
                                          field808.render(restored, 256, 3 * 256, 1800))

    def test_listening_cohort_contains_four_fitting_and_twelve_validation_settings(self):
        _, events = fit808.protocol()
        chosen = field808.listening_subset(events)
        self.assertEqual(Counter(e['partition'] for e in chosen), dict(train=4, validation=12))
        self.assertEqual(len({(e['tone_cc'], e['decay_cc']) for e in chosen}), 16)

    def test_fitting_recovers_an_independent_synthetic_controlled_carrier(self):
        np = self.np
        model = field808.geometry()
        times = np.arange(fit808.FRAMES) / fit808.RATE
        fade = np.clip((times - .020) / .010, 0, 1)
        carrier = fade * fade * (3 - 2 * fade) * np.sin(2 * np.pi * float(model['carrier_hz'][0]) * times)
        decays = list(range(0, 128, 4)) + [127]
        targets = np.array([(.03 + .02 * fit808.native_coordinate(d * 256)) * carrier for d in decays])
        config, _ = fit808.protocol()
        field808.fit_body(targets, decays, config, model)
        model['tone'] = np.array([17e-6, 200e-6, 40e-6, .14, .7], dtype='float32')
        raw = 13 * 256 + 128
        expected = (.03 + .02 * fit808.native_coordinate(raw)) * carrier[:6000]
        prediction = field808.render(model, 127 * 256, raw, len(expected))
        self.assertLess(float(np.linalg.norm(prediction - expected) / np.linalg.norm(expected)), .001)

    def test_invalid_inputs_and_malformed_coefficient_arrays_fail(self):
        np = self.np
        model = self.synthetic()
        for value in (-1, 32513, float('nan')):
            with self.assertRaises(ValueError):
                field808.render(model, value, 0, 1)
            with self.assertRaises(ValueError):
                field808.control_weights(model, value)
        for frames in (0, fit808.FRAMES + 1, 2.5):
            with self.assertRaises(ValueError):
                field808.render(model, 0, 0, frames)
        for values in ([0, float('nan')], [[1, float('inf')]]):
            with self.assertRaises(ValueError):
                field808.encode_rows(values)
        model['block2'] = np.zeros((8, 63), dtype='int16')
        with self.assertRaises(ValueError):
            field808.body_basis(model)


if __name__ == '__main__':
    unittest.main()
