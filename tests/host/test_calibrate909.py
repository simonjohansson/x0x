import unittest

from x0x import body909
from x0x.calibrate909 import WORDS, carrier, envelope, mapped, search


class Calibration909Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy as np
        except ImportError:
            raise unittest.SkipTest('requires existing numpy research environment')
        cls.np=np

    def test_identity_mapping_and_monotonic_interpolated_mapping(self):
        for word in (0,1,8192,12345,16384,24320,32512):
            self.assertEqual(mapped(word,WORDS),word)
        values=[mapped(word,(100,5000,15000,24000,32512)) for word in range(0,32513,32)]
        self.assertEqual(values,sorted(values))
        for bad in ((0,1,2,3),(-1,1,2,3,4),(0,10,5,20,30),(0,1,2,3,32513)):
            with self.assertRaises(ValueError):mapped(0,bad)

    def test_factorized_fit_render_matches_existing_renderer(self):
        for tune,decay in ((0,0),(16384,16384),(32512,8192)):
            expected=body909.reference(24000,decay,tune_raw=tune)
            self.np.testing.assert_allclose(carrier(tune)*envelope(decay),expected,atol=1e-14,rtol=0)

    def test_integer_search_keeps_baseline_and_finds_known_bounded_optimum(self):
        word,loss,_=search(lambda v:(v-12345)**2,0,32512,16384)
        self.assertEqual((word,loss),(12345,0))
        self.assertEqual(search(lambda v:1,0,32512,8192)[0],8192)
        self.assertEqual(search(lambda v:-v,0,100,50)[0],100)


if __name__=='__main__':
    unittest.main()
