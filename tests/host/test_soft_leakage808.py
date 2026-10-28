import math
import unittest

from x0x import body808, leakage808, pulse808, retrigger808
from x0x import soft_leakage808 as soft


def capacitor_reference(frames, raw, subdivisions=8):
    """Independent capacitor-coordinate KCL with continuously evaluated sources."""
    a=1/(retrigger808.R167*retrigger808.C41)
    sigma=-48000*math.log(body808.retention(raw))
    q1=q2=0.;main=14/60;companion=.71/60;values=[]
    dt=1/(48000*subdivisions)
    for sample in range(frames):
        if sample==48:main=-.71/60
        if sample==288:companion-=.25
        attack=sample<288
        omega=2*math.pi*(body808.ATTACK_FREQUENCY if attack else body808.FREQUENCY)
        g=(sigma*sigma+omega*omega)/a
        equilibrium=pulse808.ON_EQUILIBRIUM if sample<48 else 0.
        def derivative(x,y,t):
            u=equilibrium+(main-equilibrium)*math.exp(-t/pulse808.TAU)
            r=companion*math.exp(-t/retrigger808.TAU)
            current=0. if attack else soft.collector_current((u-x)*60)
            leak=(47000/53800)/15e-9*current/60
            return -a*(x+y),(g+a-2*sigma)*x+(a-2*sigma)*y-(g+2*a-2*sigma)*u+a*r-leak
        for sub in range(subdivisions):
            t=sub*dt
            k1=derivative(q1,q2,t)
            k2=derivative(q1+dt*k1[0]/2,q2+dt*k1[1]/2,t+dt/2)
            k3=derivative(q1+dt*k2[0]/2,q2+dt*k2[1]/2,t+dt/2)
            k4=derivative(q1+dt*k3[0],q2+dt*k3[1],t+dt)
            q1+=dt*(k1[0]+2*k2[0]+2*k3[0]+k4[0])/6
            q2+=dt*(k1[1]+2*k2[1]+2*k3[1]+k4[1])/6
        main=equilibrium+(main-equilibrium)*math.exp(-1/(48000*pulse808.TAU))
        companion*=math.exp(-1/(48000*retrigger808.TAU))
        values.append(main-q1-q2)
    return values


class SoftLeakage808Tests(unittest.TestCase):
    def test_published_current_and_asymptote_without_zero_subtraction(self):
        self.assertEqual((soft.ALPHA,soft.KNEE_V,soft.SLOPE),(14.315,-.556,1.4765e-5))
        self.assertAlmostEqual(soft.collector_current(soft.KNEE_V),-soft.SLOPE/soft.ALPHA*math.log(2),places=18)
        self.assertLess(soft.collector_current(0),0)
        for volts in(-10,-1,-.556,0,.5,10):
            x=-soft.ALPHA*(volts-soft.KNEE_V)
            expected=-soft.SLOPE/soft.ALPHA*math.log1p(math.exp(x))
            self.assertAlmostEqual(soft.collector_current(volts),expected,places=18)
            hard=soft.SLOPE*min(volts-soft.KNEE_V,0)
            self.assertLessEqual(soft.collector_current(volts),hard)
        for volts in(-1e308,1e308):
            self.assertTrue(math.isfinite(soft.collector_current(volts)))
            self.assertTrue(0<=soft.collector_slope(volts)<=soft.SLOPE)

    def test_independent_capacitor_kcl_matches_modal_ode(self):
        for raw in(0,8192,16384,32512):
            actual=soft.reference(6144,raw)
            independent=capacitor_reference(6144,raw)
            self.assertLess(max(abs(a-b) for a,b in zip(actual,independent)),1e-7)

    def test_refinement_preserves_excitation_and_live_control_policy(self):
        for raw in(0,16384,32512):
            prefix=soft.reference(288,raw)
            self.assertEqual(prefix,leakage808.reference(288,raw))
        changes={3200:8193,8000:12288,16000:24576}
        coarse=soft.reference(24000,4096,changes)
        fine=soft.reference(24000,4096,changes,subdivisions=8)
        self.assertLess(max(abs(a-b) for a,b in zip(coarse,fine)),1e-7)

    def test_quiet_bias_has_zero_output_but_zero_state_is_not_equilibrium(self):
        self.assertEqual(body808.FREQUENCY,47.65)
        for raw in(0,8192,16384,32512):
            state=soft.quiet_state(raw)
            self.assertEqual(state.real,0)
            self.assertGreater(state.imag,0)
            values,end=soft.continue_reference(state,0.,0.,raw,2048)
            self.assertLess(max(map(abs,values)),1e-15)
            self.assertLess(abs(end[0]-state),1e-15)
            transient,_=soft.continue_reference(0j,0.,0.,raw,1024)
            self.assertLess(transient[0],0.)
            self.assertGreater(max(map(abs,transient)),0.)
            sigma,omega,a,cw,cy=soft._parameters(raw)
            q1=-cw*state.real-cy*state.imag
            current=soft.collector_current(-q1/soft.SCALE)
            self.assertAlmostEqual((sigma*sigma+omega*omega)/a*q1-soft.RATIO/soft.C42*soft.SCALE*current,0.,places=15)
            derivative=soft.RATIO/soft.C42*soft.collector_slope(-q1/soft.SCALE)
            j00,j01=-a,-a
            j10,j11=(sigma*sigma+omega*omega)/a+a-2*sigma+derivative,a-2*sigma
            pole=soft.quiet_pole(raw)
            self.assertAlmostEqual(pole.real,(j00+j11)/2,places=12)
            self.assertAlmostEqual(pole.imag,math.sqrt(j00*j11-j01*j10-pole.real**2),places=12)
            self.assertGreater(pole.imag/(2*math.pi),body808.FREQUENCY)

    def test_invalid_inputs_are_rejected(self):
        for voltage in(float('nan'),float('inf'),-float('inf')):
            with self.assertRaises(ValueError):soft.collector_current(voltage)
        for raw in(-1,32513,True,.5):
            with self.assertRaises(ValueError):soft.reference(1,raw)
        for frames in(-1,True,.5):
            with self.assertRaises(ValueError):soft.reference(frames)
        for count in(0,-1,True,.5):
            with self.assertRaises(ValueError):soft.reference(1,subdivisions=count)
        with self.assertRaises(ValueError):soft.continue_reference(0j,float('nan'),0.,16384,1)
