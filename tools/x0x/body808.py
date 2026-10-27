"""Independent 55 Hz body oracle with provisional Decay feedback control.

This is an uncalibrated 808 starting point, before excitation, pitch sigh,
stock Decay/Tone networks and residual-state retrigger behavior are modeled.
"""
import math

SAMPLE_RATE = 48000
FREQUENCY = 55.0
TAU = 0.25
GAIN = 0.25


RAW_MAX = 32512
DEFAULT_DECAY = 16384
RETENTION_MAX = math.exp(-1 / SAMPLE_RATE)  # One-second maximum amplitude time constant.
RETENTION_DEFAULT = math.exp(-1 / (SAMPLE_RATE * TAU))
RETENTION_MIN = ((RETENTION_DEFAULT - (DEFAULT_DECAY / RAW_MAX) * RETENTION_MAX)
                 / (1 - DEFAULT_DECAY / RAW_MAX))


def retention(decay_raw):
    """Provisional linear feedback retention, not a stock VR6 circuit/pot curve."""
    if type(decay_raw) is not int or not 0 <= decay_raw <= RAW_MAX:
        raise ValueError("Decay must be an exact native word in 0..32512")
    return RETENTION_MIN + (RETENTION_MAX - RETENTION_MIN) * decay_raw / RAW_MAX


def decay_tau(decay_raw):
    return -1 / (SAMPLE_RATE * math.log(retention(decay_raw)))


def reference(frames, decay_raw=DEFAULT_DECAY, changes=None):
    """Analytical phase and integrated log attenuation; changes apply before sample n."""
    changes = changes or {}
    loss = math.log(retention(decay_raw))
    attenuation = 0.0
    samples = []
    for n in range(frames):
        if n in changes:
            loss = math.log(retention(changes[n]))
        attenuation += loss
        samples.append(GAIN * math.exp(attenuation)
                       * math.sin(2 * math.pi * FREQUENCY * (n + 1) / SAMPLE_RATE))
    return samples


def compare():
    """Compare matching actual CPU samples; each runner writes its own evidence."""
    import json
    from pathlib import Path
    import struct

    root = Path(__file__).resolve().parents[2]
    cases = {}
    for decay_raw in (0, DEFAULT_DECAY, RAW_MAX):
        cf_path = root / f"out/coldfire/body808/samples_{decay_raw}.json"
        sharc_path = root / f"out/sharc/body808/samples_{decay_raw}.f32"
        coldfire = json.loads(cf_path.read_text())
        raw = sharc_path.read_bytes()
        sharc = struct.unpack(f"<{len(raw) // 4}f", raw)
        frames = min(len(coldfire), len(sharc))
        assert frames >= SAMPLE_RATE // 2, "matching half-second CPU renders are required"
        expected = reference(frames, decay_raw)
        errors = {
            "coldfire_oracle": max(abs(a - b) for a, b in zip(coldfire[:frames], expected)),
            "sharc_oracle": max(abs(a - b) for a, b in zip(sharc[:frames], expected)),
            "cross_cpu": max(abs(a - b) for a, b in zip(coldfire[:frames], sharc[:frames])),
        }
        assert all(math.isfinite(e) and e <= 1e-5 for e in errors.values()), (decay_raw, errors)
        cases[str(decay_raw)] = dict(frames=frames, maximum_errors_fs=errors,
                                    expected_tau_s=decay_tau(decay_raw))
    report = dict(status="passed", scope="matching unshifted Decay-controlled body samples",
                  cases=cases, sample_rate=SAMPLE_RATE, limit_fs=1e-5,
                  alignment_samples=0, normalization=False)
    (root / "out/808-body-comparison.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    import json
    print(json.dumps(compare()))
