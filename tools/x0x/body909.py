"""Independent 909 triangle, antiparallel diode shaper and provisional envelope.

S02 p4/p11 and S05 p3/p12 establish the triangle VCO and C9/IC12 Tune path.
Settled 52.58 Hz is a separate training calibration; gain 0.25 and zero-crossing START remain provisional. Decay uses unloaded C8/VR5/R58,
not the complete ENV1/Q12 VCA. The physical A taper remains uncalibrated.
"""
import math

from . import tune909

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
    changes = changes or {}
    loss = -1 / (SAMPLE_RATE * decay_tau(decay_raw))
    total = 0.0
    phases, _ = tune909.reference(frames, tune_raw, tune_changes)
    result = []
    for n in range(frames):
        if n in changes:
            loss = -1 / (SAMPLE_RATE * decay_tau(changes[n]))
        total += loss
        result.append(GAIN * math.exp(total) * shaped_triangle(phases[n]))
    return result


INITIAL_STATE = (0.0, 0.0, tune909.TRIGGER_SAMPLES, GAIN)


def continue_reference(state, decay_raw, tune_raw, frames):
    """Continue physical phase/C9/count/amplitude from a private snapshot.

    START callers use INITIAL_STATE; native phase words map to cycles by
    uint32/2**32 minus .25. The diode shaper remains before the separate VCA.
    """
    phase, voltage, remaining, amplitude = state
    phases, voltages, remaining = tune909.continue_reference(
        phase, voltage, remaining, tune_raw, frames)
    loss = -1/(SAMPLE_RATE*decay_tau(decay_raw))
    samples=[amplitude*math.exp((i+1)*loss)*shaped_triangle(value)
             for i,value in enumerate(phases)]
    return samples, (phases[-1], voltages[-1], remaining, amplitude*math.exp(frames*loss))


def compare():
    import json
    import struct
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    cases = []
    for setting in (0, 1, 16384, 16385, 32511, 32512):
        cf = json.loads((root / f"out/coldfire/body909/samples_{setting}.json").read_text())
        raw = (root / f"out/sharc/body808/samples_909_{setting}.f32").read_bytes()
        sharc = struct.unpack(f"<{len(raw)//4}f", raw)
        assert len(cf) == len(sharc) == 24000, "matching 909 renders must contain 24000 samples"
        expected = reference(len(cf), setting)
        assert all(math.isfinite(x) for x in [*cf, *sharc])
        errors = dict(coldfire_oracle=max(abs(a-b) for a,b in zip(cf,expected)),
                      sharc_oracle=max(abs(a-b) for a,b in zip(sharc,expected)),
                      cross_cpu=max(abs(a-b) for a,b in zip(cf,sharc)))
        assert all(error <= 1e-5 for error in errors.values()), (setting, errors)
        cases.append(dict(raw=setting, maximum_errors_fs=errors))
    report = dict(status="passed", scope="diode-shaped 909 triangle with unloaded RC Decay; no complete circuit fidelity claim",
                  frames=24000, sample_rate=SAMPLE_RATE, decay_cases=cases,
                  maximum_errors_fs={key:max(row["maximum_errors_fs"][key] for row in cases) for key in errors},
                  limit_fs=1e-5, alignment_samples=0, normalization=False)
    (root / "out/909-body-comparison.json").write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__ == "__main__":
    import json
    print(json.dumps(compare()))
