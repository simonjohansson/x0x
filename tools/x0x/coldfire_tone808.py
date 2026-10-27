"""Execute the source-derived 808 Tone RC filter as actual ColdFire ASM."""
import hashlib
import json
import math
from pathlib import Path
import struct

from . import body808, cpu, tone808
from .coldfire_arithmetic import EMAC_SEED
from .coldfire_body808 import Runner as BodyRunner

SOURCE = cpu.ROOT / "targets/coldfire/tone808.s"


class Runner(BodyRunner):
    """Reuse instruction/write instrumentation; Tone owns one state word per voice."""

    def render(self, inputs, tone_raw=16384, voice=0):
        assert len(inputs) == 32 and all(type(x) is int and -(1 << 31) <= x < 1 << 31 for x in inputs)
        assert 0 <= voice < 8 and 0 <= tone_raw <= 32512
        uc = self.uc
        register = lambda name: getattr(self.regs, "UC_M68K_REG_" + name)
        state = self.STATES + 16 * voice
        before = bytes(uc.mem_read(self.STATES - 4, 136))
        uc.mem_write(self.OUTPUT - 4, b"\xa5" * 4 + struct.pack(">32i", *inputs) + b"\xa5" * 4)
        uc.mem_write(self.SNAPSHOT - 4, b"\xa5" * 44)
        uc.mem_write(self.STACK - 108, b"\xa5" * 136)
        arguments = struct.pack(">5I", self.STOP, state, self.OUTPUT, tone_raw, self.SNAPSHOT)
        uc.mem_write(self.STACK, arguments)
        uc.reg_write(register("SR"), 0x2700)
        saved = {register(name): 0x10203040 + i for i, name in enumerate(
            [*(f"D{i}" for i in range(2, 8)), *(f"A{i}" for i in range(2, 7))])}
        for reg, value in saved.items():
            uc.reg_write(reg, value)
        uc.reg_write(register("A7"), self.STACK)
        self.steps, self.invalid = 0, []
        self.allowed = [(state, state + 4), (self.OUTPUT, self.OUTPUT + 128),
                        (self.SNAPSHOT, self.SNAPSHOT + 36), (self.STACK - 92, self.STACK)]
        uc.emu_start(self.BASE, self.STOP, timeout=10_000_000)
        assert not self.invalid, self.invalid
        assert uc.reg_read(register("PC")) == self.STOP, "Tone did not return before the test watchdog"
        assert uc.reg_read(register("A7")) == self.STACK + 4, "caller stack pointer changed"
        assert all(uc.reg_read(reg) == value for reg, value in saved.items()), "callee register changed"
        assert bytes(uc.mem_read(self.STACK, 20)) == arguments, "caller arguments changed"
        assert bytes(uc.mem_read(self.STACK - 108, 16)) == b"\xa5" * 16, "stack underflow"
        assert bytes(uc.mem_read(self.STACK + 20, 8)) == b"\xa5" * 8, "stack overflow"
        snapshot = bytes(uc.mem_read(self.SNAPSHOT - 4, 44))
        assert snapshot[:4] == snapshot[-4:] == b"\xa5" * 4, "EMAC snapshot guard changed"
        assert struct.unpack(">8I", snapshot[4:36]) == EMAC_SEED, "EMAC context changed"
        after = bytes(uc.mem_read(self.STATES - 4, 136))
        at = state - (self.STATES - 4)
        assert before[:at] == after[:at] and before[at + 4:] == after[at + 4:], "other voice/guard changed"
        output = bytes(uc.mem_read(self.OUTPUT - 4, 136))
        assert output[:4] == output[-4:] == b"\xa5" * 4, "output guard changed"
        return list(struct.unpack(">32i", output[4:-4]))


def run(folder=None):
    folder = Path(folder) if folder is not None else cpu.ROOT / "out/coldfire/tone808"
    folder.mkdir(parents=True, exist_ok=True)
    wrapper_source = cpu.ROOT / "targets/coldfire/selector.s"
    wrapper = wrapper_source.read_text().split("    .globl x0x_selector\n")[0]
    wrapper = wrapper.replace("bsr x0x_selector", "bsr x0x_808_tone")
    combined = folder / "probe.s"
    combined.write_text(wrapper + "\n" + SOURCE.read_text())
    image, _ = cpu.build_coldfire(folder, combined)
    worst = 0

    def stream(inputs, raw, changes=None):
        nonlocal worst
        machine, words = Runner(image), []
        current = raw
        for n in range(0, len(inputs), 32):
            current = (changes or {}).get(n, current)
            words.extend(machine.render(inputs[n:n + 32], current))
            worst = max(worst, machine.steps)
        return words

    # Impulse, step, rich body, and opposite-sign near-full-scale values.
    signal = [.5] + [0.] * 511 + [.25] * 512 + [0.] * 512
    signal += [.2 * math.sin(2 * math.pi * 55 * n / 48000)
               + .2 * math.sin(2 * math.pi * 1000 * n / 48000) for n in range(4096)]
    signal += [.99] * 512 + [.99 if n % 2 else -.99 for n in range(512)] + [0.] * 1536
    inputs = [round(x * 2**31) for x in signal]
    quantized = [x / 2**31 for x in inputs]
    cases = []
    for raw in (0, 1, 16384, 16385, 32511, 32512):
        assert Runner(image).render([0] * 32, raw) == [0] * 32
        words = stream(inputs, raw)
        samples = [x / 2**31 for x in words]
        expected = tone808.filter_reference(quantized, raw)
        error = max(abs(a - b) for a, b in zip(samples, expected))
        assert error <= 1e-5, (raw, error)
        # The first impulse sample directly checks the unsigned long-division coefficient.
        coefficient_error = abs(2 * samples[0] - tone808.coefficient(raw))
        assert coefficient_error <= 2 / 2**31, (raw, coefficient_error)
        cases.append(dict(tone_raw=raw, cutoff_hz=tone808.cutoff(raw),
                          waveform_peak_error_fs=error, coefficient_error=coefficient_error))
        if raw == 16384:
            default_words = words
    changes = {2048: 32512, 4096: 0}
    live = [x / 2**31 for x in stream(inputs, 16384, changes)]
    expected = tone808.filter_reference(quantized, 16384, changes)
    live_error = max(abs(a - b) for a, b in zip(live, expected))
    assert live_error <= 1e-5, live_error
    interleaved = Runner(image)
    for block in range(80):
        interleaved.render([-1 << 30] * 32, 32512 if block % 2 else 0, 7)
        assert interleaved.render(inputs[32 * block:32 * (block + 1)]) == default_words[32 * block:32 * (block + 1)]
    composed = []
    settings = [(decay, 16384) for decay in (0, 16384, 32512)] + [(16384, tone) for tone in (0, 32512)]
    for decay, tone in settings:
        path = cpu.ROOT / f"out/coldfire/body808/samples_{decay}.json"
        body = json.loads(path.read_text())
        assert len(body) >= 24000 and len(body) % 32 == 0, "run test:808:coldfire first"
        filtered = [x / 2**31 for x in stream([round(x * 2**31) for x in body], tone)]
        expected = tone808.filter_reference(body808.reference(len(body), decay), tone)
        error = max(abs(a - b) for a, b in zip(filtered, expected))
        assert error <= 1e-5, (decay, tone, error)
        output = folder / f"body_{decay}_{tone}.json"
        output.write_text(json.dumps(filtered) + "\n")
        composed.append(dict(decay_raw=decay, tone_raw=tone, frames=len(filtered),
                             waveform_peak_error_fs=error, samples=str(output),
                             input_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    report = dict(status="passed", scope="actual ColdFire Tone ASM and composed body; no native OS",
                  project_revision=cpu.revision(cpu.ROOT),
                  emulator_revision=cpu.revision(cpu.ROOT / "vendor/digiemu"),
                  source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                  wrapper_source_sha256=hashlib.sha256(wrapper_source.read_bytes()).hexdigest(),
                  image_sha256=hashlib.sha256(image).hexdigest(), frames=len(inputs),
                  cases=cases, live_tone_peak_error_fs=live_error, composed=composed,
                  maximum_instructions_per_block_with_wrapper=worst,
                  checked=["source-derived RC response", "unsigned coefficient division",
                           "impulse/step/two-tone/full-scale differences", "live Tone with persistent state",
                           "state/output/stack guards", "callee registers and full EMAC preservation",
                           "independent interleaved voice", "actual body plus Tone output"],
                  unqualified=["physical pot taper calibration", "remaining 808 circuit", "native OS integration", "hardware timing"])
    (folder / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    print(json.dumps(run()))
