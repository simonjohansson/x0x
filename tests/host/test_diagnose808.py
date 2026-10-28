import base64
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from x0x import diagnose808, fit808


class Diagnose808Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy as np
            import scipy
            import soundfile as sf
        except ImportError:
            raise unittest.SkipTest('requires the pinned 808 research environment')
        cls.np, cls.sf = np, sf
        cls.config, _ = fit808.protocol()

    def parameters(self):
        np = self.np
        return np.array([50, 0, np.log(.002), 0, np.log(.05), np.log(.001),
                         np.log(.099), np.log(.02), np.log(.05), np.log(.18)])

    def test_full_rate_objective_matches_the_declared_window_sum(self):
        np = self.np
        r = np.ones(fit808.FRAMES) * .02
        indices, weights = diagnose808.objective_weights(r, self.config, True)
        self.assertEqual(len(indices), fit808.FRAMES)
        self.assertAlmostEqual(float(np.sum((.01 * r * weights) ** 2)), .0002)
        q, qw = diagnose808.objective_weights(r, self.config)
        self.assertAlmostEqual(float(np.sum((.01 * r[q] * qw) ** 2)), .0002)

    def test_output_basis_starts_at_zero_and_expanded_coefficients_reproduce_it(self):
        np = self.np
        p = self.parameters()
        t = np.arange(fit808.FRAMES) / fit808.RATE
        matrix = diagnose808.columns(p, t, True)
        self.assertEqual(matrix.shape, (fit808.FRAMES, 7))
        np.testing.assert_array_equal(matrix[0], np.zeros(7))
        coefficients = np.array([.04, .003, -.01, .002, .001, -.002, .0005])
        full = diagnose808.amplitudes(coefficients, True)
        from x0x import capacity808
        raw = np.column_stack((capacity808.columns(p[:9], t, True), np.exp(-t / .2)))
        np.testing.assert_allclose(raw @ full, matrix @ coefficients, atol=1e-16)
        self.assertAlmostEqual(sum(full[i] for i in (1, 3, 4, 6, 7)), 0)

    def test_cycle_initialization_recovers_a_known_pitch_trajectory(self):
        np = self.np
        t = np.arange(fit808.FRAMES) / fit808.RATE
        phase = 2 * np.pi * (47.65 * t + 14 * .05 * (1 - np.exp(-t / .05)))
        r = .05 * np.exp(-t / .2) * np.sin(phase)
        seeds, measured = diagnose808.measured_seed(r, self.parameters()[:9])
        self.assertEqual(len(seeds), 4)
        self.assertLess(abs(measured['bend_hz'] - 14), 2)
        self.assertLess(abs(measured['pitch_tau_seconds'] - .05), .01)

    def test_projection_recovers_an_independent_causal_damped_sine(self):
        np = self.np
        p = self.parameters()
        t = np.arange(fit808.FRAMES) / fit808.RATE
        reference = .04 * np.exp(-t / .1) * np.sin(2 * np.pi * 50 * t) + .002 * (np.exp(-t / .2) - np.exp(-t / .02))
        predicted, result = diagnose808.solve(reference, self.config, [p], p - .2, p + .2, True, max_nfev=10)
        self.assertLess(np.linalg.norm(predicted - reference) / np.linalg.norm(reference), 1e-10)
        self.assertTrue(result['numerically_viable'])
        self.assertEqual(predicted[0], 0)

    def test_adopted_full_rate_polish_keeps_acyclic_auditable_history(self):
        np = self.np
        initial = dict(runs=[{'nonlinear': [1.]}], selected_start=0, bounds={'lower': [0], 'upper': [2]}, full_objective=1.)
        evidence = dict(numerically_viable=True, full_objective=.5)
        with patch.object(diagnose808, 'solve', return_value=(np.zeros(2), evidence)):
            _, fit = diagnose808.polish(np.zeros(2), self.config, np.ones(2), initial, False)
        self.assertTrue(fit['polish_adopted'])
        self.assertIn('quadrature_fit', fit)
        json.dumps(fit, allow_nan=False)

    def test_listening_wavs_keep_relative_gain_and_trigger_timing(self):
        np = self.np
        r, p = np.zeros(fit808.FRAMES), np.zeros(fit808.FRAMES)
        r[7], p[7] = .01, .012
        with tempfile.TemporaryDirectory() as folder:
            gain = diagnose808.listening_report(Path(folder), [{'tone_cc': 0, 'decay_cc': 0}],
                {(0, 0): r}, {(0, 0): p}, {'source_sha256': 'test'})
            page = (Path(folder) / 'index.html').read_text()
            downloads = {p.name: p.read_bytes() for p in Path(folder).glob('*-playback.wav')}
        payload = page.split('const data=', 1)[1].split(';\nconst $', 1)[0]
        data = json.loads(payload)
        self.assertEqual(gain, 4)
        for key, original in [('recorded', r), ('candidate', p)]:
            encoded = base64.b64decode(data['stimuli'][0][key])
            self.assertEqual(downloads[data['stimuli'][0][key + '_download']], encoded)
            self.assertEqual(self.sf.info(io.BytesIO(encoded)).subtype, 'PCM_24')
            wave, rate = self.sf.read(io.BytesIO(encoded))
            self.assertEqual(rate, fit808.RATE)
            np.testing.assert_allclose(wave, original * gain, atol=1 / 2**23, rtol=0)
            self.assertEqual(int(np.argmax(abs(wave))), 7)
        self.assertEqual(data['manifest']['source_sha256'], 'test')
        self.assertTrue(data['gain_applied'])
        self.assertEqual(data['playback_encoding'], 'PCM_24')

    def test_one_common_gain_prevents_clipping_without_per_hit_normalization(self):
        np = self.np
        r, p = np.array([.2, 0.]), np.array([.5, 0.])
        with tempfile.TemporaryDirectory() as folder:
            gain = diagnose808.listening_report(Path(folder), [{'tone_cc': 0, 'decay_cc': 0}],
                {(0, 0): r}, {(0, 0): p}, {})
        self.assertAlmostEqual(gain, 1.9)
        self.assertEqual((p[0] * gain) / (r[0] * gain), 2.5)
