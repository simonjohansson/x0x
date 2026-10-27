"""Physical KCL and independent quadrature checks for the 909 Tune CV."""
import math
import unittest

from x0x import tune909 as tune


class Tune909Tests(unittest.TestCase):
    def test_endpoints_and_loaded_capacitor(self):
        low, high = tune.coefficients(0), tune.coefficients(tune.RAW_MAX)
        self.assertAlmostEqual(low['tau_off'], .33e-6 / (1/22000 + 1/330000))
        self.assertAlmostEqual(high['tau_off'], .33e-6 / (1/122000 + 1/330000))
        self.assertLess(low['tau_off'], high['tau_off'])
        self.assertLess(high['tau_off'], .33e-6 * 122000)
        for raw in range(tune.RAW_MAX + 1):
            c = tune.coefficients(raw)
            self.assertTrue(0 < c['radius_on'] < c['radius_off'] < 1)
            self.assertTrue(0 < c['on_level'] < 1)
            self.assertTrue(0 < c['mean_on'] < c['mean_off'] < 1)

    def test_exact_voltage_and_phase_against_rk4_kcl(self):
        for raw in (0, 1, tune.DEFAULT_TUNE, tune.RAW_MAX-1, tune.RAW_MAX):
            phases, voltages = tune.reference(2400, raw)
            resistance = tune.R57 + tune.VR2 * raw / tune.RAW_MAX
            voltage = phase = 0.0
            dt = 1 / (tune.SAMPLE_RATE * 8)
            def derivative(v, charging):
                current = (tune.CHARGE_V - v) / tune.R21 if charging else 0.0
                return ((current - v/resistance - v/tune.R26) / tune.C9,
                        tune.SETTLED_HZ * (1 + tune.CV_GAIN * v / tune.CV_BASE_V))
            for sample in range(2400):
                charging = sample < tune.TRIGGER_SAMPLES
                for _ in range(8):
                    k1,p1 = derivative(voltage, charging)
                    k2,p2 = derivative(voltage + dt*k1/2, charging)
                    k3,p3 = derivative(voltage + dt*k2/2, charging)
                    k4,p4 = derivative(voltage + dt*k3, charging)
                    voltage += dt*(k1 + 2*k2 + 2*k3 + k4)/6
                    phase += dt*(p1 + 2*p2 + 2*p3 + p4)/6
                self.assertAlmostEqual(voltages[sample], voltage/tune.SUPPLY_V, delta=1e-10)
                self.assertAlmostEqual(phases[sample], phase, delta=1e-10)

    def test_tune_changes_sweep_not_settled_pitch(self):
        phases0, v0 = tune.reference(24000, 0)
        phases1, v1 = tune.reference(24000, tune.RAW_MAX)
        self.assertGreater(phases1[2400], phases0[2400])
        self.assertGreater(v1[2400], v0[2400])
        for phases in (phases0, phases1):
            self.assertAlmostEqual((phases[-1]-phases[-2])*tune.SAMPLE_RATE,
                                   tune.SETTLED_HZ, delta=1e-4)

    def test_live_tune_preserves_charge(self):
        _, original = tune.reference(800, 0)
        _, changed = tune.reference(800, 0, {512:tune.RAW_MAX})
        self.assertEqual(original[:512], changed[:512])
        self.assertGreater(changed[512], original[512])
        self.assertLess(changed[512], changed[511])

    def test_native_snapshot_continuation_uses_the_same_physical_flow(self):
        for split in (32, 96, 128, 2048):
            full_phase, full_voltage = tune.reference(3072)
            phase, voltage, remaining = tune.continue_reference(
                full_phase[split-1], full_voltage[split-1],
                max(tune.TRIGGER_SAMPLES-split, 0), tune.DEFAULT_TUNE, 3072-split)
            self.assertEqual(phase, full_phase[split:])
            self.assertEqual(voltage, full_voltage[split:])
            self.assertEqual(remaining, 0)

    def test_rejects_non_native_control(self):
        for raw in (-1, tune.RAW_MAX+1, True, 1.0, math.nan):
            with self.assertRaises(ValueError):
                tune.coefficients(raw)


if __name__ == '__main__':
    unittest.main()
