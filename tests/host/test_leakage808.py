import math
from pathlib import Path
import re
import unittest

from x0x import body808, leakage808 as leakage, pulse808, retrigger808


class Leakage808Tests(unittest.TestCase):
    def test_cubic_coefficient_remainder_improves_existing_model_precision(self):
        source = (Path(__file__).resolve().parents[2] / 'targets/coldfire/body808.s').read_text()
        for label, lo, hi in (('low', 0, 16384), ('high', 16384, 32512)):
            block = source.split(f'.Lleakage_{label}_data:\n')[1].split('\n.')[0]
            table = [[int(word) / 2**31 for word in line.split(',')]
                     for line in re.findall(r'\.long ([^\n]+)', block)]
            self.assertEqual([len(row) for row in table], [4, 4, 4])
            old_error = new_error = 0.
            left, right = body808.retention(lo), body808.retention(hi)
            for raw in range(lo, hi + 1, 17):
                t = (body808.retention(raw) - left) / (right - left)
                exact = leakage.coefficients(raw)
                for index, (a, b, c, d) in enumerate(table):
                    target = exact[(0, 1, 3)[index]]
                    old = a + b * t + c * t * (1 - t)
                    new = old + d * t * (1 - t) * (t - .5)
                    old_error = max(old_error, abs(old - target))
                    new_error = max(new_error, abs(new - target))
            self.assertLess(new_error, old_error / 10)

    def test_hard_knee_sign_and_half_kick_match_configured_capacitor_kcl(self):
        self.assertEqual(leakage.KNEE,-.018011980654046803)
        self.assertEqual(leakage.LEAK_RATE,2933.2119129807006)
        self.assertEqual(leakage.half_kick(0j,0.,16384),0j)
        for raw in (0,16384,32512):
            cw,cy,gain,n = leakage.coefficients(raw)
            state,main = complex(.02,-.2),0.
            q1 = -cw*state.real-cy*state.imag
            common = main-q1
            after = leakage.half_kick(state,main,raw)
            self.assertAlmostEqual(-cw*after.real-cy*after.imag,q1,places=14)
            ic = leakage.SLOPE*min(common*60-leakage.KNEE_V,0.)
            delta_q2 = -(leakage.R165/(leakage.R165+leakage.R166)/15e-9)*ic/60/(2*48000)
            self.assertAlmostEqual(after.real-state.real,-delta_q2,places=14)
            self.assertAlmostEqual(after.imag-state.imag,n*delta_q2,places=14)
            self.assertLess(after.real,state.real)
            # Eq9's resistance form agrees away from zero; KCL itself never divides by Vcomm.
            volts = common*60
            resistance = volts*6800*53800/(volts*53800-47000*(volts-6800*ic))
            self.assertAlmostEqual(1/resistance,1/53800+47000/53800*ic/volts,places=14)

    def test_strang_candidate_matches_independent_continuous_ode_with_live_controls(self):
        for raw in (0,1,8192,16383,16384,24576,32511,32512):
            changes = {256:32512,288:raw,320:raw,8000:0,16000:32512}
            exact = leakage.reference(24000,raw,changes)
            candidate = leakage.reference(24000,raw,changes,split=True)
            self.assertLess(max(abs(a-b) for a,b in zip(exact,candidate)),1e-5)

    def test_no_attack_leakage_and_quiet_body_returns_to_settled_pitch(self):
        for raw in (0,16384,32512):
            before = [a+b for a,b in zip(pulse808.main_reference(288,raw),
                                        retrigger808.companion_body_reference(288,raw))]
            after = leakage.reference(288,raw)
            self.assertLess(max(abs(a-b) for a,b in zip(before,after)),1e-12)
            samples = leakage.reference(96000,raw)
            self.assertLess(max(map(abs,samples)),.25)
            self.assertLess(max(map(abs,samples[-4800:])),.0015)
            # Once Vcomm no longer reaches the knee, no imposed pitch envelope remains.
            at = 72000
            theta = 2*math.pi*body808.FREQUENCY/48000
            rho = body808.retention(raw)
            self.assertLess(max(abs(samples[i+2]-2*rho*math.cos(theta)*samples[i+1]
                                    +rho*rho*samples[i]) for i in range(at,at+1000)),1e-10)

    def test_coefficient_range_has_fixed_effective_parameters_and_refinement_converges(self):
        gain = leakage.LEAK_RATE/(2*48000)
        for raw in range(32513):
            cw,cy,g,n = leakage.coefficients(raw)
            self.assertGreater(min(cw,cy,g,n),0.)
            self.assertLess(max(cw,cy,g,n),1.)
            self.assertEqual(g,gain)
            self.assertAlmostEqual(cw,cy*n,places=14)
        for raw in (0,4096,8192,12288,16384,20224,24320,28416,32512):
            coarse = leakage.reference(24000,raw)
            fine = leakage.reference(24000,raw,subdivisions=16)
            self.assertLess(max(abs(a-b) for a,b in zip(coarse,fine)),1e-7)

    def test_native_snapshot_continuation_matches_fresh_reference_and_chunking(self):
        for raw in (0,16384,32512):
            sigma = -48000*math.log(body808.retention(raw))
            omega = 2*math.pi*body808.ATTACK_FREQUENCY
            a = 1/(1e6*15e-9)
            pole = complex(-sigma,-omega)
            main_gain = ((sigma*sigma+omega*omega)/a+2*a-2*sigma)*complex(1,-sigma/omega)
            companion_gain = complex(-a,a*sigma/omega)
            state,main,companion = 0j,14/60,.71/60
            # Independently integrate the attack to obtain a realistic mid-state.
            for sample in range(288):
                if sample == 48:
                    main = -.71/60
                equilibrium = pulse808.ON_EQUILIBRIUM if sample < 48 else 0.
                def derivative(z,t):
                    u = equilibrium+(main-equilibrium)*math.exp(-t/pulse808.TAU)
                    r = companion*math.exp(-t/.033)
                    return pole*z+main_gain*u+companion_gain*r
                dt = 1/(48000*16)
                for sub in range(16):
                    t = sub*dt
                    k1 = derivative(state,t)
                    k2 = derivative(state+dt*k1/2,t+dt/2)
                    k3 = derivative(state+dt*k2/2,t+dt/2)
                    k4 = derivative(state+dt*k3,t+dt)
                    state += dt*(k1+2*k2+2*k3+k4)/6
                main = equilibrium+(main-equilibrium)*math.exp(-1/(48000*pulse808.TAU))
                companion *= math.exp(-1/(48000*.033))
            alpha,beta = body808.switch_coordinates(raw)
            state = complex(state.real,alpha*state.imag+beta*state.real)
            companion -= .25
            actual,final = leakage.continue_reference(state,main,companion,raw,512)
            fresh = leakage.reference(800,raw)[288:]
            self.assertLess(max(abs(a-b) for a,b in zip(actual,fresh)),1e-10)
            first,middle = leakage.continue_reference(state,main,companion,raw,256)
            second,end = leakage.continue_reference(*middle,raw,256)
            self.assertEqual(actual,first+second)
            self.assertEqual(final,end)

    def test_invalid_controls_and_frame_counts_are_rejected(self):
        for raw in (-1,32513,True,.5):
            with self.assertRaises(ValueError): leakage.coefficients(raw)
        for frames in (-1,True,.5):
            with self.assertRaises(ValueError): leakage.reference(frames)
        for subdivisions in (0,-1,True,.5):
            with self.assertRaises(ValueError): leakage.reference(1,subdivisions=subdivisions)
        with self.assertRaises(ValueError): leakage.continue_reference(0j,float('nan'),0.,16384,32)
