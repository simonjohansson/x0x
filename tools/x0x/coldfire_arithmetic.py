"""Bounded, assembled ColdFire fixed-point probe; no firmware or sound model.

Arithmetic follows MCF54418RM sections 5.2.1, 5.3.1 and 5.3.5:
https://www.nxp.com/docs/en/reference-manual/MCF54418RM.pdf
The 64-bit fractional product is narrowed to 40 bits before adding to the
48-bit accumulator; extraction narrows another 8 bits to Q1.31. Both steps
use truncation or nearest-even rounding, with saturated 32-bit output.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile

from . import cpu
from .fixtures import load_json, make_result, validate_fixture, write_json
from .oracle import render_diagnostic

MINIMUM, MAXIMUM = -(1 << 31), (1 << 31) - 1
HALF = 1 << 30
TRUNCATE, NEAREST = 0xA0, 0xB0
SOURCE = cpu.ROOT / "targets/coldfire/arithmetic.s"
EMAC_SEED = (0x12345678, 0x89ABCDEF, 0x13579BDF, 0x2468ACE0,
             0x11223344, 0x55667788, 0xFFFFABCE, 0x0CB1)


def rounded_shift(value: int, bits: int, nearest: bool) -> int:
    """Exact integer division, optionally rounded to the nearest even integer."""
    whole, remainder = divmod(value, 1 << bits)
    half = 1 << (bits - 1)
    return whole + int(nearest and (remainder > half or (remainder == half and whole & 1)))


def reference_step(state: int, excitation: int, coefficient: int, level: int,
                   mode: int = NEAREST) -> tuple[int, int]:
    if type(mode) is not int or mode not in (TRUNCATE, NEAREST):
        raise ValueError("probe supports saturated Q1.31 truncation or nearest-even only")
    if any(type(x) is not int or not MINIMUM <= x <= MAXIMUM
           for x in (state, excitation, coefficient, level)):
        raise ValueError("probe values must be signed Q1.31 words")
    nearest = mode == NEAREST
    product = rounded_shift(2 * state * coefficient, 24, nearest)
    state = max(MINIMUM, min(MAXIMUM, rounded_shift((excitation << 8) + product, 8, nearest)))
    product = rounded_shift(2 * state * level, 24, nearest)
    output = max(MINIMUM, min(MAXIMUM, rounded_shift(product, 8, nearest)))
    return state, output


def q31(value: float) -> int:
    if not 0 <= value <= 1:
        raise ValueError("normalized input must be in 0..1")
    return min(MAXIMUM, round(value * (1 << 31)))


class Runner:
    """Keep independently owned state for sixteen diagnostic voices."""
    BASE, OUTPUT, STATES = 0x40000400, 0x40010004, 0x40011004
    INPUT, SNAPSHOT, STACK, STOP = 0x40012004, 0x40018004, 0x40020000, 0x40030000

    def __init__(self, image: bytes):
        harness = cpu.require_module("emu.harness", "digiemu")
        from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
        from unicorn import m68k_const as registers

        self.registers = registers
        self.machine = harness.Machine()
        self.uc = self.machine.uc
        self.machine.ensure(0x40000000)
        self.uc.mem_write(self.BASE, image)
        self.uc.mem_write(self.STATES - 4, b"\xa5" * 264)
        for voice in range(16):
            self.set_state(voice, 0)
        self.steps = 0
        self.invalid_writes = []
        self.allowed_writes = []
        self.uc.hook_add(UC_HOOK_CODE, self._step)
        self.uc.hook_add(UC_HOOK_MEM_WRITE, self._write)

    def _step(self, uc, *_):
        self.steps += 1
        if self.invalid_writes:
            uc.emu_stop()

    def _write(self, _uc, _access, address, size, _value, _data):
        if not any(first <= address and address + size <= last for first, last in self.allowed_writes):
            self.invalid_writes.append((address, size))

    def register(self, name):
        return getattr(self.registers, "UC_M68K_REG_" + name)

    def address(self, voice):
        if type(voice) is not int or not 0 <= voice < 16:
            raise ValueError("diagnostic voice index must be in 0..15")
        return self.STATES + 16 * voice

    def set_state(self, voice, value):
        if type(value) is not int or not MINIMUM <= value <= MAXIMUM:
            raise ValueError("state must be a signed Q1.31 word")
        self.uc.mem_write(self.address(voice), struct.pack(">i", value))

    def state(self, voice):
        return struct.unpack(">i", self.uc.mem_read(self.address(voice), 4))[0]

    def render(self, voice, inputs, coefficient=HALF, level=HALF, mode=NEAREST):
        from unicorn import UcError

        if not isinstance(inputs, list) or not 1 <= len(inputs) <= 32:
            raise ValueError("probe call needs 1..32 excitation words")
        reference_step(0, 0, coefficient, level, mode)
        if any(type(x) is not int or not MINIMUM <= x <= MAXIMUM for x in inputs):
            raise ValueError("excitation must contain signed Q1.31 words")
        state_address = self.address(voice)
        before = bytes(self.uc.mem_read(self.STATES - 4, 264))
        guards = b"\xa5" * (4 * (len(inputs) + 2))
        self.uc.mem_write(self.OUTPUT - 4, guards)
        encoded = struct.pack(">" + "i" * len(inputs), *inputs)
        self.uc.mem_write(self.INPUT - 4, b"\xa5" * 4 + encoded + b"\xa5" * 4)
        self.uc.mem_write(self.SNAPSHOT - 4, b"\xa5" * 40)
        self.uc.mem_write(self.STACK - 128, b"\xa5" * 172)
        words = (self.STOP, state_address, self.OUTPUT, self.INPUT,
                 coefficient & 0xFFFFFFFF, level & 0xFFFFFFFF, len(inputs), mode, self.SNAPSHOT)
        arguments = struct.pack(">9I", *words)
        self.uc.mem_write(self.STACK, arguments)
        self.uc.reg_write(self.register("SR"), 0x2700)
        saved = {self.register(name): 0x10203040 + index for index, name in enumerate(
            [*(f"D{i}" for i in range(2, 8)), *(f"A{i}" for i in range(2, 7))])}
        for register, value in saved.items():
            self.uc.reg_write(register, value)
        self.uc.reg_write(self.register("A7"), self.STACK)
        self.steps = 0
        self.invalid_writes = []
        self.allowed_writes = [(state_address, state_address + 4),
                               (self.OUTPUT, self.OUTPUT + 4 * len(inputs)),
                               (self.STACK - 108, self.STACK),
                               (self.SNAPSHOT, self.SNAPSHOT + 32)]
        try:
            self.uc.emu_start(self.BASE, self.STOP, count=10000)
        except UcError as error:
            raise RuntimeError(f"ColdFire arithmetic execution failed: {error}") from error
        if self.invalid_writes:
            raise AssertionError(f"arithmetic probe wrote unowned memory: {self.invalid_writes}")
        if self.uc.reg_read(self.register("PC")) != self.STOP:
            raise AssertionError("arithmetic probe did not return within 10000 instructions")
        if self.uc.reg_read(self.register("A7")) != self.STACK + 4:
            raise AssertionError("arithmetic probe corrupted the caller stack pointer")
        if any(self.uc.reg_read(reg) != value for reg, value in saved.items()):
            raise AssertionError("arithmetic probe corrupted a callee-preserved register")
        if bytes(self.uc.mem_read(self.STACK, len(arguments))) != arguments:
            raise AssertionError("arithmetic probe corrupted caller arguments")
        if (bytes(self.uc.mem_read(self.STACK - 128, 16)) != b"\xa5" * 16
                or bytes(self.uc.mem_read(self.STACK + 36, 8)) != b"\xa5" * 8):
            raise AssertionError("arithmetic probe overwrote a stack guard")
        snapshot = bytes(self.uc.mem_read(self.SNAPSHOT - 4, 40))
        if snapshot[:4] != b"\xa5" * 4 or snapshot[-4:] != b"\xa5" * 4:
            raise AssertionError("arithmetic wrapper overwrote its context buffer")
        if struct.unpack(">8I", snapshot[4:-4]) != EMAC_SEED:
            raise AssertionError("arithmetic probe failed to preserve complete EMAC context")
        after = bytes(self.uc.mem_read(self.STATES - 4, 264))
        at = state_address - (self.STATES - 4)
        if before[:at] != after[:at] or before[at + 4:] != after[at + 4:]:
            raise AssertionError("arithmetic probe changed unowned voice state or a state guard")
        if bytes(self.uc.mem_read(self.INPUT - 4, len(encoded) + 8)) != b"\xa5" * 4 + encoded + b"\xa5" * 4:
            raise AssertionError("arithmetic probe changed read-only inputs")
        output = bytes(self.uc.mem_read(self.OUTPUT - 4, len(guards)))
        if output[:4] != b"\xa5" * 4 or output[-4:] != b"\xa5" * 4:
            raise AssertionError("arithmetic probe overwrote an output guard")
        values = list(struct.unpack(">" + "i" * len(inputs), output[4:-4]))
        return values, self.state(voice), self.steps


CASES = (
    ("silence", 0, 0, HALF, HALF, NEAREST, 0),
    ("positive product", HALF, 0, HALF, HALF, NEAREST, 1 << 29),
    ("negative product", -HALF, 0, HALF, HALF, NEAREST, -(1 << 29)),
    ("two negatives", -HALF, 0, -HALF, HALF, NEAREST, 1 << 29),
    ("minus-one squared saturates", MINIMUM, 0, MINIMUM, HALF, NEAREST, MAXIMUM),
    ("positive sum saturates", MAXIMUM, MAXIMUM, MAXIMUM, HALF, NEAREST, MAXIMUM),
    ("negative sum saturates", MINIMUM, MINIMUM, MAXIMUM, HALF, NEAREST, MINIMUM),
    ("small product truncates", 1, 0, 0x7FE00000, HALF, TRUNCATE, 0),
    ("small product rounds", 1, 0, 0x7FE00000, HALF, NEAREST, 1),
    ("40-bit even tie", 1, 0, 0x40400000, HALF, NEAREST, 0),
    ("40-bit odd tie", 1, 0, 0x40C00000, HALF, NEAREST, 1),
    ("positive even tie", 1, 0, HALF, HALF, NEAREST, 0),
    ("positive odd tie", 3, 0, HALF, HALF, NEAREST, 2),
    ("negative even tie", -1, 0, HALF, HALF, NEAREST, 0),
    ("negative odd tie", -3, 0, HALF, HALF, NEAREST, -2),
    ("negative truncation tail", -1, 0, HALF, HALF, TRUNCATE, -1),
)


def check_cases(image):
    runner = Runner(image)
    reports = []
    for name, initial, excitation, coefficient, level, mode, expected_state in CASES:
        expected = reference_step(initial, excitation, coefficient, level, mode)
        if expected[0] != expected_state:
            raise AssertionError("independent arithmetic vector disagrees with its explicit expectation")
        runner.set_state(0, initial)
        output, state, steps = runner.render(0, [excitation], coefficient, level, mode)
        if (state, output[0]) != expected:
            raise AssertionError(f"{name}: actual arithmetic {(state, output[0])} != {expected}")
        reports.append(dict(name=name, mode=mode, state=state, output=output[0], instructions=steps))
    return reports


def render_fixture(image, fixture):
    validate_fixture(fixture)
    if fixture["model"] != "diagnostic-pole-v1" or set(fixture["settings"]) != {"level"}:
        raise ValueError("arithmetic fixture runner only supports diagnostic-pole-v1 with Level")
    runner = Runner(image)
    voices = {name: index for index, name in enumerate(fixture["voices"])}
    level = dict.fromkeys(voices, fixture["settings"]["level"])
    samples = {name: [] for name in voices}
    boundaries = sorted({0, fixture["frames"], *range(0, fixture["frames"], 32),
                         *(event["sample"] for event in fixture["events"])})
    events = iter(fixture["events"])
    event = next(events, None)
    total_steps = 0
    for start, end in zip(boundaries, boundaries[1:]):
        excitation = dict.fromkeys(voices, 0)
        while event is not None and event["sample"] == start:
            name, kind = event["voice"], event["kind"]
            if kind in {"reset", "reassign"}:
                runner.set_state(voices[name], 0)
                excitation[name] = 0
            elif kind == "parameter":
                if event["parameter"] != "level":
                    raise ValueError("arithmetic probe only consumes Level")
                level[name] = event["value"]
            else:
                if kind == "trigger" and (runner.state(voices[name]) != 0 or excitation[name]):
                    raise ValueError("fresh trigger requires quiescent diagnostic state")
                excitation[name] += q31(event["strength"])
                if excitation[name] > MAXIMUM:
                    raise ValueError("diagnostic fixture excitation exceeds Q1.31 headroom")
            event = next(events, None)
        for name, index in voices.items():
            values, _, steps = runner.render(index, [excitation[name]] + [0] * (end - start - 1), level=q31(level[name]))
            samples[name].extend(value / (1 << 31) for value in values)
            total_steps += steps
    result = make_result(fixture, "coldfire", samples,
                         dict(source_revision=cpu.revision(cpu.ROOT), toolchain="GNU m68k-elf ASM + pinned digiemu",
                              source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                              image_sha256=hashlib.sha256(image).hexdigest(),
                              emulator_revision=cpu.revision(cpu.ROOT / "vendor/digiemu")))
    oracle = render_diagnostic(fixture)
    maximum_error = max(abs(a - b) for name in voices
                        for a, b in zip(samples[name], oracle["samples"][name]))
    if maximum_error > 2 / (1 << 31):
        raise AssertionError(f"fixed-point fixture error {maximum_error} exceeds two Q1.31 LSBs")
    return result, maximum_error, total_steps


def check_interleaving(image):
    baseline, interleaved = Runner(image), Runner(image)
    steps = 0
    for block in range(3):
        for voice in range(1, 16):
            _, _, count = interleaved.render(voice, [voice << 24], coefficient=0x60000000)
            steps += count
        inputs = [HALF if block == 0 else 0] + [0] * 7
        expected = baseline.render(0, inputs, coefficient=0x60000000)
        actual = interleaved.render(0, inputs, coefficient=0x60000000)
        if actual[:2] != expected[:2]:
            raise AssertionError("unrelated voice callbacks changed the diagnostic voice")
        steps += actual[2] + expected[2]
    return dict(voices=16, blocks=3, instructions=steps,
                checked="persistent state and output invariant under 15 unrelated voices")


def check_semantics(image, fixture, baseline):
    reports = []
    reversed_voices = copy.deepcopy(fixture)
    reversed_voices["voices"].reverse()
    result, error, steps = render_fixture(image, reversed_voices)
    if result["samples"] != baseline["samples"]:
        raise AssertionError("render-lane ordering changed logical voice output")
    reports.append(dict(name="reversed-voice-order", maximum_error_fs=error, instructions=steps))
    for name, events, audible in [
        ("trigger-then-reset", [dict(sample=0, voice="A", kind="trigger", strength=.5),
                                dict(sample=0, voice="A", kind="reset")], False),
        ("reassignment", [dict(sample=0, voice="A", kind="trigger", strength=.5),
                          dict(sample=1, voice="A", kind="reassign", identity="new-owner"),
                          dict(sample=1, voice="A", kind="trigger", strength=.25)], True),
        ("muted-state-keeps-running", [dict(sample=0, voice="A", kind="parameter", parameter="level", value=0),
                                      dict(sample=0, voice="A", kind="trigger", strength=.5),
                                      dict(sample=1, voice="A", kind="parameter", parameter="level", value=.5)], True),
    ]:
        variant = copy.deepcopy(fixture)
        variant["frames"] = max(2, variant["frames"])
        variant["voices"] = ["A"]
        variant["expected_audible"] = {"A": audible}
        variant["events"] = events
        _, error, steps = render_fixture(image, variant)
        reports.append(dict(name=name, maximum_error_fs=error, instructions=steps))
    return reports


def reject_mutations(folder):
    source = SOURCE.read_text()
    changes = (
        ("arithmetic-sign", "    mac.l %d5, %d3, %acc0", "    msac.l %d5, %d3, %acc0"),
        ("skipped-output", "    move.l %d0, (%a1)+", "    addq.l #4, %a1"),
        ("state-overrun", "    move.l %d5, (%a0)", "    move.l %d5, 4(%a0)"),
        ("unowned-write", "    move.l %d5, (%a0)", "    move.l %d5, (%a0)\n    move.l %d0, 0x40014000"),
        ("callee-register", "    movem.l (%sp), %d2-%d7/%a2-%a6", "    nop"),
        ("macsr-context", "    move.l %d0, %macsr /* restore MACSR */", "    moveq #0, %d0\n    move.l %d0, %macsr"),
        ("accumulator-extension", "    move.l 60(%sp), %d0\n    move.l %d0, %accext01", "    nop\n    nop"),
        ("rounding-save", "    move.l %d0, 72(%sp)\n    moveq #0, %d0\n    move.l %d0, %macsr", "    move.l %d0, 72(%sp)\n    nop\n    nop"),
    )
    reports = []
    for name, before, after in changes:
        if source.count(before) != 1:
            raise ValueError(f"mutation marker is not unique: {name}")
        directory = folder / name
        directory.mkdir()
        altered = directory / "arithmetic.s"
        altered.write_text(source.replace(before, after))
        image, _ = cpu.build_coldfire(directory, altered)
        try:
            check_cases(image)
        except AssertionError as error:
            reports.append(dict(name=name, reason=str(error)))
        else:
            raise AssertionError(f"arithmetic harness accepted defective {name}")
    return reports


def diagnose(fixture_path=None):
    fixture_path = fixture_path or cpu.ROOT / "tests/fixtures/diagnostic.json"
    fixture = validate_fixture(load_json(fixture_path))
    with tempfile.TemporaryDirectory(prefix="x0x-coldfire-arithmetic-") as temp:
        folder = Path(temp)
        image, _ = cpu.build_coldfire(folder, SOURCE)
        cases = check_cases(image)
        interleaving = check_interleaving(image)
        result, error, instructions = render_fixture(image, fixture)
        semantics = check_semantics(image, fixture, result)
        mutations = reject_mutations(folder)
        report = cpu.provenance("coldfire", image, SOURCE, "digiemu")
        report.update(numeric_format="Q1.31 state/output; 40-bit fractional product; 48-bit EMAC accumulator",
                      modes={"truncate_saturate": TRUNCATE, "nearest_even_saturate": NEAREST},
                      checked=["independent arithmetic vectors", "full EMAC context", "callee registers/stack",
                               "owned state/input/output guards", "shared multi-voice event fixture", "reassembled defective programs"],
                      unqualified=["complete EMAC instruction set", "native callback ABI/allocator",
                                   "hardware instructions", "physical deadlines", "kick fidelity"],
                      arithmetic_cases=cases, rejected_mutations=mutations,
                      interleaving=interleaving, semantic_cases=semantics,
                      semantic_result=result, maximum_oracle_error_fs=error,
                      fixture_instruction_count=instructions, instruction_bound_per_call=10000,
                      stack_frame_bytes=76, wrapper_and_nested_stack_extent_bytes=108)
        prefix = os.environ.get("ELEKLOADER_CROSS", "m68k-elf-")
        for tool in ("assembler", "linker"):
            program = prefix + ("as" if tool == "assembler" else "ld")
            report[tool] = cpu.command([cpu.require_program(program), "--version"]).splitlines()[0]
        return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--result-out", type=Path)
    args = parser.parse_args(argv)
    try:
        report = diagnose(args.fixture)
        if args.result_out:
            write_json(args.result_out, report["semantic_result"])
    except cpu.Unavailable as error:
        print(json.dumps(dict(status="unavailable", reason=str(error))))
        return 77
    except (AssertionError, OSError, RuntimeError, ValueError) as error:
        print(json.dumps(dict(status="failed", reason=str(error))))
        return 1
    print(json.dumps(dict(status="passed", **report), allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
