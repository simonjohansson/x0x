"""Assemble author-owned diagnostic kernels and run the required emulators.

These private entry points prove output writes and selected register preservation.
They do not qualify native firmware callbacks, EMAC behavior or device timing.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SELACHE_PIN = "2b26d3b75c53063575bc5c820fa0d38879335187"
FRAMES = 32
SAMPLE = 0.25


class Unavailable(RuntimeError):
    """A required tool or emulator is absent; not a passing test."""


def command(args: list[str | Path], cwd: Path | None = None) -> str:
    result = subprocess.run(list(map(str, args)), cwd=cwd, capture_output=True,
                            text=True, check=False)
    if result.returncode:
        raise RuntimeError(f"{args[0]} failed: {result.stdout}{result.stderr}")
    return result.stdout


def revision(path: Path) -> str:
    return command(["git", "rev-parse", "HEAD"], cwd=path).strip()


def require_program(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise Unavailable(f"{name} is unavailable; run the documented mise bootstrap")
    return path


def require_module(name: str, dependency: str):
    try:
        module = importlib.import_module(name)
    except ImportError as error:
        raise Unavailable(f"{dependency} runtime is unavailable: {error}") from error
    expected = (ROOT / "vendor" / dependency).resolve()
    actual = Path(module.__file__).resolve()
    if not actual.is_relative_to(expected):
        raise Unavailable(f"{name} must come from pinned vendor/{dependency}, got {actual}")
    return module


def provenance(backend: str, image: bytes, source: Path, emulator: str) -> dict:
    return {
        "backend": backend,
        "kind": "assembled-diagnostic",
        "emulator": emulator,
        "emulator_revision": revision(ROOT / "vendor" / emulator),
        "project_revision": revision(ROOT),
        "project_dirty": bool(command(["git", "status", "--porcelain",
                                        "--untracked-files=normal"], cwd=ROOT).strip()),
        "elekloader_revision": revision(ROOT / "vendor/elekloader"),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "image_sha256": hashlib.sha256(image).hexdigest(),
        "code_bytes": len(image),
        "sample_rate": 48000,
        "frames": FRAMES,
        "checked": ["output extent", "buffer guards", "selected preserved registers"],
        "unqualified": ["native callback ABI", "DSP arithmetic/context",
                        "voice lifecycle", "hardware instructions", "physical deadlines"],
    }


def build_coldfire(folder: Path, source: Path | None = None) -> tuple[bytes, Path]:
    source = source or ROOT / "targets/coldfire/diagnostic.s"
    prefix = os.environ.get("ELEKLOADER_CROSS", "m68k-elf-")
    assembler = require_program(prefix + "as")
    linker = require_program(prefix + "ld")
    objcopy = require_program(prefix + "objcopy")
    obj, executable, binary = [folder / name for name in ("diagnostic.o", "diagnostic.elf", "diagnostic.bin")]
    command([assembler, "-mcpu=54455", source, "-o", obj])
    command([linker, "-Ttext=0x40000400", "-e", "x0z_diagnostic", obj, "-o", executable])
    command([objcopy, "-O", "binary", executable, binary])
    return binary.read_bytes(), source


def run_coldfire(image: bytes, word: int) -> tuple[list[float], int]:
    harness = require_module("emu.harness", "digiemu")
    from unicorn import UC_HOOK_CODE, UcError
    from unicorn import m68k_const as regs

    base, output, stack, stop = 0x40000400, 0x40010004, 0x40020000, 0x40030000
    machine = harness.Machine()
    machine.ensure(0x40000000)
    machine.uc.mem_write(base, image)
    machine.uc.mem_write(output - 4, b"\xa5" * (4 * (FRAMES + 2)))
    saved = {getattr(regs, "UC_M68K_REG_" + name): 0x10203040 + index
             for index, name in enumerate([*(f"D{i}" for i in range(2, 8)),
                                           *(f"A{i}" for i in range(2, 7))])}
    for reg, value in saved.items():
        machine.uc.reg_write(reg, value)
    machine.uc.reg_write(regs.UC_M68K_REG_SR, 0x2700)
    machine.uc.mem_write(stack, struct.pack(">III", stop, output, word))
    machine.uc.reg_write(regs.UC_M68K_REG_A7, stack)
    count = [0]
    machine.uc.hook_add(UC_HOOK_CODE, lambda *_: count.__setitem__(0, count[0] + 1))
    try:
        machine.uc.emu_start(base, stop, count=1000)
    except UcError as error:
        raise RuntimeError(f"ColdFire instruction execution failed: {error}") from error
    if machine.uc.reg_read(regs.UC_M68K_REG_PC) != stop:
        raise AssertionError("ColdFire diagnostic did not return within its instruction bound")
    if machine.uc.reg_read(regs.UC_M68K_REG_A7) != stack + 4:
        raise AssertionError("ColdFire diagnostic did not preserve its caller's stack")
    if any(machine.uc.reg_read(reg) != value for reg, value in saved.items()):
        raise AssertionError("ColdFire diagnostic corrupted a preserved register")
    result = bytes(machine.uc.mem_read(output - 4, 4 * (FRAMES + 2)))
    if result[:4] != b"\xa5" * 4 or result[-4:] != b"\xa5" * 4:
        raise AssertionError("ColdFire diagnostic overwrote a buffer guard")
    return [x / 2**31 for x in struct.unpack(">32i", result[4:-4])], count[0]


def build_sharc(folder: Path, source: Path | None = None) -> tuple[bytes, int, Path, Path]:
    source = source or ROOT / "targets/sharc/diagnostic.s"
    configured = os.environ.get("SELACHE", str(ROOT / "vendor/digikit/out/tools/selache"))
    selache = Path(configured).expanduser().resolve()
    if not selache.is_dir():
        raise Unavailable(f"Selache checkout is missing: {selache}")
    if revision(selache) != SELACHE_PIN:
        raise RuntimeError(f"Selache must be pinned to {SELACHE_PIN}")
    tools = selache / "target/release"
    if not all((tools / name).is_file() for name in ("selas", "seld")):
        raise Unavailable("Pinned Selache assembler/linker binaries are missing")
    obj, executable = folder / "diagnostic.doj", folder / "diagnostic.dxe"
    command([tools / "selas", "-proc", "ADSP-21569", "-o", obj, source])
    command([tools / "seld", "-proc", "ADSP-21569", "-T",
             ROOT / "targets/sharc/diagnostic.ldf", "-entry", "x0z_diagnostic.",
             "-o", executable, obj])
    raw = executable.read_bytes()
    code, entry = sharc_code(raw)
    return code, entry, source, selache


def sharc_code(raw: bytes) -> tuple[bytes, int]:
    """Read the one allocated section of our own tiny linked ELF32 executable."""
    if len(raw) < 52 or raw[:7] != b"\x7fELF\x01\x01\x01":
        raise ValueError("expected a little-endian ELF32 SHARC executable")
    header = struct.unpack_from("<16sHHIIIIIHHHHHH", raw)
    _, kind, machine, _, entry, _, shoff, _, _, _, _, shsize, shnum, _ = header
    if kind != 2 or machine != 0x85 or shsize != 40 or shoff + shsize * shnum > len(raw):
        raise ValueError("invalid SHARC executable/header extent")
    allocated = []
    for index in range(shnum):
        _, kind, flags, address, offset, size, _, _, _, _ = struct.unpack_from("<10I", raw, shoff + index * shsize)
        if flags & 2:
            if kind != 1 or flags != 7 or offset + size > len(raw) or size % 2:
                raise ValueError("unexpected allocated SHARC section")
            allocated.append((address, raw[offset:offset + size]))
    if len(allocated) != 1 or allocated[0][0] != entry or not allocated[0][1]:
        raise ValueError("diagnostic must have one code section beginning at entry")
    code = allocated[0][1]
    # Selache stores big-endian parcels; ADI loader streams store each parcel little-endian.
    return b"".join(code[i:i + 2][::-1] for i in range(0, len(code), 2)), entry


def run_sharc(code: bytes, entry: int, word: int) -> tuple[list[float], int]:
    runner_module = require_module("tools.sharc_dev.sharc_run", "digikit")
    from tools.sharc_dev import sharcldr, sharc_trace as trace

    header = bytearray(struct.pack("<IIII", 0xAD000000, sharcldr.sw_to_byte(entry), len(code), 0))
    checksum = 0
    for byte in header:
        checksum ^= byte
    header[2] = checksum
    memory = sharcldr.LoadedMemory.from_stream(bytes(header) + code)
    output = 0x20092004
    seed = {f"R{i}": 0x10203040 + i for i in range(16)}
    seed.update(R4=output, R8=word)
    pokes = {output + i * 4: 0xA5A5A5A5 for i in range(-1, FRAMES + 1)}
    runner = runner_module.Runner(memory, entry, regs=seed, pokes=pokes)
    result = runner.run(max_steps=1000)
    if result.halt.reason != "return without followed call":
        raise AssertionError(f"SHARC diagnostic failed: {result.halt}")
    for name, value in seed.items():
        if name not in {"R0", "R1", "R2"}:
            if runner.state.uregs[trace.UREG_CODES[name]] != trace.Const(value):
                raise AssertionError(f"SHARC diagnostic corrupted {name}")
    words = [trace._dm_read(runner.state, trace.Const(output + i * 4), 4)
             for i in range(-1, FRAMES + 1)]
    if words[0] != trace.Const(0xA5A5A5A5) or words[-1] != trace.Const(0xA5A5A5A5):
        raise AssertionError("SHARC diagnostic overwrote a buffer guard")
    if not all(isinstance(word, trace.Const) for word in words):
        raise AssertionError("SHARC diagnostic left unknown output")
    return [struct.unpack("<f", struct.pack("<I", x.value))[0] for x in words[1:-1]], result.instructions


def diagnose(backend: str) -> dict:
    with tempfile.TemporaryDirectory(prefix=f"x0z-{backend}-") as temp:
        folder = Path(temp)
        if backend == "coldfire":
            image, source = build_coldfire(folder)
            execute = lambda word: run_coldfire(image, word)
            words = [(0, 0.0), (0x20000000, SAMPLE), (0xE0000000, -SAMPLE)]
            result = provenance(backend, image, source, "digiemu")
            result["numeric_format"] = "Q1.31"
            prefix = os.environ.get("ELEKLOADER_CROSS", "m68k-elf-")
            result["assembler"] = command([require_program(prefix + "as"), "--version"]).splitlines()[0]
            result["linker"] = command([require_program(prefix + "ld"), "--version"]).splitlines()[0]
        elif backend == "sharc":
            image, entry, source, selache = build_sharc(folder)
            execute = lambda word: run_sharc(image, entry, word)
            words = [(0, 0.0), (0x3E800000, SAMPLE), (0xBE800000, -SAMPLE)]
            result = provenance(backend, image, source, "digikit")
            result["numeric_format"] = "float32"
            result["assembler_revision"] = revision(selache)
            result["assembler"] = {"name": "Selache selas", "revision": revision(selache),
                                   "sha256": hashlib.sha256((selache / "target/release/selas").read_bytes()).hexdigest()}
            result["linker"] = {"name": "Selache seld", "revision": revision(selache),
                                "sha256": hashlib.sha256((selache / "target/release/seld").read_bytes()).hexdigest()}
        else:
            raise ValueError(f"unknown backend: {backend}")
        cases = []
        for word, expected in words:
            samples, instructions = execute(word)
            check_output(samples, expected)
            cases.append({"sample_word": word, "samples": samples, "instructions": instructions})
        result["cases"] = cases
        result["rejected_mutations"] = reject_mutations(backend, source, folder)
        return result


def check_output(samples: list[float], expected: float) -> None:
    if samples != [expected] * FRAMES:
        raise AssertionError("diagnostic did not write the expected 32 samples")


def reject_mutations(backend: str, source: Path, folder: Path) -> list[dict]:
    """Require actual reassembled defective programs to fail the same runner checks."""
    if backend == "coldfire":
        changes = [("skipped-output", "moveq #31", "moveq #30"),
                   ("buffer-overrun", "moveq #31", "moveq #32"),
                   ("preserved-register", "    rts", "    moveq #0, %d2\n    rts")]
    else:
        changes = [("skipped-output", "R1=32;", "R1=31;"),
                   ("buffer-overrun", "R1=32;", "R1=33;"),
                   ("preserved-register", "    RTS;", "    R3=0;\n    RTS;")]
    original = source.read_text()
    rejected = []
    for name, old, new in changes:
        if original.count(old) != 1:
            raise ValueError(f"mutation marker is not unique: {name}")
        work = folder / name
        work.mkdir()
        altered = work / "diagnostic.s"
        altered.write_text(original.replace(old, new))
        if backend == "coldfire":
            image, _ = build_coldfire(work, altered)
            execute = lambda: run_coldfire(image, 0x20000000)
        else:
            image, entry, _, _ = build_sharc(work, altered)
            execute = lambda: run_sharc(image, entry, 0x3E800000)
        try:
            samples, _ = execute()
            check_output(samples, SAMPLE)
        except AssertionError as error:
            rejected.append({"name": name, "reason": str(error),
                             "image_sha256": hashlib.sha256(image).hexdigest()})
        else:
            raise AssertionError(f"runner accepted the defective {name} program")
    return rejected


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backend", choices=("coldfire", "sharc"))
    args = parser.parse_args(argv)
    try:
        result = diagnose(args.backend)
    except Unavailable as error:
        print(json.dumps({"status": "unavailable", "reason": str(error)}))
        return 77
    except (AssertionError, OSError, RuntimeError, ValueError) as error:
        print(json.dumps({"status": "failed", "reason": str(error)}))
        return 1
    print(json.dumps({"status": "passed", **result}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
