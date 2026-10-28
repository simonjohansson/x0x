"""Original pulse-network KCL, independent of either target instruction port."""
import math
import unittest

from x0x import attack909 as pulse


class Attack909Tests(unittest.TestCase):
    def test_quiescent_q9_and_c11_are_zero_not_a_hidden_positive_bias(self):
        self.assertEqual(pulse.follower(0),0)
        out,state,count=pulse.continue_reference(pulse.INITIAL_STATE,0,16384,64,substeps=16)
        self.assertEqual(out,[0.]*64)
        self.assertEqual(state,pulse.INITIAL_STATE)
        self.assertEqual(count,0)

    def test_q8_off_c5_supplies_both_r14_and_c2_filter_load(self):
        state=(-2.,1.,.3,1.1,.2,2.,3.)
        change=pulse.derivative(state,True,pulse.passive_mix(16384)[0])
        emitter=pulse.follower(state[3])
        current_c2=(state[0]-state[1]-state[2]-emitter)/pulse.R7
        self.assertAlmostEqual(pulse.C5*change[0],-(state[0]+pulse.HIGH)/pulse.R14-current_c2)
        self.assertAlmostEqual(pulse.C2*change[1],current_c2)
        current_c3=current_c2-(state[2]+emitter)/pulse.R15-(state[2]+emitter-state[3])/pulse.R16
        self.assertAlmostEqual(pulse.C3*change[2],current_c3)
        self.assertAlmostEqual(pulse.C4*change[3],(state[2]+emitter-state[3])/pulse.R16)

    def test_leading_negative_is_cutoff_then_release_has_signed_highpass_tail(self):
        out,state,count=pulse.reference(768,substeps=16)
        self.assertEqual(out[:96],[0.]*96)
        self.assertGreater(max(out[96:]),0)
        self.assertLess(min(out[96:]),0)
        self.assertEqual(count,0)
        self.assertEqual(state[0],0)
        self.assertGreater(state[4],0)

    def test_attack_rheostat_is_500ohm_linear_and_keeps_grounded_noise_load(self):
        previous=0
        for raw in (0,1,8192,16384,24576,32511,32512):
            tau,transfer=pulse.passive_mix(raw)
            pot=500*(1-raw/32512)
            load=1/(1/330+1/47000+1/(pot+47))
            self.assertAlmostEqual(tau,(22000+load)*.47e-6)
            self.assertAlmostEqual(transfer,load/(22000+load)*47/(pot+47))
            self.assertGreater(transfer,previous)
            previous=transfer

    def test_split_continuity_and_live_attack_do_not_reset_capacitors(self):
        full,final,count=pulse.reference(192,substeps=16,changes={96:32512})
        first,state,remaining=pulse.reference(96,substeps=16)
        second,state,remaining=pulse.continue_reference(state,remaining,32512,96,substeps=16)
        self.assertEqual(first+second,full)
        self.assertEqual(state,final)
        self.assertEqual(remaining,count)

    def test_target_substeps_converge_against_independent_high_rate_flow(self):
        for raw in (0,16384,32512):
            target=pulse.audio(pulse.reference(384,raw,substeps=16)[0])
            oracle=pulse.audio(pulse.reference(384,raw,substeps=128)[0])
            self.assertLess(max(abs(a-b) for a,b in zip(target,oracle)),3e-6)
            self.assertTrue(all(math.isfinite(x) for x in target))

    def test_invalid_input_is_rejected(self):
        for raw in (-1,32513,1.5):
            with self.assertRaises(ValueError):pulse.passive_mix(raw)
        for state,count,frames in (([0.]*6,96,1),(pulse.INITIAL_STATE,97,1),(pulse.INITIAL_STATE,96,-1)):
            with self.assertRaises(ValueError):pulse.continue_reference(state,count,16384,frames)


if __name__=='__main__':
    unittest.main()
