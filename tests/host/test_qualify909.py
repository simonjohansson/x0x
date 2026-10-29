"""Qualification rejects invalid output instead of issuing a passing receipt."""
import unittest
import hashlib
import json
from pathlib import Path
import tempfile
from unittest import mock

import numpy as np
from x0x import qualify909


class QualificationTests(unittest.TestCase):
    def test_report_rejects_changed_artifacts_and_historical_sources(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(qualify909, 'OUT', Path(tmp)):
            folder = Path(tmp)/'sharc'
            folder.mkdir()
            wav, png = folder/'audio.wav', folder/'corners.png'
            wav.write_bytes(b'complete audio')
            png.write_bytes(b'complete picture')
            report = dict(status='passed', target='sharc', model_sha256=qualify909.field909.MODEL_SHA,
                          test_settings=721, test_events=724, inputs_sha256=qualify909.input_hashes(),
                          rendered_wav=str(wav), rendered_wav_sha256=hashlib.sha256(wav.read_bytes()).hexdigest(),
                          corners_png=str(png), corners_png_sha256=hashlib.sha256(png.read_bytes()).hexdigest())
            path = folder/'report.json'
            path.write_text(json.dumps(report))
            self.assertEqual(qualify909.load_report('sharc'), report)
            wav.write_bytes(b'partial replacement')
            with self.assertRaisesRegex(ValueError, 'artifact hash'):
                qualify909.load_report('sharc')
            report['inputs_sha256'] = {}
            path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, 'Historical'):
                qualify909.load_report('sharc')

    def test_failed_rerun_preserves_previous_receipt_and_audio(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(qualify909, 'OUT', Path(tmp)):
            folder = Path(tmp)/'sharc'
            folder.mkdir()
            (folder/'report.json').write_bytes(b'previous receipt')
            (folder/'rendered-native.wav').write_bytes(b'previous audio')
            with mock.patch.object(qualify909.field909, 'load', side_effect=RuntimeError('interrupted')):
                with self.assertRaisesRegex(RuntimeError, 'interrupted'):
                    qualify909.qualify('sharc')
            self.assertEqual((folder/'report.json').read_bytes(), b'previous receipt')
            self.assertEqual((folder/'rendered-native.wav').read_bytes(), b'previous audio')
            self.assertEqual(len(list((folder/'runs').iterdir())), 1)

    def test_port_gate_rejects_nonfinite_or_excessive_error(self):
        expected = np.ones(96000)
        self.assertEqual(qualify909.port_error(expected, expected), 0)
        for bad in (float('nan'), float('inf'), -float('inf')):
            actual = expected.copy()
            actual[100] = bad
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    qualify909.port_error(actual, expected)
                with self.assertRaises(ValueError):
                    qualify909.port_error(expected, actual)
                with self.assertRaises(ValueError):
                    qualify909.measure(actual, expected)
        with self.assertRaises(AssertionError):
            qualify909.port_error(expected + .001, expected)
