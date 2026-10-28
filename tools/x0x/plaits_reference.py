"""Render pinned third-party research classes, without changing production DSP."""
import hashlib
import json
import math
import os
from pathlib import Path
import shlex
import struct
import subprocess
import tarfile
import tempfile

from . import analysis, audio, body808, body909, coupling808, cpu, tone808

ROOT = cpu.ROOT
FOLDER = ROOT / "out/reference/plaits"
HARNESS = ROOT / "tests/reference/plaits_drums.cc"
RATE, FRAMES, BLOCK, SEED = 48000, 96000, 12, 33
CASES = {
    "default": (.5, .5, 1, 0),
    "short": (.5, 0, 1, 0),
    "long": (.5, 1, 1, 0),
    "dark": (0, .5, 1, 0),
    "bright": (1, .5, 1, 0),
    "no-fm": (.5, .5, 0, 0),
    "retrigger": (.5, .5, 1, 1),
}


def run():
    sources = {row["id"]: row for row in json.loads((ROOT / "research/manifest.json").read_text())}
    archives = [sources["S47"], sources["S48"]]
    for source in archives:
        path = ROOT / "research" / source["path"]
        if not path.exists():
            raise cpu.Unavailable("missing reference archive; see docs/reference-renders.md: " + str(path))
        if hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError("reference archive hash mismatch: " + str(path))
    FOLDER.mkdir(parents=True, exist_ok=True)
    compiler = shlex.split(os.environ.get("CC", "clang")) + ["--driver-mode=g++"]
    flags = ["-std=c++11", "-O2", "-DTEST", "-fno-strict-aliasing", "-ffp-contract=off"]
    binary = FOLDER / "render"
    with tempfile.TemporaryDirectory(prefix="sources-", dir=FOLDER) as temporary:
        tree = Path(temporary)
        for source, target in zip(archives, [tree, tree / "stmlib"]):
            with tarfile.open(ROOT / "research" / source["path"]) as archive:
                for member in archive:
                    parts = Path(member.name).parts
                    if len(parts) < 2:
                        continue
                    member.name = str(Path(*parts[1:]))
                    archive.extract(member, target, filter="data")
        # The original four inspected snapshots must match the full source archive.
        for sid in ("S43", "S44", "S45", "S46"):
            source = sources[sid]
            actual = tree / source["locators"]
            assert hashlib.sha256(actual.read_bytes()).hexdigest() == source["sha256"], sid
        translation_units = [HARNESS, tree / "plaits/resources.cc",
                             tree / "stmlib/dsp/units.cc", tree / "stmlib/utils/random.cc"]
        cpu.command([*compiler, *flags, "-I", tree, *translation_units, "-o", binary])
        sanitized = FOLDER / "render-sanitized"
        cpu.command([*compiler, *flags, "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
                     "-I", tree, *translation_units, "-o", sanitized])
    def render(executable, model, settings, seed=SEED):
        process = subprocess.run([str(executable), model, *map(str, settings), str(seed)],
                                 capture_output=True, timeout=30, check=False)
        if process.returncode:
            raise RuntimeError("reference render failed: " + process.stderr.decode(errors="replace"))
        assert len(process.stdout) == FRAMES * 4, "incomplete reference capture"
        return process.stdout

    measurements, captured = {}, {}
    for model in ("analog", "synthetic"):
        measurements[model], captured[model] = {}, {}
        for label, settings in CASES.items():
            raw = render(binary, model, settings)
            samples = struct.unpack(f"={FRAMES}f", raw)
            assert all(math.isfinite(x) for x in samples) and any(samples), (model, label)
            assert raw == render(binary, model, settings), "fresh-process capture is not deterministic"
            assert raw == render(sanitized, model, settings), "sanitizers changed reference output"
            path = FOLDER / f"{model}-{label}.f32"
            path.write_bytes(struct.pack(f"<{FRAMES}f", *samples))
            measured = analysis.analyze(samples, RATE)
            peak = max(map(abs, samples))
            wav = FOLDER / f"{model}-{label}.wav"
            if peak <= 1:
                audio.write_wav(wav, samples, RATE)
            measurements[model][label] = dict(settings=dict(tone=settings[0], decay=settings[1],
                fm_amount=settings[2], retrigger_sample=7200 if settings[3] else None),
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(), raw=str(path),
                wav=str(wav) if peak <= 1 else None, analysis=measured)
            captured[model][label] = samples
        default = captured[model]["default"]
        assert captured[model]["retrigger"][:7200] == default[:7200]
        assert captured[model]["retrigger"][7200:] != default[7200:], "retrigger has no effect"
        assert captured[model]["retrigger"][7200:8192] != default[:992], "retrigger lost residual history"
        def tail_energy(samples):
            return sum(x*x for x in samples[4800:9600]) / sum(x*x for x in samples[:4800])
        short_tail = tail_energy(captured[model]["short"])
        long_tail = tail_energy(captured[model]["long"])
        assert long_tail > short_tail, "long Decay does not retain more tail energy"
        measurements[model]["decay_tail_energy"] = dict(short=short_tail, long=long_tail,
            early_window_samples=[0,4800], late_window_samples=[4800,9600])
        assert captured[model]["dark"] != captured[model]["bright"], "Tone is disconnected"
        assert captured[model]["no-fm"] != default, "FM is disconnected"
        changed_seed = render(binary, model, CASES["default"], SEED+1)
        assert (changed_seed == struct.pack(f"={FRAMES}f", *default)) == (model == "analog"), "noise seed check failed"
    # Descriptive differences only: these control positions/scales are not calibrated equivalents.
    prototypes = {
        "analog": coupling808.render_reference(tone808.filter_reference(body808.reference(FRAMES))),
        "synthetic": body909.reference(FRAMES),
    }
    differences = {}
    for model, prototype in prototypes.items():
        delta = [a-b for a,b in zip(captured[model]["default"],prototype)]
        differences[model] = dict(maximum_absolute_difference=max(map(abs,delta)),
                                 rms_difference=math.sqrt(sum(x*x for x in delta)/FRAMES),
                                 interpretation="descriptive; no equivalence/fidelity verdict")
    report = dict(status="passed", scope="host execution of original third-party classes; no ASM/native OS/VST proof",
        project_revision=cpu.revision(ROOT), project_dirty=bool(cpu.command(["git","status","--porcelain"],cwd=ROOT).strip()),
        prototype_source_sha256={str(Path(module.__file__).relative_to(ROOT)):
            hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
            for module in (body808,body909,tone808,coupling808)},
        source_archives=archives, compiler=cpu.command([*compiler,"--version"]).splitlines()[0],
        compiler_flags=flags, harness_sha256=hashlib.sha256(HARNESS.read_bytes()).hexdigest(),
        executable_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(), sample_rate=RATE,
        frames=FRAMES, block_size=BLOCK, seed=SEED, silent_priming_frames=BLOCK,
        initialization="static zero initialization, original Init(), one fresh process per capture",
        common_settings=dict(accent=.8, sustain=False, frequency_hz=dict(analog=55,synthetic=50),
            trigger_sample=0, analog_attack_and_self_fm="fm_amount",
            synthetic_dirtiness="0.4 - 0.25 * decay^2", synthetic_fm_decay=0),
        measurements=measurements, prototype_differences=differences,
        normalization=False, alignment_samples=0,
        checked=["archive/snapshot integrity", "finite unnormalized audio", "fresh-process repeatability",
                 "ASan/UBSan and identical sanitized samples", "Decay/Tone/FM response", "residual retrigger history",
                 "seed sensitivity only for the noisy synthetic class"],
        unqualified=["stock control mapping and output scale", "complete 808/909 circuit fidelity",
                     "full Plaits engine/overdrive/hardware behavior", "x0x ASM or native emulator comparison",
                     "VST or physical-device comparison", "bit-identical output across compilers/platforms"])
    (FOLDER / "report.json").write_text(json.dumps(report,indent=2)+"\n")
    return report


if __name__ == "__main__":
    try:
        result = run()
        print(json.dumps(dict(status=result["status"], scope=result["scope"], report=str(FOLDER/"report.json"))))
    except cpu.Unavailable as error:
        print(json.dumps(dict(status="unavailable", reason=str(error))))
        raise SystemExit(77)
