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

    def __init__(self, image):
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
            self.uc.mem_write(self.STATES + 16 * voice, bytes(8))
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

    def render(self, voice=0, start=0):
        assert 0 <= voice < 8 and start in (0, 1)
        uc = self.uc
        register = lambda name: getattr(self.regs, "UC_M68K_REG_" + name)
        state = self.STATES + 16 * voice
        before = bytes(uc.mem_read(self.STATES - 4, 136))
        uc.mem_write(self.OUTPUT - 4, b"\xa5" * 136)
        uc.mem_write(self.SNAPSHOT - 4, b"\xa5" * 44)
        uc.mem_write(self.STACK - 108, b"\xa5" * 136)
        arguments = struct.pack(">5I", self.STOP, state, self.OUTPUT, start, self.SNAPSHOT)
        uc.mem_write(self.STACK, arguments)
        uc.reg_write(register("SR"), 0x2700)
        saved = {register(name): 0x10203040 + i for i, name in enumerate(
            [*(f"D{i}" for i in range(2, 8)), *(f"A{i}" for i in range(2, 7))])}
        for reg, value in saved.items():
            uc.reg_write(reg, value)
        uc.reg_write(register("A7"), self.STACK)
        self.steps, self.invalid = 0, []
        self.allowed = [(state, state + 8), (self.OUTPUT, self.OUTPUT + 128),
                        (self.SNAPSHOT, self.SNAPSHOT + 36), (self.STACK - 92, self.STACK)]
        uc.emu_start(self.BASE, self.STOP, count=1024)
        assert not self.invalid, self.invalid
        assert uc.reg_read(register("PC")) == self.STOP, "body exceeded instruction bound"
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
        assert before[:at] == after[:at] and before[at + 8:] == after[at + 8:], "other voice/guard changed"
        output = bytes(uc.mem_read(self.OUTPUT - 4, 136))
        assert output[:4] == output[-4:] == b"\xa5" * 4, "output guard changed"
        return list(struct.unpack(">32i", output[4:-4]))


def run(folder=None):
    folder = Path(folder) if folder is not None else cpu.ROOT / "out/coldfire/body808"
    folder.mkdir(parents=True, exist_ok=True)
    # The existing selector wrapper has the same three arguments and seeds all EMAC state.
    wrapper_source = cpu.ROOT / "targets/coldfire/selector.s"
    wrapper = wrapper_source.read_text().split("    .globl x0x_selector\n")[0]
    wrapper = wrapper.replace("bsr x0x_selector", "bsr x0x_808_body")
    combined = folder / "probe.s"
    combined.write_text(wrapper + "\n" + SOURCE.read_text())
    image, _ = cpu.build_coldfire(folder, combined)
    runner = Runner(image)
    assert runner.render() == [0] * 32, "untriggered zero state is not silent"
    words, worst = [], 0
    for block in range(body808.SAMPLE_RATE // 32):
        words.extend(runner.render(start=int(block == 0)))
        worst = max(worst, runner.steps)
    samples = [word / 2**31 for word in words]
    expected = body808.reference(len(samples))
    error = max(abs(a - b) for a, b in zip(samples, expected))
    # A stable recurrence accumulates per-sample Q31 quantization; no gain/time fitting.
    assert error <= 1e-5, f"waveform error {error} exceeds 1e-5 FS"
    measures = analyze(samples, body808.SAMPLE_RATE)
    assert measures["onset_sample"] == 0 and measures["onset_polarity"] == 1
    assert measures["full_scale_samples"] == 0
    frequency = measures["frequency"]["median_hz"]
    tau = measures["decay_positive"]["time_constant_s"]
    assert frequency is not None and abs(frequency - body808.FREQUENCY) <= .02, frequency
    assert tau is not None and abs(tau - body808.TAU) <= .001, tau
    # A second state is called between blocks; the first voice must remain bit-identical.
    interleaved = Runner(image)
    for block in range(20):
        interleaved.render(7, int(block % 5 == 0))
        assert interleaved.render(0, int(block == 0)) == words[32 * block:32 * (block + 1)]
    assert runner.render(start=1) == words[:32], "retrigger did not restart the provisional body"
    assert runner.render() == words[32:64], "retrigger continuation differs"
    samples_path = folder / "samples.json"
    samples_path.write_text(json.dumps(samples) + "\n")
    audio.write_wav(folder / "body808.wav", samples, body808.SAMPLE_RATE)
    report = dict(status="passed", scope="actual ColdFire ASM with owned state/output; no native OS",
                  project_revision=cpu.revision(cpu.ROOT),
                  emulator_revision=cpu.revision(cpu.ROOT / "vendor/digiemu"),
                  source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                  wrapper_source_sha256=hashlib.sha256(wrapper_source.read_bytes()).hexdigest(),
                  image_sha256=hashlib.sha256(image).hexdigest(), frames=len(samples),
                  waveform_peak_error_fs=error, frequency_hz=frequency, decay_tau_s=tau,
                  onset_sample=measures["onset_sample"], peak_fs=measures["peak_fs"],
                  maximum_instructions_per_block_with_wrapper=worst,
                  samples=str(samples_path), wav=str(folder / "body808.wav"),
                  checked=["zero state silence", "streamed analytical waveform", "onset/frequency/decay",
                           "output/state/stack guards", "callee registers and full EMAC preservation",
                           "independent interleaved voice", "provisional phase-reset retrigger"],
                  unqualified=["stock 808 timbre", "controls", "native OS integration", "hardware timing"])
    (folder / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    print(json.dumps(run()))
