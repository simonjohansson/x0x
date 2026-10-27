"""Execute the diode-shaped 909 body as ColdFire ASM in digiemu."""
import hashlib
import json
from pathlib import Path
import struct

from . import audio, body909, cpu
from .analysis import analyze
from .coldfire_body808 import Runner

SOURCE = cpu.ROOT / "targets/coldfire/body909.s"


def run(folder=None):
    folder = Path(folder) if folder is not None else cpu.ROOT / "out/coldfire/body909"
    folder.mkdir(parents=True, exist_ok=True)
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
    bsr x0x_909_body
    lea 16(%sp), %sp
    movea.l 20(%sp), %a0
""" + wrapper[last:]
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
    decay_cases=[]
    for raw in (0,1,16384,16385,32511,32512):
        case=Runner(image)
        rendered=[]
        for block in range(frames//32):
            rendered.extend(case.render(start=int(block==0),decay_raw=raw))
            worst=max(worst,case.steps)
        signal=[x/2**31 for x in rendered]
        expected=body909.reference(frames,raw)
        peak_error=max(abs(a-b) for a,b in zip(signal,expected))
        assert peak_error<=1e-5,(raw,peak_error)
        fit=analyze(signal[:min(frames,int(5*body909.decay_tau(raw)*48000))],48000)
        assert abs(fit["decay_positive"]["time_constant_s"]-body909.decay_tau(raw))<=.001,(raw,fit)
        (folder/f"samples_{raw}.json").write_text(json.dumps(signal)+"\n")
        decay_cases.append(dict(raw=raw,maximum_error_fs=peak_error,expected_tau_s=body909.decay_tau(raw)))
    live_runner=Runner(image)
    changes={4096:32512,8192:0}
    raw=16384
    live=[]
    for n in range(0,12288,32):
        raw=changes.get(n,raw)
        live.extend(v/2**31 for v in live_runner.render(start=int(n==0),decay_raw=raw))
    live_error=max(abs(a-b) for a,b in zip(live,body909.reference(len(live),changes=changes)))
    assert live_error<=1e-5,live_error
    assert runner.render(start=1) == words[:32], "retrigger differs"
    assert runner.render() == words[32:64], "retrigger continuation differs"
    # Cover exact fold extrema, including positive unity's Q31 clamp.
    for phase, sign in ((0, -1), (0x80000000, 1)):
        edge = Runner(image)
        edge.uc.mem_write(edge.STATES,struct.pack(">II",(phase-body909.PHASE_STEP) & 0xffffffff,0x20000000))
        first = edge.render()[0] / 2**31
        assert abs(first-sign * body909.diode_shape(1) * body909.GAIN * body909.RETENTION) <= 1e-9, first
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
    assert amplitude == 0 and tail_peak == 0, (amplitude,tail_peak)
    for raw in (0,16384,32512):
        residue = Runner(image)
        residue.uc.mem_write(residue.STATES,struct.pack(">II",0x40000000,1))
        assert residue.render(decay_raw=raw) == [0]*32, raw
        assert struct.unpack(">i",residue.uc.mem_read(residue.STATES+4,4))[0] == 0
    samples_path = folder / "samples.json"
    samples_path.write_text(json.dumps(samples) + "\n")
    audio.write_wav(folder / "body909.wav",samples,body909.SAMPLE_RATE)
    report = dict(status="passed",scope="actual ColdFire ASM with owned state/output; no native OS",
        source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        emulator_revision=cpu.revision(cpu.ROOT / "vendor/digiemu"),
        image_sha256=hashlib.sha256(image).hexdigest(),frames=frames,
        waveform_peak_error_fs=error,frequency_hz=frequency,decay_tau_s=tau,
        decay_cases=decay_cases,live_decay_maximum_error_fs=live_error,
        onset_sample=measures["onset_sample"],peak_fs=measures["peak_fs"],
        maximum_instructions_per_block_with_wrapper=worst,
        tail_after_seconds=4,tail_amplitude_q31=amplitude,tail_peak_fs=tail_peak,
        samples=str(samples_path),wav=str(folder / "body909.wav"),
        checked=["zero-state silence","diode KCL shaper after analytic triangle and unloaded RC Decay corners/fractions", "live Decay without START","phase wrap and exact fold extrema",
                 "output/state/stack guards","callee registers and complete EMAC context",
                 "independent interleaved voice","provisional START restart","exact silence after the rounding fixed point"],
        unqualified=["909 physical diode parameters and circuit envelopes","stock VCA/taper and Tune/Attack controls",
                     "stock 909 fidelity","native OS integration","hardware timing"])
    (folder / "report.json").write_text(json.dumps(report,indent=2) + "\n")
    return report


if __name__ == "__main__":
    print(json.dumps(run()))
