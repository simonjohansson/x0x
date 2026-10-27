"""Independent stock TR-909 C9/IC12 Tune CV and integrated oscillator phase.

S02 p5/p11, S05 p3/p12: Tune changes C9 discharge, not settled pitch.
The source A taper, Q2/D7 drops, Q11 reset and comparator swing remain unmeasured.
This isolates the nominal switched RC circuit from the one settled-Hz calibration.
"""
import math

SAMPLE_RATE = 48000
RAW_MAX = 32512
DEFAULT_TUNE = 16384
TRIGGER_SAMPLES = 96  # S02: positive 5 V electrical trigger, 2 ms.
C9, R21, R57, VR2, R26 = .33e-6, 2200.0, 22000.0, 100000.0, 330000.0
R27, R28, SUPPLY_V = 1500000.0, 150000.0, 15.0
# shortcut: nominal silicon switch/diode drops, replace only with circuit evidence.
CHARGE_V = SUPPLY_V - .2 - .7
CV_BASE_V = SUPPLY_V * R28 / R27
CV_GAIN = R28 / R26
# Training recordings, measured separately from the nominal component transfer.
SETTLED_HZ = 52.58
NOMINAL_HZ = CV_BASE_V / (4 * 47000 * .033e-6 * (13 * 47000 / 147000))


def coefficients(raw):
    """Exact one-sample C9 flow; Tune currently maps linearly to resistance.

    C9 is normalized by the 15 V rail. The phase contribution uses the interval
    mean of that physical state, so no sample delay or Euler pitch drift enters.
    """
    if type(raw) is not int or not 0 <= raw <= RAW_MAX:
        raise ValueError("Tune must be an exact native word in 0..32512")
    resistance = R57 + VR2 * raw / RAW_MAX
    load = 1 / (1 / resistance + 1 / R26)
    tau_off = C9 * load
    tau_on = C9 / (1 / load + 1 / R21)
    radius_off = math.exp(-1 / (SAMPLE_RATE * tau_off))
    radius_on = math.exp(-1 / (SAMPLE_RATE * tau_on))
    mean_off = -math.expm1(-1 / (SAMPLE_RATE * tau_off)) * SAMPLE_RATE * tau_off
    mean_on = -math.expm1(-1 / (SAMPLE_RATE * tau_on)) * SAMPLE_RATE * tau_on
    on_level = CHARGE_V / SUPPLY_V * load / (R21 + load)
    return dict(tau_on=tau_on, tau_off=tau_off, radius_on=radius_on,
                radius_off=radius_off, mean_on=mean_on, mean_off=mean_off,
                on_level=on_level, cv_ratio=R27 / R26)


def _advance(frames, phase, voltage, remaining, tune_raw, changes):
    c = coefficients(tune_raw)
    phases, voltages = [], []
    for sample in range(frames):
        if sample in changes:
            c = coefficients(changes[sample])
        charging = remaining > 0
        level = c['on_level'] if charging else 0.0
        radius = c['radius_on'] if charging else c['radius_off']
        mean = level + (voltage - level) * c['mean_on' if charging else 'mean_off']
        voltage = level + (voltage - level) * radius
        phase += SETTLED_HZ / SAMPLE_RATE * (1 + c['cv_ratio'] * mean)
        remaining = max(remaining - 1, 0)
        phases.append(phase)
        voltages.append(voltage)
    return phases, voltages, remaining


def reference(frames, tune_raw=DEFAULT_TUNE, changes=None):
    """Return end-of-interval phase cycles and normalized C9 voltage.

    This models the switched C9 path only. Existing zero-phase START is retained;
    deriving the Q11/C14 reset path is separate from this CV calculation.
    """
    phases, voltages, _ = _advance(frames, 0.0, 0.0, TRIGGER_SAMPLES,
                                  tune_raw, changes or {})
    return phases, voltages


def continue_reference(phase_cycles, voltage, remaining, tune_raw, frames):
    """Continue the physical RC/phase flow from an observed private snapshot.

    Phase is physical cycles (native uint32/2**32 minus the START quarter cycle).
    C9 voltage is normalized by 15 V; no oscillator phase or capacitor is reset.
    """
    if (not math.isfinite(phase_cycles) or not math.isfinite(voltage)
            or type(remaining) is not int or not 0 <= remaining <= TRIGGER_SAMPLES):
        raise ValueError("invalid 909 phase/C9/trigger snapshot")
    return _advance(frames, phase_cycles, voltage, remaining, tune_raw, {})
