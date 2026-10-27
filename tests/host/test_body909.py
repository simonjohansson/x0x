import math
import unittest

from x0x import body909 as body, tune909, vca909
from x0x.analysis import analyze


class Body909Tests(unittest.TestCase):
    def test_body_combines_tune_and_finite_loaded_vca_without_changing_reset(self):
        samples = body.reference(48000)
        report = analyze(samples,body.SAMPLE_RATE)
        self.assertIsNotNone(report["frequency"]["median_hz"])
        short = body.reference(1001,0)
        long = body.reference(1001,32512)
        short_gain=vca909.gain(vca909.envelope(1001,0)[-1])
        long_gain=vca909.gain(vca909.envelope(1001,32512)[-1])
        self.assertAlmostEqual(short[1000]/long[1000],short_gain/long_gain,places=12)
        peak_gain=max(map(vca909.gain,vca909.envelope(48000)))
        self.assertGreater(report["peak_fs"],0)
        self.assertLessEqual(report["peak_fs"],body.GAIN*peak_gain*body.diode_shape(1))
        self.assertEqual(body.reference(32),samples[:32])
        self.assertEqual(report["onset_sample"],0)
        self.assertGreater(samples[0],0)

    def test_body_continuation_preserves_independent_tune_and_envelope_history(self):
        expected=body.reference(6144,32512,tune_raw=0,tune_changes={32:32512,160:0})
        state=body.INITIAL_STATE
        result=[]
        for sample in range(0,6144,32):
            raw=0 if sample<32 or sample>=160 else 32512
            chunk,state=body.continue_reference(state,32512,raw,32)
            result.extend(chunk)
        self.assertLess(max(abs(a-b) for a,b in zip(result,expected)),1e-12)

    def test_triangle_has_odd_harmonics_distinct_from_the_808_sine(self):
        n=4800
        samples=[body.triangle(5*i/n) for i in range(n)]
        def amplitude(harmonic):
            return 2*abs(sum(y*complex(math.cos(2*math.pi*harmonic*5*i/n),
                                       math.sin(2*math.pi*harmonic*5*i/n))
                             for i,y in enumerate(samples)))/n
        fundamental=amplitude(1)
        self.assertAlmostEqual(fundamental,8/math.pi**2,delta=1e-5)
        self.assertAlmostEqual(amplitude(3)/fundamental,1/9,delta=1e-5)
        self.assertAlmostEqual(amplitude(5)/fundamental,1/25,delta=1e-5)
        self.assertLess(amplitude(2),1e-12)

    def test_diode_voltage_satisfies_independent_loaded_circuit_kcl(self):
        for value in (-1,-.9,-.5,-.01,0,.01,.5,.9,1):
            node=body.diode_shape(value)*body.LINEAR_VOLTS
            current=(body.TRIANGLE_VOLTS*value-node)/10000
            load=node/2247
            diode=2e-9*math.sinh(node/.052)
            self.assertAlmostEqual(current,load+diode,delta=1e-15)
            lo,hi=0.,abs(value)*body.LINEAR_VOLTS
            for _ in range(80):
                mid=(lo+hi)/2
                if mid+body.THEVENIN_OHMS*2e-9*math.sinh(mid/.052)>abs(value)*body.LINEAR_VOLTS:
                    hi=mid
                else:
                    lo=mid
            self.assertAlmostEqual(abs(node),(lo+hi)/2,delta=1e-13)
        self.assertGreater(body.diode_shape(1)*body.LINEAR_VOLTS,.5)
        self.assertLess(body.diode_shape(1)*body.LINEAR_VOLTS,.6)
        for value in (-1.01,1.01,float('nan'),True,'0'):
            with self.assertRaises(ValueError): body.diode_shape(value)

    def test_cubic_cpu_curve_is_bounded_monotone_and_matches_kcl_root(self):
        rows=body.shaper_coefficients()
        worst,previous=0.,0.
        for i in range(10001):
            x=i/10000
            index=min(int(x*16),15)
            t=x*16-index
            a,b,c,d=rows[index]
            actual=((d*t+c)*t+b)*t+a
            self.assertGreaterEqual(actual,previous-1e-15)
            self.assertLessEqual(actual,x+1e-15)
            self.assertAlmostEqual(body.diode_shape(-x),-body.diode_shape(x),delta=1e-15)
            worst=max(worst,abs(actual-body.diode_shape(x)))
            previous=actual
        self.assertLess(worst,6e-6)
        for left,right in zip(rows,rows[1:]):
            a,b,c,d=left
            self.assertAlmostEqual(a+b+c+d,right[0],places=14)
            self.assertAlmostEqual(b+2*c+3*d,right[1],places=14)

    def test_diode_rounding_reduces_triangle_third_harmonic_before_envelope(self):
        n=960
        shaped=[body.shaped_triangle(i/n) for i in range(n)]
        def magnitude(harmonic):
            return abs(sum(v*complex(math.cos(2*math.pi*harmonic*i/n),math.sin(2*math.pi*harmonic*i/n))
                           for i,v in enumerate(shaped)))
        self.assertLess(magnitude(3)/magnitude(1),1/9)
        self.assertLess(magnitude(2)/magnitude(1),1e-12)
        # The shaper stays at its fixed oscillator operating point as the VCA falls.
        sample=119
        wave=body.reference(sample+1,32512)
        expected=body.GAIN*vca909.gain(vca909.envelope(sample+1,32512)[-1])*body.shaped_triangle(tune909.reference(sample+1)[0][-1])
        self.assertAlmostEqual(wave[sample],expected,places=13)


class Decay909Tests(unittest.TestCase):
    def test_unloaded_RC_values_and_fractional_control(self):
        self.assertAlmostEqual(body.decay_tau(0),.01551)
        self.assertAlmostEqual(body.decay_tau(32512),.34551)
        self.assertAlmostEqual(body.decay_tau(16384),.1818092125984252)
        self.assertLess(body.decay_tau(16384),body.decay_tau(16385))
        for raw in (-1,32513,True,64.5):
            with self.assertRaises(ValueError): body.decay_tau(raw)

    def test_live_decay_preserves_phase_and_accumulated_envelope(self):
        switch=1024
        baseline=body.reference(4096,0)
        actual=body.reference(4096,0,{switch:32512})
        self.assertEqual(actual[:switch],baseline[:switch])
        n=2048
        c8=vca909.envelope(n+1,0,{switch:32512})[-1]
        expected=body.GAIN*vca909.gain(c8)*body.shaped_triangle(tune909.reference(n+1)[0][-1])
        self.assertAlmostEqual(actual[n],expected,places=12)
        self.assertGreater(abs(actual[n]),abs(baseline[n]))
