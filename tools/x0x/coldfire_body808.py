"""Execute the provisional 808 body as actual ColdFire ASM in digiemu."""
import hashlib
import json
from pathlib import Path
import struct

from . import audio, body808, cpu
from .analysis import analyze
from .coldfire_arithmetic import EMAC_SEED

SOURCE = cpu.ROOT / "targets/coldfire/body808.s"


class Runner:
    BASE, OUTPUT, STATES = 0x40000400, 0x40010004, 0x40011004
    SNAPSHOT, STACK, STOP = 0x40018004, 0x40020000, 0x40030000

    def __init__(self, image, state_words=2):
        self.state_words = state_words
        harness = cpu.require_module("emu.harness", "digiemu")
        from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
        from unicorn import m68k_const

        self.regs = m68k_const
        self.machine = harness.Machine()
        self.uc = self.machine.uc
        self.machine.ensure(0x40000000)
        self.uc.mem_write(self.BASE, image)
        self.uc.mem_write(self.STATES - 4, b"\xa5" * 136)
        for voice in range(8):
            self.uc.mem_write(self.STATES + 16 * voice, bytes(state_words * 4))
        self.steps = 0
        self.invalid = []
        self.allowed = []
        self.uc.hook_add(UC_HOOK_CODE, self._step)
        self.uc.hook_add(UC_HOOK_MEM_WRITE, self._write)

    def _step(self, *_):
        self.steps += 1

    def _write(self, _uc, _access, address, size, _value, _data):
        if not any(lo <= address and address + size <= hi for lo, hi in self.allowed):
            self.invalid.append((address, size))

    def render(self, voice=0, start=0, decay_raw=16384):
        assert 0 <= voice < 8 and start in (0, 1) and 0 <= decay_raw <= 32512
        uc = self.uc
        register = lambda name: getattr(self.regs, "UC_M68K_REG_" + name)
        state = self.STATES + 16 * voice
        before = bytes(uc.mem_read(self.STATES - 4, 136))
        uc.mem_write(self.OUTPUT - 4, b"\xa5" * 136)
        uc.mem_write(self.SNAPSHOT - 4, b"\xa5" * 44)
        uc.mem_write(self.STACK - 112, b"\xa5" * 144)
        arguments = struct.pack(">6I", self.STOP, state, self.OUTPUT, start, decay_raw, self.SNAPSHOT)
        uc.mem_write(self.STACK, arguments)
        uc.reg_write(register("SR"), 0x2700)
        saved = {register(name): 0x10203040 + i for i, name in enumerate(
            [*(f"D{i}" for i in range(2, 8)), *(f"A{i}" for i in range(2, 7))])}
        for reg, value in saved.items():
            uc.reg_write(reg, value)
        uc.reg_write(register("A7"), self.STACK)
        self.steps, self.invalid = 0, []
        self.allowed = [(state, state + 4*self.state_words), (self.OUTPUT, self.OUTPUT + 128),
                        (self.SNAPSHOT, self.SNAPSHOT + 36), (self.STACK - 96, self.STACK)]
        uc.emu_start(self.BASE, self.STOP, timeout=10_000_000)
        assert not self.invalid, self.invalid
        assert uc.reg_read(register("PC")) == self.STOP, "body did not return before the test watchdog"
        assert uc.reg_read(register("A7")) == self.STACK + 4, "caller stack pointer changed"
        assert all(uc.reg_read(reg) == value for reg, value in saved.items()), "callee register changed"
        assert bytes(uc.mem_read(self.STACK, 24)) == arguments, "caller arguments changed"
        assert bytes(uc.mem_read(self.STACK - 112, 16)) == b"\xa5" * 16, "stack underflow"
        assert bytes(uc.mem_read(self.STACK + 24, 8)) == b"\xa5" * 8, "stack overflow"
        snapshot = bytes(uc.mem_read(self.SNAPSHOT - 4, 44))
        assert snapshot[:4] == snapshot[-4:] == b"\xa5" * 4, "EMAC snapshot guard changed"
        assert struct.unpack(">8I", snapshot[4:36]) == EMAC_SEED, "EMAC context changed"
        after = bytes(uc.mem_read(self.STATES - 4, 136))
        at = state - (self.STATES - 4)
        assert before[:at] == after[:at] and before[at + 4*self.state_words:] == after[at + 4*self.state_words:], "other voice/guard changed"
        output = bytes(uc.mem_read(self.OUTPUT - 4, 136))
        assert output[:4] == output[-4:] == b"\xa5" * 4, "output guard changed"
        return list(struct.unpack(">32i", output[4:-4]))


def run(folder=None):
    folder = Path(folder) if folder is not None else cpu.ROOT / "out/coldfire/body808"
    folder.mkdir(parents=True, exist_ok=True)
    # Reuse the existing EMAC seed/snapshot wrapper with one extra body argument.
    wrapper_source = cpu.ROOT / "targets/coldfire/selector.s"
    wrapper = wrapper_source.read_text().split("    .globl x0x_selector\n")[0]
    first = wrapper.index("    lea -12(%sp), %sp")
    last = wrapper.index("    move.l %d0, 32(%a0)")
    wrapper = wrapper[:first] + """    lea -16(%sp), %sp
    move.l 20(%sp), %d0
    move.l %d0, 0(%sp)
    move.l 24(%sp), %d0
    move.l %d0, 4(%sp)
    move.l 28(%sp), %d0
    move.l %d0, 8(%sp)
    move.l 32(%sp), %d0
    move.l %d0, 12(%sp)
    bsr x0x_808_body
    lea 16(%sp), %sp
    movea.l 20(%sp), %a0
""" + wrapper[last:]
    combined = folder / "probe.s"
    combined.write_text(wrapper + "\n" + SOURCE.read_text())
    image, _ = cpu.build_coldfire(folder, combined)
    cases, default_words, worst = [], [], 0
    frames = body808.SAMPLE_RATE // 2
    for raw in (0, 1, 16384, 16385, 32511, 32512):
        runner = Runner(image, state_words=3)
        assert runner.render(decay_raw=raw) == [0] * 32, "untriggered zero state is not silent"
        words = []
        for block in range(frames // 32):
            words.extend(runner.render(start=int(block == 0), decay_raw=raw))
            assert struct.unpack(">I",runner.uc.mem_read(runner.STATES+8,4))[0] == max(48-(block+1)*32,0)
            worst = max(worst, runner.steps)
        samples = [word / 2**31 for word in words]
        expected = body808.reference(len(samples), raw)
        error = max(abs(a - b) for a, b in zip(samples, expected))
        # Stable feedback accumulates Q31 quantization; no gain/time fitting.
        assert error <= 1e-5, f"decay {raw}: waveform error {error} exceeds 1e-5 FS"
        measures = analyze(samples, body808.SAMPLE_RATE)
        assert measures["onset_sample"] == 0 and measures["onset_polarity"] == 1
        assert measures["full_scale_samples"] == 0
        frequency = measures["frequency"]["median_hz"]
        tau = measures["decay_positive"]["time_constant_s"]
        assert frequency is not None and abs(frequency - body808.FREQUENCY) <= .02, frequency
        assert tau is not None and abs(tau - body808.decay_tau(raw)) <= .001, tau
        path = folder / f"samples_{raw}.json"
        path.write_text(json.dumps(samples) + "\n")
        cases.append(dict(decay_raw=raw, waveform_peak_error_fs=error, frequency_hz=frequency,
                          decay_tau_s=tau, expected_tau_s=body808.decay_tau(raw), samples=str(path)))
        assert runner.render(start=1, decay_raw=raw) == words[:32], "retrigger differs"
        assert runner.render(decay_raw=raw) == words[32:64], "retrigger continuation differs"
        if raw == 16384:
            default_words, default_samples, default_measures = words, samples, measures
            default_case = cases[-1]
    interleaved = Runner(image, state_words=3)
    for block in range(20):
        interleaved.render(7, int(block % 5 == 0), 32512)
        assert interleaved.render(0, int(block == 0)) == default_words[32 * block:32 * (block + 1)]
    runner, live, raw = Runner(image, state_words=3), [], 16384
    changes = {8000: 32512, 16000: 0}
    for sample in range(0, frames, 32):
        raw = changes.get(sample, raw)
        live.extend(word / 2**31 for word in runner.render(start=int(sample == 0), decay_raw=raw))
    expected = body808.reference(frames, 16384, changes)
    live_error = max(abs(a - b) for a, b in zip(live, expected))
    assert live_error <= 1e-5, f"live decay error {live_error} exceeds 1e-5 FS"
    (folder / "samples_live.json").write_text(json.dumps(live) + "\n")
    samples_path = folder / "samples.json"
    samples_path.write_text(json.dumps(default_samples) + "\n")
    audio.write_wav(folder / "body808.wav", default_samples, body808.SAMPLE_RATE)
    report = dict(status="passed", scope="actual ColdFire ASM with owned state/output; no native OS",
                  project_revision=cpu.revision(cpu.ROOT),
                  emulator_revision=cpu.revision(cpu.ROOT / "vendor/digiemu"),
                  source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                  wrapper_source_sha256=hashlib.sha256(wrapper_source.read_bytes()).hexdigest(),
                  image_sha256=hashlib.sha256(image).hexdigest(), frames=frames,
                  cases=cases, live_decay_peak_error_fs=live_error,
                  waveform_peak_error_fs=default_case["waveform_peak_error_fs"],
                  frequency_hz=default_case["frequency_hz"], decay_tau_s=default_case["decay_tau_s"],
                  onset_sample=default_measures["onset_sample"], peak_fs=default_measures["peak_fs"],
                  maximum_instructions_per_block_with_wrapper=worst,
                  samples=str(samples_path), wav=str(folder / "body808.wav"),
                  checked=["zero state silence", "streamed analytical waveform", "onset/frequency/decay",
                           "output/state/stack guards", "callee registers and full EMAC preservation",
                           "independent interleaved voice", "provisional phase-reset retrigger",
                           "min/mid/max and fractional Decay", "live Decay without START"],
                  unqualified=["stock 808 timbre", "Tone/Attack", "native OS integration", "hardware timing"])
    (folder / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    print(json.dumps(run()))
