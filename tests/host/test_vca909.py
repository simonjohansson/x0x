import math
import unittest

from x0x import body909, vca909 as v


class Vca909Tests(unittest.TestCase):
    def test_switching_charge_current_matches_independent_two_node_kcl(self):
        vs,drop=14.8,.7
        for env in (0,.3,.6,1,v.DIVIDER_V,5,12,13,14.8):
            valid=[]
            for d8,d9 in ((False,False),(False,True),(True,False),(True,True)):
                if d8 and d9:
                    a,b=env+drop,env
                    i8=b/10000-(vs-b)/47000
                    i9=(vs-a)/1000-i8
                elif d8:
                    b=((vs-drop)/1000+vs/47000)/(1/1000+1/47000+1/10000)
                    a=b+drop;i8=(vs-a)/1000;i9=0.
                elif d9:
                    a=env+drop;b=vs*10000/57000;i8=0.;i9=(vs-a)/1000
                else:
                    a,b=vs,vs*10000/57000;i8=i9=0.
                if (i8>=-1e-15 if d8 else a-b<=drop+1e-14) and (i9>=-1e-15 if d9 else a-env<=drop+1e-14):
                    self.assertAlmostEqual((vs-a)/1000,i8+i9,delta=1e-15)
                    self.assertAlmostEqual((vs-b)/47000+i8,b/10000,delta=1e-15)
                    valid.append(i9)
            self.assertTrue(valid,env)
            self.assertAlmostEqual(v.drive_current(env,True),valid[0],delta=1e-15)
            self.assertEqual(v.drive_current(env,False),0)

    def test_loaded_discharge_crosses_physical_base_knee_then_keeps_capacitor_charge(self):
        for raw in (0,16384,32512):
            r=v.resistance(raw)
            loss=(1/r+1/470000)/.33e-6
            equilibrium=.6*r/(470000+r)
            initial=12.
            crossing=-math.log((.6-equilibrium)/(initial-equilibrium))/loss
            self.assertAlmostEqual(v.step(initial,raw,False,.01),equilibrium+(initial-equilibrium)*math.exp(-loss*.01),delta=1e-12)
            late=v.step(initial,raw,False,crossing+.01)
            self.assertAlmostEqual(late,.6*math.exp(-.01/(r*.33e-6)),delta=1e-12)
            self.assertGreater(late,0)
            self.assertEqual(v.gain(late),0)
        self.assertAlmostEqual(.33e-6/(1/1047000+1/470000),.10704660514172709)

    def test_piecewise_exact_flow_matches_independent_original_branch_rk4(self):
        actual=v.envelope(256,32512,{64:0,192:16384})
        env=0.;raw=32512;worst=0.
        for n in range(256):
            raw={64:0,192:16384}.get(n,raw)
            r=47000+1000000*raw/32512
            def derivative(e):
                drive=0.
                if n<96:
                    drive=(14.8-.7-e)/1000
                    if e>14.8*10000/57000:
                        drive+=(14.8-e)/47000-e/10000
                    drive=max(0.,drive)
                return (drive-e/r-max(0.,e-.6)/470000)/.33e-6
            dt=1/(48000*128)
            for _ in range(128):
                a=derivative(env);b=derivative(env+dt*a/2)
                c=derivative(env+dt*b/2);d=derivative(env+dt*c)
                env+=dt*(a+2*b+2*c+d)/6
            worst=max(worst,abs(env-actual[n]))
        self.assertLess(worst,2e-7)

    def test_finite_charge_quarter_step_candidate_is_bounded_without_fitted_time_constants(self):
        for raw in (0,1,8192,16384,24576,32511,32512):
            exact=v.envelope(24000,raw)
            candidate=v.envelope(24000,raw,candidate=True)
            self.assertGreater(exact[0],0)
            self.assertLess(exact[0],1.)
            self.assertLess(exact[0],max(exact[:96]))
            self.assertTrue(all(0<=e<=v.SOURCE_V for e in candidate))
            error=max(abs(v.gain(a)-v.gain(b)) for a,b in zip(exact,candidate))
            self.assertLess(error*body909.GAIN*body909.diode_shape(1),3e-6)
        changes={32:32512,64:0,3200:32512,6400:0}
        a=v.envelope(24000,0,changes);b=v.envelope(24000,0,changes,candidate=True)
        self.assertLess(max(abs(v.gain(x)-v.gain(y)) for x,y in zip(a,b))*body909.GAIN*body909.diode_shape(1),3e-6)

    def test_gain_is_first_order_base_current_not_a_fitted_envelope_power(self):
        for env in (0,.4,.6,1,5,12):
            current=max(0.,env-.6)/470000
            self.assertAlmostEqual(v.gain(env),current/(16/470000),places=14)
        for raw in (-1,32513,True,.5):
            with self.assertRaises(ValueError):v.resistance(raw)
        for env in (-.1,15.,float('nan'),True):
            with self.assertRaises(ValueError):v.step(env,0,True)
        for dt in (0,-1,float('nan'),True):
            with self.assertRaises(ValueError):v.step(0,0,True,dt)

    def test_port_coefficients_retain_the_same_physical_quarter_flow(self):
        probes=[(.3,False),(5,False),(.3,True),(1,True),(5,True)]
        for raw in (0,1,8192,16384,24576,32511,32512):
            coefficients=v.port_coefficients(raw)
            for index,(voltage,on) in enumerate(probes):
                self.assertEqual(v.port_region(voltage,on),index)
                loss,equilibrium=v.linear_region(voltage,raw,on)
                alpha=loss/(8*48000)
                expected=-2*alpha/(1+alpha)
                delta,bias=coefficients[index]
                self.assertAlmostEqual(delta,expected,delta=2e-10)
                self.assertAlmostEqual(bias,-expected*equilibrium/64,delta=1e-12)
