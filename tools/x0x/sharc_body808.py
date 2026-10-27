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

    stream = runner()
    samples = []
    for block in range(FRAMES // 32):
        chunk, _ = stream.call_raw(selector.case("body", flags=int(block == 0)), True)
        samples.extend(chunk)
    reference = body808.reference(FRAMES)
    maximum_error = max(abs(a - b) for a, b in zip(samples, reference, strict=True))
    assert maximum_error < 1e-5, maximum_error
    measured = analysis.analyze(samples, body808.SAMPLE_RATE)
    frequency = measured["frequency"]["median_hz"]
    decay = measured["decay_positive"]["time_constant_s"]
    assert frequency is not None and abs(frequency - body808.FREQUENCY) < .02, frequency
    assert decay is not None and abs(decay - body808.TAU) < .001, decay

    retrigger, _ = stream.call_raw(selector.case("retrigger"), True)
    assert retrigger == samples[:32], "same-model START must restart the provisional body"
    pending, state = stream.call_raw(selector.case("pending-909", flags=0, model=32512), True)
    assert pending == samples[32:64] and state[1] == 1, "MODEL changed before START"
    silent, state = stream.call_raw(selector.case("switch-909", model=32512), True)
    assert silent == [0.0] * 32 and state[1] == 2 and state[32:34] == [0, 0]
    other, state = stream.call_raw(selector.case("other-slot", slot=15), True)
    assert other == samples[:32] and state[1] == 2 and state[32:34] == [0, 0]
    returned, _ = stream.call_raw(selector.case("back-to-808"), True)
    assert returned == samples[:32], "model change left an old tail"

    output = FOLDER / "samples.f32"
    output.write_bytes(struct.pack(f"<{len(samples)}f", *samples))
    report = dict(status="passed", scope="actual SHARC 808 body with synthetic SDK frames",
                  project_revision=cpu.revision(cpu.ROOT),
                  elekloader_revision=cpu.revision(cpu.ROOT / "vendor/elekloader"),
                  emulator_revision=cpu.revision(cpu.ROOT / "vendor/digikit"),
                  calls=policy.calls + stream.calls, code_bytes=len(code), state_bytes=STATE_BYTES,
                  source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                  image_sha256=hashlib.sha256(code).hexdigest(),
                  samples_path=str(output), samples_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                  frames=FRAMES, sample_rate=body808.SAMPLE_RATE,
                  maximum_error_fs=maximum_error, maximum_error_limit_fs=1e-5,
                  frequency_hz=frequency, decay_time_constant_s=decay,
                  worst_instructions=max(policy.worst_instructions, stream.worst_instructions),
                  instruction_bound=selector.BOUND, c_reference=provenance,
                  checked=["analytic fixed-frequency damped-sine body", "all 16 independent slots",
                           "START-only MODEL latch", "provisional same-model retrigger",
                           "model-change body clear", "909 silence", "invalid-input atomicity",
                           "state/output guards", "SDK context preservation"],
                  unqualified=["808 circuit fidelity", "Tone/Decay control response", "native OS integration",
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
