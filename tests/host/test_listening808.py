import base64
import io
import json
from pathlib import Path
import tempfile
import unittest
from x0x import listening808, fit808

class Listening808Tests(unittest.TestCase):
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

    def test_listening_wavs_keep_relative_gain_and_trigger_timing(self):
        np = self.np
        r, p = np.zeros(fit808.FRAMES), np.zeros(fit808.FRAMES)
        r[7], p[7] = .01, .012
        with tempfile.TemporaryDirectory() as folder:
            gain = listening808.listening_report(Path(folder), [{'tone_cc': 0, 'decay_cc': 0}],
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
            gain = listening808.listening_report(Path(folder), [{'tone_cc': 0, 'decay_cc': 0}],
                {(0, 0): r}, {(0, 0): p}, {})
        self.assertAlmostEqual(gain, 1.9)
        self.assertEqual((p[0] * gain) / (r[0] * gain), 2.5)
