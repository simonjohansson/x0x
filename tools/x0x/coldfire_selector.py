"""Actual ColdFire selector instructions with a host policy oracle; no native UI."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile

from . import cpu
from .coldfire_arithmetic import EMAC_SEED, Runner as ArithmeticRunner

SOURCE = cpu.ROOT / "targets/coldfire/selector.s"
INVALID, APPLY, MISSING, STALE, WAIT = range(5)
FRESH = 1


def reference_step(bank, lane, raw, trigger, delivery):
    """Caller-classified delivery validity; no inference from native timestamps."""
    if len(bank) != 8 or any(len(state) != 3 for state in bank):
        raise ValueError("selector bank needs eight {initialized,model,tail} lanes")
    if any(type(value) is not int or not 0 <= value <= 0xffffffff
           for state in bank for value in state):
        raise ValueError("selector bank values must be uint32 words")
    if any(type(value) is not int for value in (lane, raw, trigger, delivery)):
        raise ValueError("private selector inputs must be integer words")
    if any(not -(1 << 31) <= value <= 0xffffffff for value in (lane, raw, trigger, delivery)):
        raise ValueError("selector input must fit one guest word")
    unchanged = list(bank)
    if delivery == 0:
        return MISSING, unchanged, None
    if delivery == 2:
        return STALE, unchanged, None
    if delivery != FRESH or not 0 <= lane < 8 or not 0 <= raw <= 32512 or trigger not in (0, 1):
        return INVALID, unchanged, None
    initialized, model, tail = bank[lane]
    if initialized not in (0, 1) or initialized and model not in (0, 1):
        return INVALID, unchanged, None
    if not initialized and not trigger:
        return WAIT, unchanged, None
    selected = int(raw >= 16384) if trigger else model
    initialize = int(not initialized)
    changed = int(bool(initialized and selected != model))
    clear = int(bool(initialize or changed))
    unchanged[lane] = (1, selected, 0 if clear else tail)
    return APPLY, unchanged, (selected, initialize, changed, clear)


class Runner(ArithmeticRunner):
    """Reuse the existing pinned native-JIT hooks and context register helpers."""
    def __init__(self, image):
        super().__init__(image)
        self.uc.mem_write(self.STATES - 4, b"\xa5" * 4 + bytes(96) + b"\xa5" * 4)
        self.writes = []

    def _write(self, uc, access, address, size, value, data):
        self.writes.append((address, size))
        super()._write(uc, access, address, size, value, data)

    def bank(self):
        words = struct.unpack(">24I", self.uc.mem_read(self.STATES, 96))
        return [tuple(words[index:index + 3]) for index in range(0, 24, 3)]

    def set_lane(self, lane, initialized, model, tail):
        if type(lane) is not int or not 0 <= lane < 8:
            raise ValueError("lane must be 0..7")
        self.uc.mem_write(self.STATES + 12 * lane, struct.pack(">3I", initialized, model, tail))

    def call(self, lane, raw, trigger, delivery=FRESH, null=None):
        from unicorn import UcError

        expected_status, expected_bank, expected_notice = reference_step(self.bank(), lane, raw, trigger, delivery)
        if null is not None:
            if null not in {"bank", "notice", "input"}:
                raise ValueError("unknown null pointer case")
            expected_status, expected_bank, expected_notice = INVALID, self.bank(), None
        words = (lane, raw, trigger, delivery)
        encoded = struct.pack(">4I", *(value & 0xffffffff for value in words))
        self.uc.mem_write(self.INPUT - 4, b"\xa5" * 4 + encoded + b"\xa5" * 4)
        self.uc.mem_write(self.OUTPUT - 4, b"\xa5" * 24)
        self.uc.mem_write(self.SNAPSHOT - 4, b"\xa5" * 44)
        self.uc.mem_write(self.STACK - 48, b"\xa5" * 76)
        arguments = struct.pack(">5I", self.STOP, 0 if null == "bank" else self.STATES,
                                0 if null == "notice" else self.OUTPUT,
                                0 if null == "input" else self.INPUT, self.SNAPSHOT)
        self.uc.mem_write(self.STACK, arguments)
        self.uc.reg_write(self.register("SR"), 0x2700)
        names = [*(f"D{i}" for i in range(2, 8)), *(f"A{i}" for i in range(2, 7))]
        saved = {self.register(name): 0x10203040 + index for index, name in enumerate(names)}
        for register, value in saved.items():
            self.uc.reg_write(register, value)
        self.uc.reg_write(self.register("A7"), self.STACK)
        self.steps, self.invalid_writes, self.writes = 0, [], []
        self.allowed_writes = [(self.STACK - 32, self.STACK), (self.SNAPSHOT, self.SNAPSHOT + 36)]
        if expected_status == APPLY:
            self.allowed_writes += [(self.STATES + lane * 12, self.STATES + (lane + 1) * 12),
                                    (self.OUTPUT, self.OUTPUT + 16)]
        try:
            self.uc.emu_start(self.BASE, self.STOP, timeout=10_000_000)
        except UcError as error:
            raise AssertionError(f"selector execution failed: {error}") from error
        if self.invalid_writes:
            raise AssertionError(f"selector wrote unowned memory: {self.invalid_writes}")
        if self.uc.reg_read(self.register("PC")) != self.STOP:
            raise AssertionError("selector did not return before the test watchdog")
        if self.uc.reg_read(self.register("A7")) != self.STACK + 4:
            raise AssertionError("selector corrupted caller stack pointer")
        if any(self.uc.reg_read(register) != value for register, value in saved.items()):
            raise AssertionError("selector corrupted callee register")
        if bytes(self.uc.mem_read(self.STACK, 20)) != arguments:
            raise AssertionError("selector changed caller arguments")
        guards = [(self.STATES - 4, 4), (self.STATES + 96, 4),
                  (self.STACK - 48, 16), (self.STACK + 20, 8),
                  (self.OUTPUT - 4, 4), (self.OUTPUT + 16, 4),
                  (self.SNAPSHOT - 4, 4), (self.SNAPSHOT + 36, 4)]
        if any(bytes(self.uc.mem_read(address, size)) != b"\xa5" * size for address, size in guards):
            raise AssertionError("selector changed a state/output/context/stack guard")
        if bytes(self.uc.mem_read(self.INPUT - 4, 24)) != b"\xa5" * 4 + encoded + b"\xa5" * 4:
            raise AssertionError("selector changed read-only delivered input")
        snapshot = struct.unpack(">9I", self.uc.mem_read(self.SNAPSHOT, 36))
        if snapshot[:8] != EMAC_SEED:
            raise AssertionError("selector corrupted complete EMAC context")
        if snapshot[8] != expected_status or self.bank() != expected_bank:
            raise AssertionError(f"selector status/state differs from policy: {snapshot[8]}, {self.bank()}")
        output = bytes(self.uc.mem_read(self.OUTPUT, 16))
        if expected_notice is None:
            if output != b"\xa5" * 16:
                raise AssertionError("selector emitted a notice without a valid initialized delivery")
        elif struct.unpack(">4I", output) != expected_notice:
            raise AssertionError("selector notice differs from policy")
        return dict(lane=lane, raw=raw, trigger=trigger, delivery=delivery,
                    status=snapshot[8], notice=expected_notice, null=null,
                    state=expected_bank[lane] if 0 <= lane < 8 else None,
                    instructions=self.steps, writes=len(self.writes))


def check_cases(image):
    runner, records = Runner(image), []
    for lane in range(8):
        runner.set_lane(lane, 0, 99, 0x1000 + lane)
        records.append(runner.call(lane, 32512, 0))
        records.append(runner.call(lane, 16383 if lane % 2 == 0 else 16384, 1))
        runner.set_lane(lane, 1, lane % 2, 0x2000 + lane)
    for lane in reversed(range(8)):
        records.append(runner.call(lane, 32512 if lane % 2 == 0 else 0, 0))
        records.append(runner.call(lane, 1 if lane % 2 == 0 else 32512, 1))
        records.append(runner.call(lane, 16384 if lane % 2 == 0 else 16383, 1))
        runner.set_lane(lane, 1, 1 - lane % 2, 0x3000 + lane)
        records.append(runner.call(lane, 16384 if lane % 2 == 0 else 16383, 1))
    for lane in range(8):
        for raw in (0, 1, 128, 16383, 16384, 32512):
            records.append(runner.call(lane, raw, 1))
        for raw, trigger, delivery in [(32513, 1, 1), (-1, 1, 1), (1, 2, 1),
                                       (1, -1, 1), (1, 1, 0), (1, 1, 2), (1, 1, 3)]:
            records.append(runner.call(lane, raw, trigger, delivery))
    for lane in (-1, 8, 0xffffffff):
        records.append(runner.call(lane, 0, 1))
    for kind in ("bank", "notice", "input"):
        records.append(runner.call(0, 32512, 1, null=kind))
    runner.set_lane(3, 2, 0, 0x12345678)
    records.append(runner.call(3, 0, 1))
    runner.set_lane(3, 1, 2, 0x12345678)
    records.append(runner.call(3, 0, 1))
    return records


def reject_mutations(folder):
    original = SOURCE.read_text()
    changes = [
        ("wrong-threshold", "cmpi.l #16384, %d3 /* MODEL threshold */", "cmpi.l #16385, %d3"),
        ("global-model", "adda.l %d1, %a0 /* selected lane */", "nop"),
        ("unconditional-reset", ".Lcontinued:\n    move.l", ".Lcontinued:\n    clr.l 8(%a0)\n    move.l"),
        ("wrong-slot", "adda.l %d1, %a0 /* selected lane */", "adda.l %d1, %a0\n    adda.l #12, %a0"),
        ("out-of-range-write", "clr.l 8(%a0) /* diagnostic tail only */", "clr.l 8(%a0)\n    clr.l 0x40014000"),
        ("notice-overrun", "move.l %d2, 12(%a1)", "move.l %d2, 16(%a1)"),
        ("callee-register", "movem.l (%sp), %d2-%d4/%a2", "nop"),
        ("emac-context", ".Ldone:\n    movem.l", ".Ldone:\n    moveq #0, %d0\n    move.l %d0, %macsr\n    movem.l"),
    ]
    reports = []
    for name, before, after in changes:
        if original.count(before) != 1:
            raise AssertionError("mutation marker is not unique: " + name)
        directory = folder / name
        directory.mkdir()
        altered = directory / "selector.s"
        altered.write_text(original.replace(before, after))
        image, _ = cpu.build_coldfire(directory, altered)
        try:
            check_cases(image)
        except AssertionError as error:
            reports.append(dict(name=name, rejected=True, reason=str(error)))
        else:
            raise AssertionError("selector harness accepted defective " + name)
    return reports


def diagnose():
    with tempfile.TemporaryDirectory(prefix="x0x-coldfire-selector-") as tmp:
        folder = Path(tmp)
        image, _ = cpu.build_coldfire(folder, SOURCE)
        cases = check_cases(image)
        mutations = reject_mutations(folder)
    report = cpu.provenance("coldfire", image, SOURCE, "digiemu")
    report.pop("sample_rate", None)
    report.pop("frames", None)
    report.update(kind="assembled-per-lane-model-selector", lanes=8, cases=cases,
                  checked=["host policy trace", "mixed-model isolation", "START-only MODEL latch",
                           "invalid/missing/stale atomicity", "complete EMAC context", "callee registers/stack",
                           "every guest write", "state/input/output/context guards", "reassembled defects"],
                  unqualified=["native delivery freshness classification", "UI/saved layout/persistence",
                               "native ownership/retrigger identity", "kick DSP reset/excitation/audio",
                               "physical deadlines"],
                  audio_frames_rendered=0,
                  worst_instructions=max(case["instructions"] for case in cases),
                  selector_stack_bytes=16, wrapper_and_nested_stack_extent_bytes=32,
                  private_abi=dict(bank_bytes=96, lanes=8, lane_bytes=12,
                                   lane_words=["initialized", "model", "diagnostic_tail"],
                                   input_bytes=16, notice_bytes=16,
                                   input_words=["lane", "delivered_MODEL", "delivered_trigger", "caller_delivery_status"],
                                   notice_words=["model", "initialize", "model_changed", "clear_tail"]),
                  raw_model_range=[0, 32512], threshold=16384,
                  input_origin="synthetic delivered frames; freshness classified by caller",
                  rejected_mutations=mutations, image_sha256=hashlib.sha256(image).hexdigest())
    prefix = os.environ.get("ELEKLOADER_CROSS", "m68k-elf-")
    report["assembler"] = cpu.command([cpu.require_program(prefix + "as"), "--version"]).splitlines()[0]
    report["linker"] = cpu.command([cpu.require_program(prefix + "ld"), "--version"]).splitlines()[0]
    return report


def main(argv=None):
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    try:
        report = diagnose()
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
