import copy
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from x0x import fit808


class Fit808ProtocolTests(unittest.TestCase):
    def test_frozen_manifest_groups_every_repeat_and_preserves_scheduled_time(self):
        config, events = fit808.protocol()
        self.assertEqual(len(events), 512)
        groups = {}
        for event in events:
            pair = event['tone_cc'], event['decay_cc']
            self.assertEqual(groups.setdefault(pair, event['partition']), event['partition'])
        self.assertEqual(len(groups), 480)
        self.assertEqual({p: sum(v == p for v in groups.values()) for p in config['setting_counts']},
                         {'train': 193, 'validation': 144, 'test': 143})
        self.assertEqual(events[-1]['onset_sample'] + fit808.FRAMES, 2817 * fit808.RATE)

    def test_native_anchors_and_fractional_resolution_follow_delivered_source_steps(self):
        for cc in range(128):
            self.assertEqual(fit808.source_step(cc), int(cc * 255 / 127 + .5))
            self.assertEqual(fit808.native_coordinate(cc * 256), fit808.source_step(cc) / 255)
        self.assertEqual((fit808.source_step(63), fit808.source_step(64)), (126, 129))
        self.assertEqual(fit808.native_coordinate(63 * 256 + 128), .5)
        self.assertGreater(fit808.native_coordinate(1), fit808.native_coordinate(0))
        for bad in (-1, 128, .5, True, float('nan')):
            with self.assertRaises(ValueError):
                fit808.source_step(bad)
        for bad in (-1, 32513, True, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                fit808.native_coordinate(bad)

    def test_manifest_mutation_is_rejected_before_loading_audio(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'protocol.json').write_bytes((fit808.FIXTURES / 'protocol.json').read_bytes())
            (root / 'events.csv').write_bytes((fit808.FIXTURES / 'events.csv').read_bytes() + b'\n')
            with patch.object(fit808, 'FIXTURES', root), self.assertRaisesRegex(ValueError, 'hash mismatch'):
                fit808.protocol()

    def test_checksums_cannot_escape_the_corpus(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaisesRegex(ValueError, 'escapes'):
                fit808.checked_path(root, '../other.wav')
            (root / 'model').mkdir()
            (root / 'SHA256SUMS').write_text('0' * 64 + '  ../outside\n')
            (root / 'model/SHA256SUMS').write_text('')
            config = {'artifacts_sha256': {'../outside': '0'*64}}
            with self.assertRaisesRegex(ValueError, 'escapes'):
                fit808.verify_artifacts(root, config, [])

    def test_changed_capture_is_rejected_before_any_scoring(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'model').mkdir()
            (root / 'input.wav').write_bytes(b'original')
            (root / 'SHA256SUMS').write_text(fit808.digest(root / 'input.wav') + '  input.wav\n')
            (root / 'model/SHA256SUMS').write_text('')
            config = {'artifacts_sha256': {'input.wav': fit808.digest(root/'input.wav')}}
            (root / 'input.wav').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'Artifact hash mismatch: input.wav'):
                fit808.verify_artifacts(root, config, [])

    def test_report_output_cannot_overwrite_a_source_artifact(self):
        args = ['fit808', 'verify', '--output', str(fit808.CORPUS / '808-corpus.wav')]
        with patch('sys.argv', args), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            fit808.main()
        self.assertEqual(error.exception.code, 2)


class Fit808MetricTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy as np
        except ImportError:
            raise unittest.SkipTest('requires the pinned numpy research environment')
        cls.np = np
        cls.config, _ = fit808.protocol()

    def reference(self):
        np = self.np
        t = np.arange(fit808.FRAMES) / fit808.RATE
        return .05 * np.exp(-t / .2) * np.sin(2 * np.pi * 50 * t)

    def row(self, prediction, reference, tone=0, decay=0):
        return dict(index=0, tone_cc=tone, decay_cc=decay,
                    **fit808.measure(prediction, reference, self.config))

    def test_exact_recovery_and_known_gain_boundary(self):
        r = self.reference()
        row = self.row(self.config['dsp_gain'] * r * self.config['capture_gain'], r)
        self.assertEqual(row['relative_l2'], 0)
        self.assertEqual(row['peak_error_db'], 0)
        self.assertEqual(row['energy_error_percent'], 0)
        self.assertEqual(row['t99_error_ms'], 0)
        self.assertTrue(fit808.summarize([row], self.config)['all']['passes_gates'])

    def test_scaled_sine_has_analytically_known_level_and_energy_errors(self):
        np = self.np
        r = self.reference()
        m = fit808.measure(r * 1.01, r, self.config)
        self.assertAlmostEqual(m['relative_l2'], .01)
        self.assertAlmostEqual(m['peak_error_db'], 20 * np.log10(1.01))
        self.assertAlmostEqual(m['energy_error_percent'], 2.01)
        self.assertEqual(m['t99_error_ms'], 0)

    def test_onset_and_t99_are_measured_without_alignment(self):
        np = self.np
        r = np.zeros(fit808.FRAMES)
        r[10:20] = .05
        predicted = np.roll(r, 1)
        m = fit808.measure(predicted, r, self.config)
        self.assertAlmostEqual(m['relative_l2'], np.sqrt(.2))
        self.assertAlmostEqual(m['t99_error_ms'], 1000 / fit808.RATE)
        self.assertGreater(m['windows']['onset0to6ms']['relative_l2'], 0)

    def test_repeat_counts_do_not_reweight_settings_or_cancel_signed_level_errors(self):
        r = self.reference()
        a = self.row(r * 1.001, r)
        b = self.row(r * 1.01, r, 1, 1)
        summary = fit808.summarize([a] * 10 + [b], self.config)['all']
        self.assertEqual((summary['settings'], summary['takes']), (2, 11))
        self.assertAlmostEqual(summary['relative_l2']['median'], .0055)
        opposite = copy.deepcopy(a)
        opposite['peak_error_db'] = -a['peak_error_db']
        m = fit808.summarize([a, opposite], self.config)['all']
        self.assertAlmostEqual(m['absolute_errors']['peak_error_db']['worst'], abs(a['peak_error_db']))

    def test_quiet_tail_has_absolute_limits_even_when_full_waveform_error_is_small(self):
        np = self.np
        r = np.zeros(fit808.FRAMES)
        r[:24000] = .05
        p = r.copy()
        p[-1] = 1.01e-5
        row = self.row(p, r)
        self.assertLess(row['relative_l2'], .001)
        self.assertIsNone(row['windows']['tail500ms_to_end']['relative_l2'])
        summary = fit808.summarize([row], self.config)['all']
        self.assertEqual(summary['windows']['tail500ms_to_end']['quiet_take_failures'], 1)
        self.assertFalse(summary['passes_gates'])

    def test_silence_cannot_pass_for_an_active_target(self):
        r = self.reference()
        row = self.row(self.np.zeros_like(r), r)
        self.assertIsNone(row['peak_error_db'])
        self.assertFalse(fit808.summarize([row], self.config)['all']['passes_gates'])

    def test_nonfinite_or_incomplete_predictions_fail(self):
        np = self.np
        r = self.reference()
        for p in (r[:-1], np.full_like(r, np.nan), r.reshape(1, -1)):
            with self.assertRaises(ValueError):
                fit808.measure(p, r, self.config)
