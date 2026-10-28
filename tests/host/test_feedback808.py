"""Isolated full-feedback/Q43 model; not a production DSP acceptance suite."""
import math
import unittest
from unittest import mock

from x0x import body808,feedback808 as f,leakage808


class Feedback808Tests(unittest.TestCase):
    def test_nonlinear_current_is_added_to_physical_capacitor_kcl(self):
        for raw in (0,16384,32512):
            matrix=f.matrix(raw,False)
            derivative=f._physical_derivative(raw,False,False,1.,1.)
            for state in [(0.,0.,0.,0.,0.),(.03,-.1,.002,0.,-.01),(-.03,.1,-.002,0.,.01)]:
                linear=[sum(a*b for a,b in zip(row,[*state,1.])) for row in matrix[:5]]
                actual=derivative(state)
                common=state[3]-state[0]
                current=1.4765e-5*min(common+.556/60,0.)
                expected=-(47000/53800)*current/15e-9
                self.assertAlmostEqual(actual[1]-linear[1],expected,delta=1e-12)
                for index in (0,2,3,4):self.assertAlmostEqual(actual[index],linear[index],delta=1e-12)

    def test_exact_leak_flow_preserves_common_node_and_other_capacitor_states(self):
        for scale in (1.,1.04):
            state=[.03,-.1,.002,0.,-.01]
            changed=f.leak_half(state,1/(2*48000),scale)
            self.assertEqual([changed[i] for i in (0,2,3,4)],[state[i] for i in (0,2,3,4)])
            self.assertEqual(changed[3]-changed[0],state[3]-state[0])
            self.assertGreater(changed[1],state[1])
            full=f.leak_half(state,1/48000,scale)
            twice=f.leak_half(changed,1/(2*48000),scale)
            self.assertLess(max(abs(a-b) for a,b in zip(full,twice)),1e-15)
        quiet=[.001,.1,0.,0.,0.]
        self.assertEqual(f.leak_half(quiet,1/48000),quiet)

    def test_nonlinear_split_matches_independent_kcl_with_refinement(self):
        for raw in (0,16384,32512):
            independent=f.reference(12000,raw)
            refined=f.reference(12000,raw,subdivisions=8)
            candidate=f.reference(12000,raw,split=True)
            self.assertLess(max(abs(a-b) for a,b in zip(independent,refined)),1e-7)
            self.assertLess(max(abs(a-b) for a,b in zip(candidate,refined)),1e-6)
            self.assertTrue(all(math.isfinite(x) and abs(x)<.5 for x in candidate))

    def test_live_decay_keeps_physical_charge_and_nonlinear_flow(self):
        changes={256:32512,288:0,320:16384,2048:8192}
        exact,states=f.reference(4096,0,changes,states=True,subdivisions=8)
        candidate=f.reference(4096,0,changes,split=True)
        self.assertLess(max(abs(a-b) for a,b in zip(exact,candidate)),1e-6)
        # Feedback's C43 voltage is retained, rather than reset by the pot change.
        self.assertNotEqual(states[256][2],0.)
        self.assertLess(abs(states[256][2]-states[255][2]),1e-5)
        self.assertNotEqual(states[320][0],0.)

    def test_nominal_model_does_not_reuse_the_fitted_modal_poles(self):
        before=f.reference(512,split=True)
        with mock.patch.object(body808,'retention',side_effect=AssertionError('calibrated damping used')):
            with mock.patch.object(body808,'FREQUENCY',1.):
                self.assertEqual(f.reference(512,split=True),before)
        for value in (0.,-1.,True,float('nan')):
            with self.assertRaises(ValueError):f.reference(32,capacitor_scale=value)
            with self.assertRaises(ValueError):f.reference(32,r170_scale=value)


if __name__=='__main__':unittest.main()
