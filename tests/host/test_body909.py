import math
import unittest

from x0x import body909 as body
from x0x.analysis import analyze


class Body909Tests(unittest.TestCase):
    def test_triangle_frequency_scale_decay_and_reset_baseline(self):
        samples = body.reference(48000)
        report = analyze(samples,body.SAMPLE_RATE)
        self.assertAlmostEqual(report["frequency"]["median_hz"],body.FREQUENCY,delta=.001)
        self.assertAlmostEqual(report["decay_positive"]["time_constant_s"],body.TAU,delta=1e-5)
        self.assertGreater(report["peak_fs"],body.GAIN*body.diode_shape(1)*.97)
        self.assertLess(report["peak_fs"],body.GAIN*body.diode_shape(1))
        self.assertEqual(body.reference(32),samples[:32])
        self.assertEqual(report["onset_sample"],0)
        self.assertGreater(samples[0],0)

    def test_triangle_has_odd_harmonics_distinct_from_the_808_sine(self):
        n=4800
        samples=[body.triangle(body.FREQUENCY*i/body.SAMPLE_RATE) for i in range(n)]
        def amplitude(harmonic):
            return 2*abs(sum(y*complex(math.cos(2*math.pi*harmonic*body.FREQUENCY*i/body.SAMPLE_RATE),
                                       math.sin(2*math.pi*harmonic*body.FREQUENCY*i/body.SAMPLE_RATE))
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
        expected=body.GAIN*math.exp(-(sample+1)/(48000*body.decay_tau(32512)))*body.shaped_triangle((sample+1)/960)
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
        expected=body.GAIN*math.exp(-switch/(48000*body.decay_tau(0))
            -(n+1-switch)/(48000*body.decay_tau(32512)))*body.shaped_triangle(50*(n+1)/48000)
        self.assertAlmostEqual(actual[n],expected,places=12)
        self.assertGreater(abs(actual[n]),abs(baseline[n]))
