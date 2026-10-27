"""Independent first 909 triangle body, before diode shaping and circuit envelopes.

S02 p4/p11 and S05 p3/p12 establish the triangle VCO topology. Fixed 50 Hz,
gain 0.25 and zero-crossing START remain provisional. Decay uses unloaded C8/VR5/R58,
not the complete ENV1/diode/Q12 VCA. The physical A taper remains uncalibrated.
"""
import math

SAMPLE_RATE = 48000
FREQUENCY = 50.0
GAIN = 0.25
RAW_MAX = 32512
DEFAULT_DECAY = 16384
C8, R58, VR5 = .33e-6, 47000.0, 1000000.0
PHASE_STEP = round(FREQUENCY / SAMPLE_RATE * 2**32)


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


def reference(frames, decay_raw=DEFAULT_DECAY, changes=None):
    changes = changes or {}
    loss = -1 / (SAMPLE_RATE * decay_tau(decay_raw))
    total = 0.0
    result = []
    for n in range(frames):
        if n in changes:
            loss = -1 / (SAMPLE_RATE * decay_tau(changes[n]))
        total += loss
        result.append(GAIN * math.exp(total) * triangle(FREQUENCY * (n+1) / SAMPLE_RATE))
    return result


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
    report = dict(status="passed", scope="unshaped 909 triangle with unloaded RC Decay; no complete circuit fidelity claim",
                  frames=24000, sample_rate=SAMPLE_RATE, decay_cases=cases,
                  maximum_errors_fs={key:max(row["maximum_errors_fs"][key] for row in cases) for key in errors},
                  limit_fs=1e-5, alignment_samples=0, normalization=False)
    (root / "out/909-body-comparison.json").write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__ == "__main__":
    import json
    print(json.dumps(compare()))
