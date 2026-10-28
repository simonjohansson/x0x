"""C47/VR4 coupling reference: S01 p9, S03 section9/Table1 (VR4 correction).

VR4 is fixed wide open; this isolated unloaded stage is not the complete output
network. Loading, C49/buffer and C50 remain open in #79. No saved Level control.
"""
import math

OUTPUT_GAIN = 1.6016645431518555  # One training-calibrated factor, shared across settings/CPUs.

SAMPLE_RATE = 48000
VR4 = 100000.0
C47 = .47e-6
TAU = VR4 * C47
CUTOFF = 1 / (2 * math.pi * TAU)
A = (2 * SAMPLE_RATE * TAU - 1) / (2 * SAMPLE_RATE * TAU + 1)
B = 2 * SAMPLE_RATE * TAU / (2 * SAMPLE_RATE * TAU + 1)


def filter_reference(samples):
    """Trapezoidal capacitor-voltage/current solution; output is resistor voltage."""
    voltage = current = 0.0
    h = 1 / (2 * SAMPLE_RATE * C47)
    g = h / VR4
    result = []
    for x in samples:
        if not math.isfinite(x):
            raise ValueError("Coupling input must be finite")
        voltage = (voltage + h * current + g * x) / (1 + g)
        current = (x - voltage) / VR4
        result.append(x - voltage)
    return result


def render_reference(samples):
    """Apply fixed digital output calibration after the unscaled capacitor model."""
    return [OUTPUT_GAIN * value for value in filter_reference(samples)]
