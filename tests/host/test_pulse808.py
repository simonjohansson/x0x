import cmath
import math
import unittest

from x0x import body808, pulse808 as pulse


class MainPulse808Tests(unittest.TestCase):
    def test_fresh_pulse_has_the_passive_shelf_and_negative_charge_clamp(self):
        self.assertAlmostEqual(pulse.TAU, 67.335243553e-6, places=14)
        self.assertAlmostEqual(pulse.DC_GAIN, 4700/104700, places=14)
        self.assertEqual(pulse.shaped_voltage(0),14/60)
        self.assertEqual(pulse.shaped_voltage(48),-.71/60)
        before = pulse.ON_EQUILIBRIUM+(14/60-pulse.ON_EQUILIBRIUM)*math.exp(-.001/pulse.TAU)
        self.assertLess(before-14/60,-.71/60)
        for n in (49,64,100,288):
            self.assertAlmostEqual(pulse.shaped_voltage(n),-.71/60*math.exp(-(n-48)/(48000*pulse.TAU)),places=14)
        # Output clipping without changing charge would have a different falling tail.
        self.assertNotEqual(pulse.shaped_voltage(64),max((before-14/60)*math.exp(-16/(48000*pulse.TAU)),-.71/60))

    def test_integrated_input_coefficients_recover_the_main_transfer_function(self):
        a = 1/(1e6*15e-9)
        for raw in (0,8192,16384,24576,32512):
            sigma = -48000*math.log(body808.retention(raw))
            for attack in (False,True):
                omega = 2*math.pi*(body808.ATTACK_FREQUENCY if attack else body808.FREQUENCY)
                gain = (sigma*sigma+omega*omega)/a+2*a-2*sigma
                gx,gy,bx,by = pulse.step_coefficients(raw,attack)
                constant = complex(gx,gy)+complex(bx,by)/pulse.ON_EQUILIBRIUM
                q = cmath.exp(complex(-sigma,-omega)/48000)
                state = 0j
                for n in range(288):
                    state = q*state+constant
                    t = (n+1)/48000
                    expected = 1+gain*math.exp(-sigma*t)*math.sin(omega*t)/omega
                    self.assertAlmostEqual(1+state.real,expected,places=11)

    def test_main_reference_matches_the_charge_and_bridge_odes(self):
        changes = {256:32512,288:0,320:16384}
        actual = pulse.main_reference(2048,0,changes)
        state,node,raw,worst = 0j,14/60,0,0.
        a = 1/(1e6*15e-9)
        for n in range(2048):
            if n == 48:
                node = max(node-14/60,-.71/60)
            if n == 288:
                alpha,beta = body808.switch_coordinates(raw)
                state = complex(state.real,alpha*state.imag+beta*state.real)
            raw = changes.get(n,raw)
            sigma = -48000*math.log(body808.retention(raw))
            omega = 2*math.pi*(body808.ATTACK_FREQUENCY if n < 288 else body808.FREQUENCY)
            gain = (sigma*sigma+omega*omega)/a+2*a-2*sigma
            pole,forcing = complex(-sigma,-omega),gain*complex(1,-sigma/omega)
            equilibrium = 14/60*4700/104700 if n < 48 else 0.
            def derivative(z,u):
                return pole*z+forcing*u,(equilibrium-u)/pulse.TAU
            dt = 1/(48000*32)
            for _ in range(32):
                k1,u1 = derivative(state,node)
                k2,u2 = derivative(state+dt*k1/2,node+dt*u1/2)
                k3,u3 = derivative(state+dt*k2/2,node+dt*u2/2)
                k4,u4 = derivative(state+dt*k3,node+dt*u3)
                state += dt*(k1+2*k2+2*k3+k4)/6
                node += dt*(u1+2*u2+2*u3+u4)/6
            worst = max(worst,abs(state.real+node-actual[n]))
        self.assertLess(worst,1e-9)
