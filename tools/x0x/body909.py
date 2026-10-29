"""Independent 909 triangle, diode shaper and first-order loaded ENV1/Q12 VCA.

S02 p4/p11 and S05 p3/p12 establish the triangle VCO and C9/IC12 Tune path.
The forced HIGH branch makes raw C14 rise; Q12/IC11a inverts the audio.
Settled52.58Hz is a separate training calibration; gain0.25 and zero-crossing
START remain provisional. ENV1 uses finite C8 charge and Q12 base-current loading;
transistor compression, subthreshold behavior and physical A taper remain open.
"""
import math

from . import tune909, trigger909

SAMPLE_RATE = 48000
FREQUENCY = tune909.SETTLED_HZ
GAIN = 0.25
RAW_MAX = 32512
DEFAULT_DECAY = 16384
C8, R58, VR5 = .33e-6, 47000.0, 1000000.0
PHASE_STEP = round(FREQUENCY / SAMPLE_RATE * 2**32)
R52, R53, R43 = 10000.0, 2200.0, 47.0
R49, R50 = 100000.0, 47000.0
# shortcut: generic silicon operating point; replace with measured D10/D11 and IC13 behavior.
COMPARATOR_SWING = 13.0
DIODE_IS, DIODE_NVT = 1e-9, .052
TRIANGLE_VOLTS = COMPARATOR_SWING * R50 / (R49 + R50)
LINEAR_VOLTS = TRIANGLE_VOLTS * (R53 + R43) / (R52 + R53 + R43)
THEVENIN_OHMS = R52 * (R53 + R43) / (R52 + R53 + R43)
SHAPER_SEGMENTS = 16
from . import vca909


def decay_tau(raw):
    """Unloaded C8 discharge, with provisional resistance-linear VR5 mapping."""
    if type(raw) is not int or not 0 <= raw <= RAW_MAX:
        raise ValueError("Decay must be an exact native word in 0..32512")
    return C8 * (R58 + VR5 * raw / RAW_MAX)


def retention(raw):
    return math.exp(-1 / (SAMPLE_RATE * decay_tau(raw)))



TAU = decay_tau(DEFAULT_DECAY)
RETENTION = retention(DEFAULT_DECAY)


def triangle(cycles):
    """Analytic triangle, independent of the ASM's integer phase folding."""
    return 2 / math.pi * math.asin(math.sin(2 * math.pi * cycles))


def diode_shape(value):
    """Solve R52/antiparallel Shockley diodes/passive R53+R43 load by KCL.

    Fixed open-diode linear units retain the existing provisional audio scale;
    there is no peak normalization. Q12's signal-dependent loading is omitted.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or abs(value) > 1:
        raise ValueError("triangle must be finite in -1..1")
    target = abs(value) * LINEAR_VOLTS
    node = min(target, .6)
    for _ in range(12):
        argument = node / DIODE_NVT
        residual = node + 2 * THEVENIN_OHMS * DIODE_IS * math.sinh(argument) - target
        slope = 1 + 2 * THEVENIN_OHMS * DIODE_IS / DIODE_NVT * math.cosh(argument)
        correction = residual / slope
        node -= correction
        if abs(correction) < 1e-14:
            break
    else:
        raise ArithmeticError("909 diode KCL did not converge")
    return math.copysign(node / LINEAR_VOLTS, value)


def shaped_triangle(cycles):
    return diode_shape(triangle(cycles))


def shaper_coefficients():
    """Positive-half cubic Hermite coefficients, constant first, for both CPUs."""
    values = [diode_shape(i / SHAPER_SEGMENTS) for i in range(SHAPER_SEGMENTS + 1)]
    slopes = [1 / (1 + 2 * THEVENIN_OHMS * DIODE_IS / DIODE_NVT
                    * math.cosh(v * LINEAR_VOLTS / DIODE_NVT)) / SHAPER_SEGMENTS
              for v in values]
    return [(left, dl, 3 * (right-left) - 2 * dl - dr, 2 * (left-right) + dl + dr)
            for left,right,dl,dr in zip(values,values[1:],slopes,slopes[1:])]


def reference(frames, decay_raw=DEFAULT_DECAY, changes=None,
              tune_raw=tune909.DEFAULT_TUNE, tune_changes=None):
    phases, _, _ = trigger909.reference(frames, tune_raw,changes=tune_changes)
    voltages = vca909.envelope(frames, decay_raw, changes)
    return [-GAIN*vca909.gain(voltage)*shaped_triangle(phase)
            for voltage,phase in zip(voltages,phases)]


INITIAL_STATE = (0.0, 0.0, tune909.TRIGGER_SAMPLES, 0.0)


def continue_reference(state, decay_raw, tune_raw, frames):
    """Continue private phase/C9/count/C8 state, with capacitor volts encoded /64.

    START callers use INITIAL_STATE; native phase words map to cycles by
    uint32/2**32 minus .25. The diode shaper remains before the separate VCA.
    """
    phase, voltage, remaining, c8_encoded = state
    phases, voltages, oscillator_state = trigger909.continue_reference(
        (phase, voltage, remaining),tune_raw,frames)
    remaining=oscillator_state[2]
    initial_remaining = state[2]
    c8 = c8_encoded / vca909.STATE_SCALE
    samples=[]
    for i,value in enumerate(phases):
        c8=vca909.step(c8,decay_raw,initial_remaining-i>0)
        samples.append(-GAIN*vca909.gain(c8)*shaped_triangle(value))
    return samples, (phases[-1], voltages[-1], remaining, c8*vca909.STATE_SCALE)
