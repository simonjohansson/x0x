import unittest

from x0x.interaction909 import body_attack, evaluation_mask, predict, score


class Interaction909Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy as np
        except ImportError:
            raise unittest.SkipTest('run this diagnostic with the existing numpy research environment')
        cls.np = np

    def test_single_curves_recover_additive_data_at_every_anchor(self):
        t, a, d = self.np.indices((3, 3, 3))
        values = (7 + t*t + 2*a + d*d*d)[..., None]
        for anchor in ((0, 0, 0), (1, 1, 1), (1, 0, 2)):
            self.np.testing.assert_array_equal(predict(values, anchor), values)

    def test_pairwise_recovers_cross_terms_but_cannot_hide_three_way_term(self):
        t, a, d = self.np.indices((3, 3, 3))
        pair = (5 + t + a + d + t*a + 2*t*d + a*d)[..., None]
        for anchor in ((0, 0, 0), (1, 1, 1), (1, 0, 2)):
            self.np.testing.assert_array_equal(predict(pair, anchor, True), pair)
            self.assertGreater(float(self.np.max(abs(predict(pair, anchor) - pair))), 0)
        triple = pair + (t*a*d)[..., None]
        error = triple - predict(triple, (0, 0, 0), True)
        self.np.testing.assert_array_equal(error[..., 0], t*a*d)

    def test_scored_settings_never_touch_any_calibration_plane(self):
        mask = evaluation_mask(9, (4, 0, 8))
        self.assertEqual(int(mask.sum()), 512)
        self.assertFalse(mask[4].any() or mask[:, 0].any() or mask[:, :, 8].any())

    def test_body_surface_and_attack_curve_need_no_other_pair_terms(self):
        t, a, d = self.np.indices((3, 3, 3))
        values = (3 + t*t*d + a*a)[..., None]
        for anchor in ((0, 0, 0), (1, 1, 1), (1, 0, 2)):
            self.np.testing.assert_array_equal(body_attack(values, anchor), values)

    def test_score_keeps_missing_pitch_missing_and_reports_known_error(self):
        actual = self.np.ones((3, 3, 3, 1)) * 2
        predicted = actual + 1
        actual[2, 2, 2] = self.np.nan
        result = score(predicted, actual, evaluation_mask(3, (0, 0, 0)))
        self.assertEqual(result['settings'], 7)
        self.assertEqual(result['rmse'], 1)
        self.assertEqual(result['relative_l2'], .5)


if __name__ == '__main__':
    unittest.main()
