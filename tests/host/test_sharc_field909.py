"""Actual assembled 909, with the frozen mathematical model as its oracle."""
import itertools
import tempfile
import unittest
from pathlib import Path
import numpy as np
from x0x import field909 as model, sharc_field808 as dsp


class Sharc909Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory(prefix='x0x-sharc909-')
        cls.receipt, cls.artifact = dsp.build(Path(cls.folder.name))
        cls.model = model.load()

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def test_complete_hits_match_frozen_reference_at_corners_and_fractions(self):
        cases = list(itertools.product((0, 32512), repeat=3))
        cases += [(1, 255, 32511), (12345, 23001, 17001)]
        for tune, attack, decay in cases:
            with self.subTest(tune=tune, attack=attack, decay=decay):
                runner = dsp.Runner(self.receipt, self.artifact)
                actual = np.concatenate([runner.call(tune, decay, b == 0, model=32512, attack=attack)[0]
                                         for b in range(3000)])
                expected = 4 * model.render(self.model, tune, attack, decay)
                self.assertLess(float(abs(actual - expected).max()), 1e-5)
                self.assertEqual(runner.call(tune, decay, model=32512, attack=attack)[0], (0.,) * 32)
                self.assertEqual(runner.core.peek(self.receipt['state_base']), 96000)
                runner.check_tables()

    def test_all_controls_latch_and_model_changes_require_start(self):
        mixed = dsp.Runner(self.receipt, self.artifact)
        isolated = dsp.Runner(self.receipt, self.artifact)
        other = dsp.Runner(self.receipt, self.artifact)
        for b in range(100):
            expected = isolated.call(12345, 17001, b == 0, model=32512, attack=23001)[0]
            actual = mixed.call(12345 if b == 0 else 0, 17001 if b == 0 else 0,
                                b == 0, model=32512 if b == 0 else 0,
                                attack=23001 if b == 0 else 0)[0]
            self.assertEqual(actual, expected)
            self.assertEqual(mixed.call(32512, 0, b == 0, slot=15, attack=32512)[0],
                             other.call(32512, 0, b == 0, slot=15, attack=32512)[0])
        self.assertEqual(mixed.call(32512, 0, True, attack=0)[0], other.call(32512, 0, True)[0])
        self.assertEqual(mixed.call(12345, 17001, True, model=32512, attack=23001)[0],
                         isolated.call(12345, 17001, True, model=32512, attack=23001)[0])
        mixed.check_tables()

    def test_two_909_slots_keep_independent_complete_tails(self):
        mixed = dsp.Runner(self.receipt, self.artifact)
        left = dsp.Runner(self.receipt, self.artifact)
        right = dsp.Runner(self.receipt, self.artifact)
        for block in range(3066):
            self.assertEqual(mixed.call(12345, 17001, block == 0,
                                       model=32512, attack=23001)[0],
                             left.call(12345, 17001, block == 0,
                                       model=32512, attack=23001)[0])
            self.assertEqual(mixed.call(32512, 32512, block == 64, slot=15,
                                       model=32512, attack=0)[0],
                             right.call(32512, 32512, block == 64, slot=15,
                                        model=32512, attack=0)[0])
        for slot in (0, 15):
            self.assertEqual(mixed.core.peek(self.receipt['state_base'] + slot*dsp.STATE_BYTES),
                             96000)
        mixed.check_tables()

    def test_bad_attack_cannot_commit_selection_or_advance_state(self):
        runner = dsp.Runner(self.receipt, self.artifact)
        runner.call(16384, 16384, True)
        base = self.receipt['state_base']
        before = [runner.core.peek(base+i) for i in range(0, dsp.STATE_BYTES, 4)]
        for attack in (32513, 0xffffffff):
            self.assertEqual(runner.call(0, 0, True, model=32512, attack=attack)[0], (0.,)*32)
            self.assertEqual(before, [runner.core.peek(base+i) for i in range(0, dsp.STATE_BYTES, 4)])
        runner.call(0, 0, True, model=32512, attack=0)
        before = [runner.core.peek(base+i) for i in range(0, dsp.STATE_BYTES, 4)]
        self.assertEqual(runner.call(0, 0, model=32512, attack=32513)[0], (0.,)*32)
        self.assertEqual(before, [runner.core.peek(base+i) for i in range(0, dsp.STATE_BYTES, 4)])

    def test_codec_rejects_bad_geometry_and_controls(self):
        for values in ((-1, 0, 0), (0, float('nan'), 0), (0, 0, 32513)):
            with self.assertRaises(ValueError):model.render(self.model, *values)
        for frames in (0, 96001, True):
            with self.assertRaises(ValueError):model.render(self.model, 0, 0, 0, frames=frames)
        changed = dict(self.model);changed['onset_nodes'] = changed['onset_nodes'][:-1]
        path = Path(self.folder.name)/'corrupt.npz';np.savez(path, **changed)
        with self.assertRaises(ValueError):model.load(path)
        for raw in np.linspace(0, 32512, 129):
            phi, K, lam = model.parameters(self.model, raw)
            self.assertTrue(-.5 < phi < .5 and 0 < K < 8 and 0 < lam < .01)
