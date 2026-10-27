"""Execute the provisional unshaped 909 body as ColdFire ASM in digiemu."""
import hashlib
import json
from pathlib import Path
import struct

from . import audio, body909, cpu
from .analysis import analyze
from .coldfire_arithmetic import EMAC_SEED
from .coldfire_body808 import Runner as BodyRunner

SOURCE = cpu.ROOT / "targets/coldfire/body909.s"


class Runner(BodyRunner):
    def render(self, voice=0, start=0):
        assert 0 <= voice < 8 and start in (0, 1)
        uc = self.uc
        register = lambda name: getattr(self.regs, "UC_M68K_REG_" + name)
        state = self.STATES + 16 * voice
        before = bytes(uc.mem_read(self.STATES - 4, 136))
        uc.mem_write(self.OUTPUT - 4, b"\xa5" * 136)
        uc.mem_write(self.SNAPSHOT - 4, b"\xa5" * 44)
        uc.mem_write(self.STACK - 112, b"\xa5" * 144)
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
        uc.emu_start(self.BASE, self.STOP, timeout=10_000_000)
        assert not self.invalid, self.invalid
        assert uc.reg_read(register("PC")) == self.STOP, "body did not return before the test watchdog"
        assert uc.reg_read(register("A7")) == self.STACK + 4, "caller stack pointer changed"
        assert all(uc.reg_read(reg) == value for reg, value in saved.items()), "callee register changed"
        assert bytes(uc.mem_read(self.STACK, 20)) == arguments, "caller arguments changed"
        assert bytes(uc.mem_read(self.STACK - 112, 16)) == b"\xa5" * 16, "stack underflow"
        assert bytes(uc.mem_read(self.STACK + 20, 12)) == b"\xa5" * 12, "stack overflow"
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
    folder = Path(folder) if folder is not None else cpu.ROOT / "out/coldfire/body909"
    folder.mkdir(parents=True, exist_ok=True)
    wrapper_source = cpu.ROOT / "targets/coldfire/selector.s"
    wrapper = wrapper_source.read_text().split("    .globl x0x_selector\n")[0]
    wrapper = wrapper.replace("bsr x0x_selector", "bsr x0x_909_body")
    combined = folder / "probe.s"
    combined.write_text(wrapper + "\n" + SOURCE.read_text())
    image, _ = cpu.build_coldfire(folder, combined)
    runner, words, worst = Runner(image), [], 0
    assert runner.render() == [0] * 32, "untriggered state is not silent"
    frames = 24000
    for block in range(frames // 32):
        words.extend(runner.render(start=int(block == 0)))
        worst = max(worst, runner.steps)
    samples = [word / 2**31 for word in words]
    error = max(abs(a-b) for a,b in zip(samples,body909.reference(frames)))
    assert error <= 1e-5, f"909 waveform error {error} exceeds 1e-5 FS"
    measures = analyze(samples, body909.SAMPLE_RATE)
    assert measures["onset_sample"] == 0 and measures["onset_polarity"] == 1
    assert measures["full_scale_samples"] == 0
    frequency, tau = measures["frequency"]["median_hz"], measures["decay_positive"]["time_constant_s"]
    assert frequency is not None and abs(frequency-body909.FREQUENCY) <= .02, frequency
    assert tau is not None and abs(tau-body909.TAU) <= .001, tau
    assert runner.render(start=1) == words[:32], "retrigger differs"
    assert runner.render() == words[32:64], "retrigger continuation differs"
    # Cover exact fold extrema, including positive unity's Q31 clamp.
    for phase, sign in ((0, -1), (0x80000000, 1)):
        edge = Runner(image)
        edge.uc.mem_write(edge.STATES,struct.pack(">II",(phase-body909.PHASE_STEP) & 0xffffffff,0x20000000))
        first = edge.render()[0] / 2**31
        assert abs(first-sign * body909.GAIN * body909.RETENTION) <= 1e-9, first
    interleaved = Runner(image)
    for block in range(80):
        interleaved.render(7, int(block % 5 == 0))
        assert interleaved.render(0,int(block == 0)) == words[32*block:32*(block+1)]
    # Run the actual integer envelope into its nearest-even limit cycle.
    tail, last = Runner(image), []
    for block in range(4 * body909.SAMPLE_RATE // 32):
        out = tail.render(start=int(block == 0))
        if block >= (4 * body909.SAMPLE_RATE - 960) // 32:
            last.extend(out)
    amplitude = struct.unpack(">i",tail.uc.mem_read(tail.STATES + 4,4))[0]
    tail.render()
    assert amplitude == struct.unpack(">i",tail.uc.mem_read(tail.STATES + 4,4))[0]
    tail_peak = max(abs(x) for x in last) / 2**31
    assert 0 < tail_peak <= 1e-5, tail_peak
    samples_path = folder / "samples.json"
    samples_path.write_text(json.dumps(samples) + "\n")
    audio.write_wav(folder / "body909.wav",samples,body909.SAMPLE_RATE)
    report = dict(status="passed",scope="actual ColdFire ASM with owned state/output; no native OS",
        source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        emulator_revision=cpu.revision(cpu.ROOT / "vendor/digiemu"),
        image_sha256=hashlib.sha256(image).hexdigest(),frames=frames,
        waveform_peak_error_fs=error,frequency_hz=frequency,decay_tau_s=tau,
        onset_sample=measures["onset_sample"],peak_fs=measures["peak_fs"],
        maximum_instructions_per_block_with_wrapper=worst,
        tail_after_seconds=4,tail_amplitude_q31=amplitude,tail_peak_fs=tail_peak,
        samples=str(samples_path),wav=str(folder / "body909.wav"),
        checked=["zero-state silence","streamed analytic triangle and decay","phase wrap and exact fold extrema",
                 "output/state/stack guards","callee registers and complete EMAC context",
                 "independent interleaved voice","provisional START restart","bounded long tail"],
        unqualified=["909 diode shaping and circuit envelopes","Tune/Decay/Attack controls",
                     "stock 909 fidelity","native OS integration","hardware timing"],
        known_limit="nearest-even Q31 amplitude settles above zero; this is not exact tail silence")
    (folder / "report.json").write_text(json.dumps(report,indent=2) + "\n")
    return report


if __name__ == "__main__":
    print(json.dumps(run()))
