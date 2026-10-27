import math
import unittest

from x0x import coupling808 as coupling


class Coupling808Tests(unittest.TestCase):
    def test_schematic_RC_and_step_transfer(self):
        self.assertAlmostEqual(coupling.TAU,.047)
        self.assertAlmostEqual(coupling.CUTOFF,3.3862753849339433)
        actual=coupling.filter_reference([.25]*24000)
        expected=[.25*coupling.B*coupling.A**n for n in range(len(actual))]
        self.assertLess(max(abs(a-b) for a,b in zip(actual,expected)),1e-12)
        self.assertLess(abs(actual[-1]),1e-5)

    def test_low_frequency_response_matches_bilinear_RC(self):
        n=48000
        for frequency in (2,55):
            samples=[.25*math.sin(2*math.pi*frequency*i/48000) for i in range(2*n)]
            filtered=coupling.filter_reference(samples)[n:]
            amplitude=2*abs(sum(y*complex(math.cos(2*math.pi*frequency*i/48000),
                                         math.sin(2*math.pi*frequency*i/48000))
                                for i,y in enumerate(filtered)))/n
            omega=96000*math.tan(math.pi*frequency/48000)
            expected=.25*omega*coupling.TAU/math.sqrt(1+(omega*coupling.TAU)**2)
            self.assertAlmostEqual(amplitude,expected,places=10)

    def test_DC_is_removed_and_invalid_samples_are_rejected(self):
        samples=coupling.filter_reference([.25]*96000+[-.25]*96000)
        self.assertLess(abs(samples[95999]),1e-12)
        self.assertLess(abs(samples[-1]),1e-12)
        self.assertLessEqual(max(map(abs,samples)),.5)
        for bad in (float('nan'),float('inf')):
            with self.assertRaises(ValueError): coupling.filter_reference([0,bad])
