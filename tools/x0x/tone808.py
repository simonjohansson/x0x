"""808 Tone RC reference from S01 p9 and S03 section9/Table1/Equation11.

Native knob direction follows R23; the taper is calibrated to training transfers.
The circuit's voltage/current trapezoid is independent of the ASM TPT form.
"""
import math

from . import body808

SAMPLE_RATE = body808.SAMPLE_RATE
RAW_MAX = body808.RAW_MAX
DEFAULT_TONE = 16384
R171, R172, VR5, C45 = 220.0, 10000.0, 10000.0, 1e-7
TAPER = 1.3739869594783976


def resistance(tone_raw):
    if type(tone_raw) is not int or not 0 <= tone_raw <= RAW_MAX:
        raise ValueError("Tone must be an exact native word in 0..32512")
    position = math.sqrt(tone_raw / RAW_MAX)
    # shortcut: one effective reference curve; exact vintage taper remains open.
    pot = VR5 * (1 - position) / (1 + TAPER * position)
    return R171 + R172 * pot / (R172 + pot)


def cutoff(tone_raw):
    return 1 / (2 * math.pi * resistance(tone_raw) * C45)


def coefficient(tone_raw):
    return 1 / (1 + 2 * SAMPLE_RATE * C45 * resistance(tone_raw))


def filter_reference(samples, tone_raw=DEFAULT_TONE, changes=None):
    """Solve C*dV/dt=(input-V)/R with capacitor-voltage/current history."""
    changes = changes or {}
    voltage, current = 0.0, 0.0
    history_scale = 1 / (2 * SAMPLE_RATE * C45)
    r = resistance(tone_raw)
    result = []
    for n, sample in enumerate(samples):
        if not math.isfinite(sample):
            raise ValueError("Tone input must be finite")
        if n in changes:
            r = resistance(changes[n])
        g = history_scale / r
        voltage = (voltage + history_scale * current + g * sample) / (1 + g)
        current = (sample - voltage) / r
        result.append(voltage)
    return result


def compare():
    """Compare actual body/Tone/C47 output with the independent circuit reference."""
    import json
    from pathlib import Path
    import struct
    from . import coupling808

    root = Path(__file__).resolve().parents[2]
    cases = {}
    settings = [(d, DEFAULT_TONE) for d in (0, body808.DEFAULT_DECAY, RAW_MAX)]
    settings += [(body808.DEFAULT_DECAY, t) for t in (0, RAW_MAX)]
    for decay, tone in settings:
        cf = json.loads((root / f"out/coldfire/coupling808/body_{decay}_{tone}.json").read_text())
        raw = (root / f"out/sharc/body808/filtered_{decay}_{tone}.f32").read_bytes()
        sharc = struct.unpack(f"<{len(raw)//4}f", raw)
        frames = min(len(cf), len(sharc))
        assert frames >= 8192, "matching CPU output is too short"
        expected = coupling808.render_reference(filter_reference(body808.reference(frames, decay), tone))
        errors = dict(coldfire_oracle=max(abs(a-b) for a,b in zip(cf[:frames], expected)),
                      sharc_oracle=max(abs(a-b) for a,b in zip(sharc[:frames], expected)),
                      cross_cpu=max(abs(a-b) for a,b in zip(cf[:frames], sharc[:frames])))
        assert all(math.isfinite(e) and e <= 1e-5 for e in errors.values()), (decay,tone,errors)
        cases[f"{decay}_{tone}"] = dict(frames=frames, maximum_errors_fs=errors)
    report = dict(status="passed", scope="matching body, Tone RC and unloaded C47 coupling output",
                  cases=cases, sample_rate=SAMPLE_RATE, limit_fs=1e-5,
                  alignment_samples=0, normalization=False)
    (root / "out/808-body-comparison.json").write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__ == "__main__":
    import json
    print(json.dumps(compare()))
