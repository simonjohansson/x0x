"""Independent first 909 triangle body, before diode shaping and circuit envelopes.

S02 p4/p11 and S05 p3/p12 establish the triangle VCO topology. Fixed 50 Hz,
250 ms decay, gain 0.25 and zero-crossing START are provisional audition values.
"""
import math

SAMPLE_RATE = 48000
FREQUENCY = 50.0
TAU = 0.25
GAIN = 0.25
PHASE_STEP = round(FREQUENCY / SAMPLE_RATE * 2**32)
RETENTION = math.exp(-1 / (SAMPLE_RATE * TAU))


def triangle(cycles):
    """Analytic triangle, independent of the ASM's integer phase folding."""
    return 2 / math.pi * math.asin(math.sin(2 * math.pi * cycles))


def reference(frames):
    return [GAIN * math.exp(-(n + 1) / (SAMPLE_RATE * TAU))
            * triangle(FREQUENCY * (n + 1) / SAMPLE_RATE) for n in range(frames)]


def compare():
    import json
    import struct
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    cf = json.loads((root / "out/coldfire/body909/samples.json").read_text())
    raw = (root / "out/sharc/body808/samples_909.f32").read_bytes()
    sharc = struct.unpack(f"<{len(raw)//4}f", raw)
    assert len(cf) == len(sharc) == 24000, "matching 909 renders must contain 24000 samples"
    expected = reference(len(cf))
    assert all(math.isfinite(x) for x in [*cf, *sharc])
    errors = dict(coldfire_oracle=max(abs(a-b) for a,b in zip(cf,expected)),
                  sharc_oracle=max(abs(a-b) for a,b in zip(sharc,expected)),
                  cross_cpu=max(abs(a-b) for a,b in zip(cf,sharc)))
    assert all(error <= 1e-5 for error in errors.values()), errors
    report = dict(status="passed", scope="first unshaped 909 triangle body; no circuit fidelity claim",
                  frames=len(cf), sample_rate=SAMPLE_RATE, maximum_errors_fs=errors,
                  limit_fs=1e-5, alignment_samples=0, normalization=False)
    (root / "out/909-body-comparison.json").write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__ == "__main__":
    import json
    print(json.dumps(compare()))
