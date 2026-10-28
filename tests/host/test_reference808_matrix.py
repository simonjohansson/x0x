import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from x0x.reference808_matrix import result, write_report


class Reference808MatrixTests(unittest.TestCase):
    def test_boundary_passes_and_small_misses_keep_their_margin(self):
        for actual in (-2, 2):
            r = result(actual, 0, 2, 'dB')
            self.assertEqual((r['status'], r['margin']), ('pass', 0))
        r = result(2.003, 0, 2, 'dB')
        self.assertEqual(r['status'], 'fail')
        self.assertAlmostEqual(r['margin'], -.003)
        r = result(422, 442, 44.2, 'ms', before_error=-72)
        self.assertEqual(r['status'], 'pass')
        self.assertAlmostEqual(r['margin'], 24.2)
        self.assertEqual(r['before_error'], -72)

    def test_quiet_and_missing_measurements_are_never_passes(self):
        self.assertEqual(result(.1, 0, 2, 'dB', eligible=False)['status'], 'quiet')
        r = result(None, 0, 50, 'cents', kind='diagnostic')
        self.assertEqual(r['status'], 'unresolved')
        self.assertIsNone(r['margin'])
        self.assertEqual(r['kind'], 'diagnostic')

    def test_nonfinite_evidence_and_invalid_limits_are_rejected(self):
        for value in (float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                result(value, 0, 2, 'dB')
        for limit in (0, -1, float('inf')):
            with self.assertRaises(ValueError):
                result(0, 0, limit, 'dB')

    def test_embedded_data_cannot_close_the_script_element(self):
        data = dict(commit='a'*40, counts={'pass': 1}, note='</script><script>alert(1)</script>')
        with tempfile.TemporaryDirectory() as directory, patch('x0x.reference808_matrix.build_data', return_value=data):
            with contextlib.redirect_stdout(io.StringIO()):
                write_report(Path('unused'), Path(directory))
            page = (Path(directory)/'index.html').read_text()
            payload = page.split('<script id="data" type="application/json">', 1)[1].split('</script>', 1)[0]
            self.assertNotIn('<', payload)
            self.assertEqual(json.loads(payload), data)
            self.assertNotIn('__MATRIX_DATA__', page)
