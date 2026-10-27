"""Execute the first 808 and 909 bodies in SHARC; no native OS or fidelity claim."""
from __future__ import annotations

import hashlib
import json
import math
import struct
import sys

from . import analysis, body808, body909, coupling808, cpu, tone808, sharc_callback as callback, sharc_selector as selector

SOURCE = cpu.ROOT / "targets/sharc/body808.s"
FOLDER = cpu.ROOT / "out/sharc/body808"
STATE_BYTES = 448
FRAMES = 24000


def component() -> tuple[dict, bytes]:
    FOLDER.mkdir(parents=True, exist_ok=True)
    code, entry, _ = callback.build(FOLDER, SOURCE)
    from elekloader.sdk.sharc import machine_layout
    layout = machine_layout("voice")
    callback.validate_layout(layout, code, entry)
    assert STATE_BYTES <= layout["data_bytes"]
    callback.decoded_instructions(code, entry)

    def runner():
        return selector.SelectorRunner(code, entry, state_bytes=STATE_BYTES,
                                       extra_slot_state_offset=128, tone_state_offset=256,
                                       coupling_state_offset=320)

    policy = runner()
    inputs = selector.cases()
    expected, provenance = selector.c_reference(FOLDER, inputs)
    position909 = [0] * 16
    for row, reference in zip(inputs, expected, strict=True):
        samples, state = policy.call_raw(row, state_writable=reference["notices"] == 1)
        assert state[:32] == reference["state"], row["label"]
        if samples is not None:
            bound = .25 if row["slot"] < 16 and state[2 * row["slot"] + 1] == 2 else .5
            assert all(math.isfinite(x) and abs(x) <= bound for x in samples), row["label"]
            if not reference["notices"]:
                assert samples == [0.0] * 32, row["label"]
            elif state[2 * row["slot"] + 1] == 2:
                slot = row["slot"]
                if row["flags"]:
                    position909[slot] = 0
                begin = position909[slot]
                wave = body909.reference(begin + 32)[begin:]
                assert max(abs(a-b) for a,b in zip(samples, wave)) < 1e-5, row["label"]
                position909[slot] += 32
                assert state[32 + 2 * slot] == (0x40000000 + position909[slot] * body909.PHASE_STEP) & 0xffffffff
                assert state[64 + slot] == 0, row["label"]

    def body_case(label, raw=16384, tone=16384, **kwargs):
        row = selector.case(label, **kwargs)
        row["params"][0] = tone
        row["params"][1] = raw
        return row

    def render(raw, frames, changes=None, tone=16384, tone_changes=None):
        machine = runner()
        result = []
        current, current_tone = raw, tone
        for block in range(frames // 32):
            current = (changes or {}).get(block * 32, current)
            current_tone = (tone_changes or {}).get(block * 32, current_tone)
            chunk, _ = machine.call_raw(body_case("body", current, current_tone, flags=int(block == 0)), True)
            result.extend(chunk)
        expected = coupling808.filter_reference(tone808.filter_reference(
            body808.reference(frames, decay_raw=raw, changes=changes),
            tone_raw=tone, changes=tone_changes))
        error = max(abs(a - b) for a, b in zip(result, expected, strict=True))
        assert error < 1e-5, (raw, changes, error)
        return machine, result, error

    rendered = {}
    decay_cases = []
    for raw in (0, 16384, 32512, 1, 16385, 32511):
        frames = FRAMES if raw in (0, 16384, 32512) else 6144
        machine, result, error = render(raw, frames)
        measured = analysis.analyze(result, body808.SAMPLE_RATE)
        frequency = measured["frequency"]["median_hz"]
        decay = measured["decay_positive"]["time_constant_s"]
        expected_samples = coupling808.filter_reference(tone808.filter_reference(body808.reference(frames,raw)))
        expected_fit = analysis.analyze(expected_samples,body808.SAMPLE_RATE)
        expected_frequency = expected_fit["frequency"]["median_hz"]
        expected_decay = expected_fit["decay_positive"]["time_constant_s"]
        assert frequency is not None and abs(frequency - expected_frequency) < .02, (raw, frequency, expected_frequency)
        assert decay is not None and abs(decay - expected_decay) < .001, (raw, decay, expected_decay)
        output = FOLDER / f"filtered_{raw}_16384.f32"
        packed = struct.pack(f"<{len(result)}f", *result)
        output.write_bytes(packed)
        (FOLDER / f"samples_{raw}.f32").write_bytes(packed)
        decay_cases.append(dict(raw=raw, frames=frames, maximum_error_fs=error,
                               frequency_hz=frequency, decay_time_constant_s=decay,
                               expected_decay_time_constant_s=expected_decay,
                               raw_body_time_constant_s=body808.decay_tau(raw),
                               samples_path=str(output),
                               samples_sha256=hashlib.sha256(output.read_bytes()).hexdigest()))
        rendered[raw] = (machine, result, error)
    assert all(decay_cases[i]["decay_time_constant_s"] < decay_cases[i + 1]["decay_time_constant_s"]
               for i in range(2)), decay_cases
    stream, samples, maximum_error = rendered[16384]
    frequency, decay = decay_cases[1]["frequency_hz"], decay_cases[1]["decay_time_constant_s"]
    live, live_samples, live_error = render(0, 6400, {3200: 32512})
    assert abs(live_samples[3200] - body808.reference(32, decay_raw=32512)[0]) > .01, \
        "live DECAY edit restarted the body"

    tone_cases = []
    tone_runs = []
    for tone in (0, 32512):
        machine, result, error = render(16384, 8192, tone=tone)
        output = FOLDER / f"filtered_16384_{tone}.f32"
        output.write_bytes(struct.pack(f"<{len(result)}f", *result))
        tone_cases.append(dict(raw=tone, frames=len(result), maximum_error_fs=error,
                               cutoff_hz=tone808.cutoff(tone), peak_fs=max(map(abs, result)),
                               samples_path=str(output),
                               samples_sha256=hashlib.sha256(output.read_bytes()).hexdigest()))
        tone_runs.append(machine)
    assert tone_cases[0]["peak_fs"] < tone_cases[1]["peak_fs"], "Tone endpoints have no effect"
    live_tone, _, live_tone_error = render(16384, 6400, tone=0, tone_changes={3200: 32512})
    tone_runs.append(live_tone)

    triangle = runner()
    triangle_samples = []
    for block in range(FRAMES // 32):
        chunk, _ = triangle.call_raw(body_case("909-body", flags=int(block == 0), model=32512), True)
        triangle_samples.extend(chunk)
    triangle_reference = body909.reference(FRAMES)
    triangle_error = max(abs(a-b) for a,b in zip(triangle_samples, triangle_reference))
    assert triangle_error < 1e-5, triangle_error
    triangle_measured = analysis.analyze(triangle_samples, body909.SAMPLE_RATE)
    assert abs(triangle_measured["frequency"]["median_hz"] - body909.FREQUENCY) < .02
    assert abs(triangle_measured["decay_positive"]["time_constant_s"] - body909.TAU) < .001
    triangle_path = FOLDER / "samples_909.f32"
    triangle_path.write_bytes(struct.pack(f"<{len(triangle_samples)}f", *triangle_samples))
    triangle_retrigger, _ = triangle.call_raw(body_case("909-retrigger", model=32512), True)
    assert triangle_retrigger == triangle_samples[:32], "909 START did not reset phase/envelope"

    retrigger, _ = stream.call_raw(body_case("retrigger"), True)
    assert retrigger == samples[:32], "START must reset body and Tone for a possibly reassigned slot"
    pending, state = stream.call_raw(body_case("pending-909", flags=0, model=32512), True)
    assert pending == samples[32:64] and state[1] == 1, "MODEL changed before START"
    switched, state = stream.call_raw(body_case("switch-909", model=32512), True)
    assert switched == triangle_samples[:32] and state[1] == 2 and state[64] == 0 and state[80:82] == [0,0]
    triangle_state = state[32:34]
    other, state = stream.call_raw(body_case("other-slot", slot=15), True)
    assert other == samples[:32] and state[1] == 2 and state[32:34] == triangle_state
    continuing909, _ = stream.call_raw(body_case("909-interleaved", flags=0, model=32512), True)
    assert continuing909 == triangle_samples[32:64], "808 slot changed the 909 body"
    returned, _ = stream.call_raw(body_case("back-to-808"), True)
    assert returned == samples[:32], "model change left an old tail"
    # Editing the other slot's Decay cannot change this slot's continuing body.
    stream.call_raw(body_case("other-slot-controls", 32512, tone=32512, slot=15, flags=0), True)
    continued, _ = stream.call_raw(body_case("first-slot-continued", flags=0), True)
    assert continued == samples[32:64], "other slot's Tone/Decay changed this body"

    output = FOLDER / "samples.f32"
    output.write_bytes(struct.pack(f"<{len(samples)}f", *samples))
    report = dict(status="passed", scope="actual SHARC 808 and unshaped 909 bodies with synthetic SDK frames",
                  project_revision=cpu.revision(cpu.ROOT),
                  elekloader_revision=cpu.revision(cpu.ROOT / "vendor/elekloader"),
                  emulator_revision=cpu.revision(cpu.ROOT / "vendor/digikit"),
                  calls=policy.calls + live.calls + triangle.calls + sum(r[0].calls for r in rendered.values())
                        + sum(r.calls for r in tone_runs),
                  code_bytes=len(code), state_bytes=STATE_BYTES,
                  source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                  image_sha256=hashlib.sha256(code).hexdigest(),
                  samples_path=str(output), samples_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                  frames=FRAMES, sample_rate=body808.SAMPLE_RATE,
                  maximum_error_fs=maximum_error, maximum_error_limit_fs=1e-5,
                  frequency_hz=frequency, decay_time_constant_s=decay,
                  decay_cases=decay_cases, live_decay_change=dict(sample=3200, before_raw=0, after_raw=32512,
                                                               maximum_error_fs=live_error),
                  tone_cases=tone_cases, live_tone_change=dict(sample=3200, before_raw=0, after_raw=32512,
                                                             maximum_error_fs=live_tone_error),
                  body909=dict(frames=FRAMES, maximum_error_fs=triangle_error,
                               frequency_hz=triangle_measured["frequency"]["median_hz"],
                               decay_time_constant_s=triangle_measured["decay_positive"]["time_constant_s"],
                               samples_path=str(triangle_path),
                               samples_sha256=hashlib.sha256(triangle_path.read_bytes()).hexdigest(),
                               worst_instructions=triangle.worst_instructions),
                  worst_instructions=max(policy.worst_instructions, live.worst_instructions, triangle.worst_instructions,
                                         *(r[0].worst_instructions for r in rendered.values()),
                                         *(r.worst_instructions for r in tone_runs)),
                  c_reference=provenance,
                  checked=["analytic fixed-frequency damped-sine body", "provisional DECAY curve and fractions",
                           "continuous live DECAY edit", "source-derived Tone RC and continuous edits",
                           "unloaded C47 coupling after Tone", "provisional full-chain reset on every START", "all 16 independent slots",
                           "START-only MODEL latch", "provisional same-model retrigger",
                           "model-change body clear", "909 triangle and independent mixed models", "invalid-input atomicity",
                           "state/output guards", "SDK context preservation"],
                  unqualified=["808/909 circuit fidelity", "909 diode shaper, pitch/amp/attack circuits and controls",
                               "stock 808 Decay circuit and Tone pot taper calibration", "loaded output/buffer/C49/C50 network", "native OS integration",
                               "VST or hardware comparison", "real-device timing"])
    (FOLDER / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report, code


def main():
    try:
        print(json.dumps(component()[0]))
        return 0
    except cpu.Unavailable as error:
        print(json.dumps(dict(status="unavailable", reason=str(error))))
        return 77


if __name__ == "__main__":
    sys.exit(main())
