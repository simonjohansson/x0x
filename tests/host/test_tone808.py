import math
import unittest

from x0x import tone808 as tone


class Tone808Tests(unittest.TestCase):
    def test_schematic_values_and_cutoff_endpoints(self):
        self.assertEqual(tone.resistance(0), 5220)
        self.assertEqual(tone.resistance(32512), 220)
        self.assertAlmostEqual(tone.cutoff(0), 304.8945269959681)
        self.assertAlmostEqual(tone.cutoff(32512), 7234.315595086152)
        self.assertLess(tone.coefficient(0), tone.coefficient(16384))
        self.assertLess(tone.coefficient(16384), tone.coefficient(32512))
        self.assertLess(tone.resistance(16385), tone.resistance(16384))
        for value in (-1,32513,True,64.5):
            with self.assertRaises(ValueError): tone.resistance(value)

    def test_step_matches_closed_form_bilinear_transfer(self):
        for raw in (0,16384,32512):
            g=tone.coefficient(raw)
            actual=tone.filter_reference([1.0]*512,raw)
            expected=[1-(1-g)*(1-2*g)**n for n in range(512)]
            self.assertLess(max(abs(a-b) for a,b in zip(actual,expected)),1e-12)
            self.assertAlmostEqual(actual[-1],1,places=8)

    def test_response_matches_analog_RC_at_bilinear_warped_frequency(self):
        rate=tone.SAMPLE_RATE
        frequency=1000
        samples=[math.sin(2*math.pi*frequency*n/rate) for n in range(4800)]
        for raw in (0,16384,32512):
            result=tone.filter_reference(samples,raw)[2400:]
            amplitude=2*abs(sum(y*complex(math.cos(-2*math.pi*frequency*n/rate),
                                         math.sin(-2*math.pi*frequency*n/rate))
                                for n,y in enumerate(result)))/len(result)
            omega=2*rate*math.tan(math.pi*frequency/rate)
            expected=1/math.sqrt(1+(omega*tone.resistance(raw)*tone.C45)**2)
            self.assertAlmostEqual(amplitude,expected,places=10)

    def test_live_change_preserves_capacitor_history(self):
        initial=tone.filter_reference([1.0]*8,0)
        changed=tone.filter_reference([1.0]*16,0,{8:32512})
        reset=tone.filter_reference([1.0]*8,32512)
        self.assertEqual(changed[:8],initial)
        self.assertNotAlmostEqual(changed[8],reset[0])
        self.assertTrue(all(0<x<=1 for x in changed))
