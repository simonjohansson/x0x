"""Independent first-body oracle: a fixed 55 Hz, 250 ms damped sine.

This is an uncalibrated 808 starting point, before excitation, pitch sigh,
stock Decay/Tone networks and residual-state retrigger behavior are modeled.
"""
import math

SAMPLE_RATE = 48000
FREQUENCY = 55.0
TAU = 0.25
GAIN = 0.25


def reference(frames):
    """Samples after a START at time zero; no recurrence or target quantization."""
    return [GAIN * math.exp(-(n + 1) / (SAMPLE_RATE * TAU))
            * math.sin(2 * math.pi * FREQUENCY * (n + 1) / SAMPLE_RATE)
            for n in range(frames)]


def compare():
    """Compare matching actual CPU samples; each runner writes its own evidence."""
    import json
    from pathlib import Path
    import struct

    root = Path(__file__).resolve().parents[2]
    cf_path = root / "out/coldfire/body808/samples.json"
    sharc_path = root / "out/sharc/body808/samples.f32"
    coldfire = json.loads(cf_path.read_text())
    raw = sharc_path.read_bytes()
    sharc = struct.unpack(f"<{len(raw) // 4}f", raw)
    frames = min(len(coldfire), len(sharc))
    assert frames >= SAMPLE_RATE // 2, "matching half-second CPU renders are required"
    expected = reference(frames)
    errors = {
        "coldfire_oracle": max(abs(a - b) for a, b in zip(coldfire[:frames], expected)),
        "sharc_oracle": max(abs(a - b) for a, b in zip(sharc[:frames], expected)),
        "cross_cpu": max(abs(a - b) for a, b in zip(coldfire[:frames], sharc[:frames])),
    }
    assert all(math.isfinite(e) and e <= 1e-5 for e in errors.values()), errors
    report = dict(status="passed", scope="matching unshifted first-body CPU samples",
                  frames=frames, sample_rate=SAMPLE_RATE, maximum_errors_fs=errors,
                  limit_fs=1e-5, alignment_samples=0, normalization=False)
    (root / "out/808-body-comparison.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    import json
    print(json.dumps(compare()))
