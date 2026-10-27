"""Execute the isolated unloaded C47/VR4 coupling as actual ColdFire ASM."""
import hashlib
import json
import math
from pathlib import Path
import struct

from . import body808, coupling808, cpu, tone808
from .coldfire_arithmetic import EMAC_SEED
from .coldfire_body808 import Runner as BodyRunner

SOURCE = cpu.ROOT / "targets/coldfire/coupling808.s"


class Runner(BodyRunner):
    def render(self, inputs, voice=0):
        assert len(inputs) == 32 and all(type(x) is int and -(1 << 31) <= x < 1 << 31 for x in inputs)
        assert 0 <= voice < 8
        uc = self.uc
        register = lambda name: getattr(self.regs, "UC_M68K_REG_" + name)
        state = self.STATES + 16 * voice
        before = bytes(uc.mem_read(self.STATES - 4, 136))
        uc.mem_write(self.OUTPUT - 4, b"\xa5" * 4 + struct.pack(">32i", *inputs) + b"\xa5" * 4)
        uc.mem_write(self.SNAPSHOT - 4, b"\xa5" * 44)
        uc.mem_write(self.STACK - 104, b"\xa5" * 128)
        arguments = struct.pack(">4I", self.STOP, state, self.OUTPUT, self.SNAPSHOT)
        uc.mem_write(self.STACK, arguments)
        uc.reg_write(register("SR"), 0x2700)
        saved = {register(name): 0x10203040 + i for i, name in enumerate(
            [*(f"D{i}" for i in range(2, 8)), *(f"A{i}" for i in range(2, 7))])}
        for reg, value in saved.items():
            uc.reg_write(reg, value)
        uc.reg_write(register("A7"), self.STACK)
        self.steps, self.invalid = 0, []
        self.allowed = [(state, state + 8), (self.OUTPUT, self.OUTPUT + 128),
                        (self.SNAPSHOT, self.SNAPSHOT + 36), (self.STACK - 88, self.STACK)]
        uc.emu_start(self.BASE, self.STOP, timeout=10_000_000)
        assert not self.invalid, self.invalid
        assert uc.reg_read(register("PC")) == self.STOP, "coupling did not return before the test watchdog"
        assert uc.reg_read(register("A7")) == self.STACK + 4, "caller stack pointer changed"
        assert all(uc.reg_read(reg) == value for reg, value in saved.items()), "callee register changed"
        assert bytes(uc.mem_read(self.STACK, 16)) == arguments, "caller arguments changed"
        assert bytes(uc.mem_read(self.STACK - 104, 16)) == b"\xa5" * 16, "stack underflow"
        assert bytes(uc.mem_read(self.STACK + 16, 8)) == b"\xa5" * 8, "stack overflow"
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
    folder = Path(folder) if folder is not None else cpu.ROOT / "out/coldfire/coupling808"
    folder.mkdir(parents=True,exist_ok=True)
    wrapper_source = cpu.ROOT / "targets/coldfire/selector.s"
    wrapper = wrapper_source.read_text().split("    .globl x0x_selector\n")[0]
    first, last = wrapper.index("    lea -12(%sp), %sp"), wrapper.index("    move.l %d0, 32(%a0)")
    wrapper = wrapper[:first] + """    lea -8(%sp), %sp
    move.l 12(%sp), %d0
    move.l %d0, (%sp)
    move.l 16(%sp), %d0
    move.l %d0, 4(%sp)
    bsr x0x_808_coupling
    lea 8(%sp), %sp
    movea.l 12(%sp), %a0
""" + wrapper[last:]
    combined = folder / "probe.s"
    combined.write_text(wrapper + "\n" + SOURCE.read_text())
    image, _ = cpu.build_coldfire(folder,combined)
    worst = 0
    def stream(inputs):
        nonlocal worst
        machine, words = Runner(image), []
        for n in range(0,len(inputs),32):
            words.extend(machine.render(inputs[n:n+32]))
            worst=max(worst,machine.steps)
        return words
    signal=[.25]+[0.]*511+[.25]*12000+[-.25]*12000+[0.]*12000
    signal += [.125*math.sin(2*math.pi*55*n/48000)+.125*math.sin(2*math.pi*1000*n/48000) for n in range(4096)]
    signal += [.25 if n%2 else -.25 for n in range(512)]
    signal += [0.]*((-len(signal))%32)
    inputs=[round(x*2**31) for x in signal]
    quantized=[x/2**31 for x in inputs]
    assert Runner(image).render([0]*32)==[0]*32
    words=stream(inputs)
    samples=[x/2**31 for x in words]
    expected=coupling808.filter_reference(quantized)
    error=max(abs(a-b) for a,b in zip(samples,expected))
    assert error<=1e-5, error
    assert max(map(abs,samples))<.5
    assert abs(samples[0]-.25*coupling808.B)<=1/2**31
    interleaved=Runner(image)
    for block in range(80):
        interleaved.render([-1<<29]*32,7)
        assert interleaved.render(inputs[32*block:32*(block+1)])==words[32*block:32*(block+1)]
    dc = Runner(image)
    for _ in range(96000//32):
        dc_tail = dc.render([1 << 29]*32)
    dc_residual = max(map(abs,dc_tail))/2**31
    assert dc_residual == 0, dc_residual
    composed=[]
    for decay,tone in [(d,16384) for d in (0,16384,32512)]+[(16384,t) for t in (0,32512)]:
        path=cpu.ROOT/f"out/coldfire/tone808/body_{decay}_{tone}.json"
        filtered=json.loads(path.read_text())
        assert len(filtered)>=24000 and len(filtered)%32==0, "run the ColdFire Tone component first"
        result=[x/2**31 for x in stream([round(x*2**31) for x in filtered])]
        expected=coupling808.filter_reference(tone808.filter_reference(body808.reference(len(result),decay),tone))
        composed_error=max(abs(a-b) for a,b in zip(result,expected))
        assert composed_error<=1e-5 and max(map(abs,result))<.5, (decay,tone,composed_error)
        output=folder/f"body_{decay}_{tone}.json"
        output.write_text(json.dumps(result)+"\n")
        composed.append(dict(decay_raw=decay,tone_raw=tone,frames=len(result),
            waveform_peak_error_fs=composed_error,peak_fs=max(map(abs,result)),samples=str(output),
            input_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    report=dict(status="passed",scope="actual ColdFire isolated unloaded C47/VR4 and composed 808 chain; no native OS",
        source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),image_sha256=hashlib.sha256(image).hexdigest(),
        emulator_revision=cpu.revision(cpu.ROOT/"vendor/digiemu"),frames=len(inputs),
        waveform_peak_error_fs=error,peak_fs=max(map(abs,samples)),composed=composed,
        dc_residual_after_seconds=2,dc_residual_fs=dc_residual,
        maximum_instructions_per_block_with_wrapper=worst,
        checked=["zero-state silence","independent capacitor/current reference","impulse/DC/sign steps/two-tone",
                 "streaming and independent interleaved voice","state/output/stack guards",
                 "callee registers and full EMAC preservation","actual body plus Tone plus coupling"],
        unqualified=["loaded output network","C49 buffer/shaper","complete 808 circuit","native OS integration"])
    (folder/"report.json").write_text(json.dumps(report,indent=2)+"\n")
    return report


if __name__ == "__main__":
    print(json.dumps(run()))
