"""Source-derived trigger events; no phase fitting to recorded audio."""
import math
import unittest

from x0x import trigger909 as trigger, tune909


class Trigger909Tests(unittest.TestCase):
    def test_regular_reset_series_covers_every_native_tune_word(self):
        for raw in range(tune909.RAW_MAX+1):
            exact=trigger.reset_coefficients(raw)
            regular=trigger.reset_series_coefficients(raw)
            for wanted,actual in zip(exact,regular):
                self.assertAlmostEqual(actual,wanted,delta=1e-12)

    def test_q7_remains_driven_until_electrical_trigger_ends(self):
        current = trigger.q7_base_current(trigger.TRIGGER_SAMPLES/48000)
        self.assertGreater(current, 80e-6)
        self.assertLess(current, trigger.q7_base_current(0))
        self.assertEqual(trigger.q7_base_current(.1), 0)

    def test_c14_has_finite_feedback_while_c9_charges_then_releases(self):
        for raw in (0,16384,32512):
            phase, voltage, state = trigger.reference(256,raw)
            free_phase, free_voltage = tune909.reference(256,raw)
            self.assertGreater(phase[0],0)
            self.assertLess(phase[95],free_phase[95])
            self.assertEqual(voltage, free_voltage)
            self.assertGreater(voltage[95], 0)
            self.assertGreater(phase[96], 0)
            for n in range(96,256):
                self.assertAlmostEqual(phase[n],phase[95]+free_phase[n]-free_phase[95],delta=1e-14)
            self.assertEqual(state, (phase[-1],voltage[-1],0))

    def test_chunk_continuity_including_trigger_release(self):
        full_phase, full_voltage, full_state = trigger.reference(1024)
        for split in (32,95,96,97,128,512):
            first, voltage, state = trigger.reference(split)
            second, after, final = trigger.continue_reference(state,16384,1024-split)
            self.assertEqual(first+second, full_phase)
            self.assertEqual(voltage+after, full_voltage)
            self.assertEqual(final, full_state)

    def test_retrigger_resets_direction_without_erasing_c9_or_c14(self):
        phase, voltage, state = trigger.reference(512,starts=(256,))
        initial_phase, initial_voltage, _ = trigger.reference(256)
        self.assertEqual(phase[:256],initial_phase)
        self.assertEqual(voltage[:256],initial_voltage)
        expected_start = math.asin(math.sin(2*math.pi*phase[255]))/(2*math.pi)
        r,c,d=trigger.reset_coefficients(16384)
        self.assertAlmostEqual(phase[256],r*expected_start+c+d*voltage[255])
        self.assertNotEqual(phase[256],0)
        self.assertGreater(voltage[256],initial_voltage[0])
        self.assertGreater(phase[352],0)
        self.assertEqual(state[2],0)

    def test_reset_matches_independent_rk4_of_c9_and_c14(self):
        for raw in (0,16384,32512):
            phases,voltages,_=trigger.reference(96,raw)
            c=tune909.coefficients(raw)
            phase=voltage=0.0
            dt=1/(48000*32)
            def derivative(p,v):
                return (tune909.SETTLED_HZ*(1+c['cv_ratio']*v)-p/(trigger.R51*trigger.C14),
                        (c['on_level']-v)/c['tau_on'])
            for n in range(96):
                for _ in range(32):
                    a,b=derivative(phase,voltage)
                    d,e=derivative(phase+dt*a/2,voltage+dt*b/2)
                    f,g=derivative(phase+dt*d/2,voltage+dt*e/2)
                    h,i=derivative(phase+dt*f,voltage+dt*g)
                    phase+=dt*(a+2*d+2*f+h)/6
                    voltage+=dt*(b+2*e+2*g+i)/6
                self.assertAlmostEqual(phases[n],phase,delta=1e-12)
                self.assertAlmostEqual(voltages[n],voltage,delta=1e-12)

    def test_no_start_preserves_phase_and_charged_state(self):
        phase,voltage,state=trigger.continue_reference((.125,.2,0),16384,32)
        self.assertGreater(phase[0],.125)
        self.assertLess(voltage[0],.2)
        self.assertEqual(state[2],0)

    def test_live_tune_changes_preserve_c14_and_c9_history_across_reset_release(self):
        changes={32:32512,160:8192}
        phases,voltages,final=trigger.reference(256,0,changes=changes)
        state=trigger.INITIAL_STATE
        continued,charged=[],[]
        for frames,raw in [(32,0),(128,32512),(96,8192)]:
            p,v,state=trigger.continue_reference(state,raw,frames)
            continued.extend(p);charged.extend(v)
        self.assertEqual(phases,continued)
        self.assertEqual(voltages,charged)
        self.assertEqual(final,state)
        self.assertEqual(voltages,tune909.reference(256,0,changes)[1])


if __name__ == '__main__':
    unittest.main()
