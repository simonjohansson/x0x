import math
import unittest

from x0x import body808, retrigger808 as retrigger


class Retrigger808Tests(unittest.TestCase):
    def test_companion_body_matches_the_inverse_laplace_response(self):
        k, lam = 1/(1e6*15e-9), 1/.033
        drive = .71*retrigger.VOLT_SCALE
        omega = 2*math.pi*body808.ATTACK_FREQUENCY
        for raw in (0,16384,32512):
            sigma = -48000*math.log(body808.retention(raw))
            a = k*drive*lam/((sigma-lam)**2+omega**2)
            c = -k*drive-a*(sigma-lam)
            actual = retrigger.companion_body_reference(288,raw)
            for n,value in enumerate(actual):
                t = (n+1)/48000
                expected = a*math.exp(-lam*t)+math.exp(-sigma*t)*(
                    -a*math.cos(omega*t)+c/omega*math.sin(omega*t))
                self.assertAlmostEqual(value,expected,places=13)
            self.assertLess(actual[0],0)  # Positive source enters the negative band-pass channel.

    def test_companion_with_live_decay_matches_an_independent_ode_solver(self):
        changes = {256:32512,288:0,320:16384,3200:32512}
        actual = retrigger.companion_body_reference(4096,0,changes)
        state,raw,worst = 0j,0,0.
        lam,k = 1/.033,1/(1e6*15e-9)
        first = .71*retrigger.VOLT_SCALE
        fall = first*math.exp(-288/(48000*.033))-.25
        for n in range(4096):
            if n == 288:
                a,b = body808.switch_coordinates(raw)
                state = complex(state.real,a*state.imag+b*state.real)
            raw = changes.get(n,raw)
            sigma = -48000*math.log(body808.retention(raw))
            omega = 2*math.pi*(body808.ATTACK_FREQUENCY if n < 288 else body808.FREQUENCY)
            source = first if n < 288 else fall
            origin = 0 if n < 288 else 288
            def derivative(z,t):
                node = source*math.exp(-lam*(t-origin/48000))
                return complex(-sigma,-omega)*z+complex(-k,k*sigma/omega)*node
            dt = 1/(48000*4)
            for j in range(4):
                t = n/48000+j*dt
                a = derivative(state,t)
                b = derivative(state+dt*a/2,t+dt/2)
                c = derivative(state+dt*b/2,t+dt/2)
                d = derivative(state+dt*c,t+dt)
                state += dt*(a+2*b+2*c+d)/6
            worst = max(worst,abs(state.real-actual[n]))
        self.assertLess(worst,1e-11)

    def test_composed_body_keeps_headroom_with_one_fixed_voltage_scale(self):
        self.assertEqual(retrigger.ENVELOPE_V*retrigger.VOLT_SCALE,.25)
        for raw in range(0,32513,2032):
            samples = body808.reference(24000,raw)
            self.assertLess(max(map(abs,samples)),body808.GAIN)

    def test_polarity_capacitor_charge_and_both_envelope_edges(self):
        self.assertAlmostEqual(retrigger.TAU, .033)
        fall = body808.ATTACK_SAMPLES
        actual = retrigger.reference(48000)
        self.assertEqual(actual[0], .71)
        before = .71 * math.exp(-fall / (48000*.033))
        self.assertAlmostEqual(actual[fall-1], .71*math.exp(-(fall-1)/(48000*.033)), places=12)
        # The charged capacitor makes a large negative companion pulse, not a positive clip.
        self.assertAlmostEqual(actual[fall], before-15, places=12)
        self.assertLess(actual[fall], -14)
        for n in (fall+1, 2400, 4800, 23999):
            expected = (before-15) * math.exp(-(n-fall)/(48000*.033))
            self.assertAlmostEqual(actual[n], expected, places=12)
        self.assertLess(abs(actual[-1]), 1e-10)
        self.assertLessEqual(max(actual), .71)

    def test_unclipped_small_signal_has_the_linear_highpass_response(self):
        actual = retrigger.filter_reference([.25]*100 + [0.0]*200)
        for n, value in enumerate(actual):
            expected = .25*math.exp(-n/(48000*.033))
            if n >= 100:
                expected -= .25*math.exp(-(n-100)/(48000*.033))
            self.assertAlmostEqual(value, expected, places=13)

    def test_rate_change_preserves_physical_edge_times_and_RC_decay(self):
        a = retrigger.filter_reference([15.0]*288 + [0.0]*4512, 48000)
        b = retrigger.filter_reference([15.0]*576 + [0.0]*9024, 96000)
        self.assertLess(max(abs(x-y) for x,y in zip(a,b[::2])), 1e-11)

    def test_a_later_small_trigger_retains_charge_history(self):
        first = [.25]*100 + [0.0]*100
        combined = retrigger.filter_reference(first + [.25]*32)
        fresh = retrigger.filter_reference([.25]*32)
        self.assertNotEqual(combined[200:], fresh)
        expected = fresh[0] + retrigger.filter_reference(first+[0.0])[200]
        self.assertAlmostEqual(combined[200], expected, places=13)

    def test_invalid_inputs_do_not_become_valid_reference_samples(self):
        for rate in (0, -1, True, 48000.5):
            with self.assertRaises(ValueError): retrigger.filter_reference([0],rate)
        for sample in (float('nan'),float('inf'),-float('inf')):
            with self.assertRaises(ValueError): retrigger.filter_reference([0,sample])
        for frames in (-1,True,32.5):
            with self.assertRaises(ValueError): retrigger.reference(frames)

    def test_bridge_sources_have_different_numerators_and_volt_units(self):
        a = 1/(1e6*15e-9)
        g = 1/1e6 + 1/470e3 + 1/6800
        omega = math.sqrt(a*g/15e-9 - a*a)
        main = retrigger.bridge_reference([1.0]*288, [0.0]*288)
        companion = retrigger.bridge_reference([0.0]*288, [1.0]*288)
        for n in range(288):
            t = n/48000
            step = math.exp(-a*t)*math.sin(omega*t)/omega
            # Independent inverse Laplace of Eq.5 / Eq.7's R161/R170 swap.
            self.assertAlmostEqual(main[n], 1+(g/15e-9)*step, places=11)
            self.assertAlmostEqual(companion[n], -step/(1e6*15e-9), places=12)
        self.assertEqual(main[0], 1.0)  # The main source has direct feedthrough.
        self.assertEqual(companion[0], 0.0)
        self.assertLess(companion[1], 0.0)

    def test_bridge_frequency_switch_retains_physical_capacitor_charge(self):
        a, k, switch = 1/(1e6*15e-9), 1/(1e6*15e-9), .006
        ga = 1/1e6 + 1/470e3 + 1/6800
        gn = 1/1e6 + 1/470e3 + 1/53800
        wa = math.sqrt(a*ga/15e-9 - a*a)
        wn = math.sqrt(a*gn/15e-9 - a*a)
        at_switch = -k*math.exp(-a*switch)*math.sin(wa*switch)/wa
        c41 = -1/(1e6*ga)*(1-math.exp(-a*switch)*(
            math.cos(wa*switch)+a/wa*math.sin(wa*switch)))
        derivative = -gn/15e-9*c41 - 2*a*at_switch - k
        actual = retrigger.bridge_reference([0.0]*48000, [1.0]*48000)
        # Solve the second-order ODE with the post-switch slope, not a
        # retained modal quadrature whose meaning changes with frequency.
        for n in (288, 289, 500, 1000, 2400, 47999):
            dt = n/48000-switch
            expected = math.exp(-a*dt)*(at_switch*math.cos(wn*dt)
                +(derivative+a*at_switch)/wn*math.sin(wn*dt))
            self.assertAlmostEqual(actual[n], expected, places=12)
        self.assertAlmostEqual(actual[288], at_switch, places=12)
        self.assertLess(abs(actual[-1]), 1e-12)  # Companion path has zero DC gain.

    def test_companion_bridge_preserves_edge_times_across_sample_rates(self):
        pulse48 = retrigger.filter_reference([15.0]*288 + [0.0]*4512)
        pulse96 = [sample for sample in pulse48 for _ in range(2)]
        a = retrigger.bridge_reference([0.0]*4800, pulse48)
        b = retrigger.bridge_reference([0.0]*9600, pulse96, 96000)
        # Preserve the same held voltage waveform when changing sample rate.
        self.assertLess(max(abs(x-y) for x,y in zip(a,b[::2])), 1e-11)
        step48 = retrigger.bridge_reference([0.0]*4800, [1.0]*4800)
        step96 = retrigger.bridge_reference([0.0]*9600, [1.0]*9600, 96000)
        self.assertLess(max(abs(x-y) for x,y in zip(step48,step96[::2])), 1e-12)

    def test_bridge_is_linear_in_the_independent_voltage_sources(self):
        main = [math.sin(n*.07) for n in range(1000)]
        companion = retrigger.reference(1000)
        combined = retrigger.bridge_reference(main, companion)
        a = retrigger.bridge_reference(main, [0.0]*1000)
        b = retrigger.bridge_reference([0.0]*1000, companion)
        self.assertLess(max(abs(x-y-z) for x,y,z in zip(combined,a,b)), 1e-11)

    def test_bridge_rejects_invalid_inputs(self):
        for rate in (0,-1,True,48000.5):
            with self.assertRaises(ValueError): retrigger.bridge_reference([0],[0],rate)
        with self.assertRaises(ValueError): retrigger.bridge_reference([0],[])
        for invalid in (float('nan'),float('inf'),-float('inf')):
            with self.assertRaises(ValueError): retrigger.bridge_reference([invalid],[0])
            with self.assertRaises(ValueError): retrigger.bridge_reference([0],[invalid])
