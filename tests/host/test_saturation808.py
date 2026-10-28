"""Isolated calibrated-core opamp KCL; no production/native acceptance."""
import math
import unittest
from x0x import body808,saturation808 as s


class Saturation808Tests(unittest.TestCase):
    def test_no_rails_preserves_current_constant_control_model(self):
        for raw in (0,16384,32512):
            current=body808.reference(24000,raw)
            equivalent=s.reference(24000,raw,main_limit_v=None,feedback_limit_v=None)
            self.assertLess(max(abs(a-b) for a,b in zip(current,equivalent)),1e-7)

    def test_equivalent_kcl_keeps_existing_quiet_poles_without_new_fit(self):
        for raw in (0,1,8192,16384,24576,32511,32512):
            sigma=-48000*math.log(body808.retention(raw))
            for attack in (False,True):
                omega=2*math.pi*(body808.ATTACK_FREQUENCY if attack else body808.FREQUENCY)
                coef=s.coefficients(raw,attack)
                a,b,c,d,_=s._affine((0,0,False),0.,0.,coef,None,None)
                self.assertAlmostEqual(a+d,-2*sigma,delta=1e-11)
                self.assertAlmostEqual(a*d-b*c,sigma*sigma+omega*omega,delta=1e-8)

    def test_main_and_buffer_limits_obey_opamp_error_and_keep_charge(self):
        q1,q2,u=-.03,-.04,.2
        d=s.coefficients(32512,False)[3]
        requested,out,common,minus,fb_request,fb,minus_fb=s.nodes(q1,q2,u,d,14/60,14/60)
        self.assertGreater(requested,out)
        self.assertEqual(out,14/60)
        self.assertGreater(u-minus,0)
        self.assertEqual(common,out+q2)
        self.assertEqual((q1,q2),(-.03,-.04))
        requested,out,common,minus,fb_request,fb,minus_fb=s.nodes(q1,q2,u,d,None,12/60)
        self.assertLess(fb_request,fb)
        self.assertEqual(fb,-12/60)
        self.assertGreater(minus_fb,0)  # Negative output saturation has negative input error.

    def test_expanded_policies_match_independent_branch_kcl(self):
        states=[(0.,0.,14/60,.71/60),(-.03,-.04,.2,-.2),(.1,.2,0.,0.),(-.1,-.3,0.,0.)]
        for raw in (0,16384,32512):
            for attack in (False,True):
                coef=s.coefficients(raw,attack)
                for main,buffer in [(14/60,14/60),(None,12/60),(None,None)]:
                    derivative=s._derivative(coef,attack,False,main,buffer)
                    for state in states:
                        q1,q2,u,r=state
                        mode=s._mode(q1,q2,u,coef[3],main,buffer,attack)
                        a,b,c,d,bias=s._affine(mode,u,r,coef,main,buffer)
                        actual=derivative(state)
                        self.assertAlmostEqual(a*q1+b*q2,actual[0],delta=1e-12)
                        self.assertAlmostEqual(c*q1+d*q2+bias,actual[1],delta=2e-12)

    def test_eight_midpoint_steps_match_independent_refined_kcl(self):
        # All nine grid Decays, including the corrected lower half. Rail-event
        # timing varies with damping, so anchor-only refinement is insufficient.
        for raw in (0,4096,8192,12288,16384,20224,24320,28416,32512):
            for rail in (14.,12.):
                original=s.reference(24000,raw,main_limit_v=rail,feedback_limit_v=rail)
                refined=s.reference(24000,raw,main_limit_v=rail,feedback_limit_v=rail,subdivisions=64)
                candidate=s.reference(24000,raw,main_limit_v=rail,feedback_limit_v=rail,
                                      subdivisions=8,midpoint_candidate=True)
                self.assertLess(max(abs(a-b) for a,b in zip(original,refined)),1e-7)
                self.assertLess(max(abs(a-b) for a,b in zip(candidate,refined)),1e-5)

    def test_saturation_changes_connected_capacitor_history_not_only_final_audio(self):
        unbounded=s.reference(24000,32512,main_limit_v=None,feedback_limit_v=None)
        connected=s.reference(24000,32512)
        post_clipped=[min(max(x,-14/60),14/60) for x in unbounded]
        self.assertLessEqual(max(map(abs,connected)),14/60)
        self.assertTrue(all(abs(x)<14/60 for x in unbounded[8000:]))
        self.assertGreater(max(abs(a-b) for a,b in zip(connected[8000:],post_clipped[8000:])),1e-5)


if __name__=='__main__':unittest.main()
