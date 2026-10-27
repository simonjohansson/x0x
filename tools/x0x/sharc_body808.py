"""Execute the first 808 body in SHARC instructions; no native OS or fidelity claim."""
from __future__ import annotations

import hashlib
import json
import math
import struct
import sys

from . import analysis, body808, cpu, sharc_callback as callback, sharc_selector as selector

SOURCE = cpu.ROOT / "targets/sharc/body808.s"
FOLDER = cpu.ROOT / "out/sharc/body808"
STATE_BYTES = 256
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
                                       extra_slot_state_offset=128)

    policy = runner()
    inputs = selector.cases()
    expected, provenance = selector.c_reference(FOLDER, inputs)
    for row, reference in zip(inputs, expected, strict=True):
        samples, state = policy.call_raw(row, state_writable=reference["notices"] == 1)
        assert state[:32] == reference["state"], row["label"]
        if samples is not None:
            assert all(math.isfinite(x) and abs(x) <= .25 for x in samples), row["label"]
            if not reference["notices"] or state[2 * row["slot"] + 1] == 2:
                assert samples == [0.0] * 32, row["label"]
            if reference["notices"] and state[2 * row["slot"] + 1] == 2:
                assert state[32 + 2 * row["slot"]:34 + 2 * row["slot"]] == [0, 0], row["label"]

    def body_case(label, raw=16384, **kwargs):
        row = selector.case(label, **kwargs)
        row["params"][1] = raw
        return row

    def render(raw, frames, changes=None):
        machine = runner()
        result = []
        current = raw
        for block in range(frames // 32):
            current = (changes or {}).get(block * 32, current)
            chunk, _ = machine.call_raw(body_case("body", current, flags=int(block == 0)), True)
            result.extend(chunk)
        expected = body808.reference(frames, decay_raw=raw, changes=changes)
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
        assert frequency is not None and abs(frequency - body808.FREQUENCY) < .02, (raw, frequency)
        assert decay is not None and abs(decay - body808.decay_tau(raw)) < .001, (raw, decay)
        output = FOLDER / f"samples_{raw}.f32"
        output.write_bytes(struct.pack(f"<{len(result)}f", *result))
        decay_cases.append(dict(raw=raw, frames=frames, maximum_error_fs=error,
                               frequency_hz=frequency, decay_time_constant_s=decay,
                               expected_decay_time_constant_s=body808.decay_tau(raw),
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

    retrigger, _ = stream.call_raw(body_case("retrigger"), True)
    assert retrigger == samples[:32], "same-model START must restart the provisional body"
    pending, state = stream.call_raw(body_case("pending-909", flags=0, model=32512), True)
    assert pending == samples[32:64] and state[1] == 1, "MODEL changed before START"
    silent, state = stream.call_raw(body_case("switch-909", model=32512), True)
    assert silent == [0.0] * 32 and state[1] == 2 and state[32:34] == [0, 0]
    other, state = stream.call_raw(body_case("other-slot", slot=15), True)
    assert other == samples[:32] and state[1] == 2 and state[32:34] == [0, 0]
    returned, _ = stream.call_raw(body_case("back-to-808"), True)
    assert returned == samples[:32], "model change left an old tail"
    # Editing the other slot's Decay cannot change this slot's continuing body.
    stream.call_raw(body_case("other-slot-decay", 32512, slot=15, flags=0), True)
    continued, _ = stream.call_raw(body_case("first-slot-continued", flags=0), True)
    assert continued == samples[32:64], "other slot's DECAY changed this body"

    output = FOLDER / "samples.f32"
    output.write_bytes(struct.pack(f"<{len(samples)}f", *samples))
    report = dict(status="passed", scope="actual SHARC 808 body with synthetic SDK frames",
                  project_revision=cpu.revision(cpu.ROOT),
                  elekloader_revision=cpu.revision(cpu.ROOT / "vendor/elekloader"),
                  emulator_revision=cpu.revision(cpu.ROOT / "vendor/digikit"),
                  calls=policy.calls + live.calls + sum(r[0].calls for r in rendered.values()),
                  code_bytes=len(code), state_bytes=STATE_BYTES,
                  source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                  image_sha256=hashlib.sha256(code).hexdigest(),
                  samples_path=str(output), samples_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                  frames=FRAMES, sample_rate=body808.SAMPLE_RATE,
                  maximum_error_fs=maximum_error, maximum_error_limit_fs=1e-5,
                  frequency_hz=frequency, decay_time_constant_s=decay,
                  decay_cases=decay_cases, live_decay_change=dict(sample=3200, before_raw=0, after_raw=32512,
                                                               maximum_error_fs=live_error),
                  worst_instructions=max(policy.worst_instructions, live.worst_instructions,
                                         *(r[0].worst_instructions for r in rendered.values())),
                  instruction_bound=selector.BOUND, c_reference=provenance,
                  checked=["analytic fixed-frequency damped-sine body", "provisional DECAY curve and fractions",
                           "continuous live DECAY edit", "all 16 independent slots",
                           "START-only MODEL latch", "provisional same-model retrigger",
                           "model-change body clear", "909 silence", "invalid-input atomicity",
                           "state/output guards", "SDK context preservation"],
                  unqualified=["808 circuit fidelity", "stock Decay/Tone circuit response", "native OS integration",
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
