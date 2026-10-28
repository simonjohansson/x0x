"""Direct SDK voice-callback instruction tests, independent of native UI."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import time

from x0x import cpu
from x0x.sharc_layout import voice_layout

ROOT = cpu.ROOT
SOURCE = ROOT / "targets/sharc/callback.s"
STATE, STATE_BYTES = voice_layout()["data_address"], 16 * 8
INPUT, PARAM, OUTPUT = 0x20094000, 0x20094100, 0x20094404
FRAME, OLD_FRAME, RETURN = 0x20095000, 0x20095100, 0xBC9FF0
GUARD = 0xA5A5A5A5
CALL_TIMEOUT_SECONDS = 10  # Hang protection, not a DSP performance budget.


def input_words(slot: int, pitch: int, flags: int, params: list[int]) -> dict[int, int]:
    if isinstance(slot, bool) or not isinstance(slot, int) or not 0 <= slot < 16:
        raise ValueError("slot must be 0..15")
    if isinstance(pitch, bool) or not isinstance(pitch, int) or not 0 <= pitch <= 0xFFFF:
        raise ValueError("pitch must be an unsigned 8.8 word")
    if isinstance(flags, bool) or not isinstance(flags, int) or flags not in (0, 1):
        raise ValueError("only SDK START or zero flags are defined")
    if len(params) != 40 or any(type(x) is not int or not 0 <= x <= 32512 for x in params):
        raise ValueError("40 unsigned 8.8 parameter words in 0..32512 are required")
    words = dict(zip(range(INPUT, INPUT + 24, 4), [OUTPUT, slot, pitch, flags, PARAM, 0]))
    words.update({PARAM + 4 * i: value for i, value in enumerate(params)})
    words.update({OUTPUT + 4 * i: GUARD for i in range(-1, 33)})
    # Exactly the software frame produced by the pinned adapter's delayed JUMP.
    words.update({FRAME: OLD_FRAME, FRAME - 4: RETURN - 1,
                  FRAME - 12: GUARD, FRAME + 4: GUARD})
    return words


def build(folder: Path, source: Path = SOURCE) -> tuple[bytes, int, Path]:
    selache = Path(os.environ.get("SELACHE", ROOT / "vendor/digikit/out/tools/selache")).resolve()
    if not (selache / "target/release/selas").is_file():
        raise cpu.Unavailable("Selache is unavailable; run mise run bootstrap")
    if cpu.revision(selache) != cpu.SELACHE_PIN:
        raise RuntimeError("Selache does not match the documented pin")
    tools = selache / "target/release"
    obj, executable = folder / "callback.doj", folder / "callback.dxe"
    cpu.command([tools / "selas", "-proc", "ADSP-21569", "-o", obj, source])
    cpu.command([tools / "seld", "-proc", "ADSP-21569", "-T", ROOT / "targets/sharc/callback.ldf",
                 "-entry", "sharc_voice_render.", "-o", executable, obj])
    code, entry = cpu.sharc_code(executable.read_bytes())
    return code, entry, selache


def check_header(folder: Path) -> str:
    header = ROOT / "vendor/elekloader/elekloader/sdk/include/digitone-mk2/voice.h"
    source = folder / "header.c"
    source.write_text('''#include <stddef.h>
#include "digitone-mk2/voice.h"
_Static_assert(sizeof(struct dn2_voice_input) == 24, "input extent");
_Static_assert(offsetof(struct dn2_voice_input, output) == 0, "output offset");
_Static_assert(offsetof(struct dn2_voice_input, slot) == 4, "slot offset");
_Static_assert(offsetof(struct dn2_voice_input, pitch) == 8, "pitch offset");
_Static_assert(offsetof(struct dn2_voice_input, flags) == 12, "flags offset");
_Static_assert(offsetof(struct dn2_voice_input, param) == 16, "parameter offset");
_Static_assert(offsetof(struct dn2_voice_input, state) == 20, "state offset");
_Static_assert(DN2_VOICE_PARAMS == 40 && DN2_VOICE_START == 1, "constants");
''')
    compiler = cpu.require_program(os.environ.get("ELEKLOADER_CROSS", "m68k-elf-") + "gcc")
    cpu.command([compiler, "-mcpu=54455", "-std=c11", "-ffreestanding", "-Werror",
                 "-I", header.parents[1], "-c", source, "-o", folder / "header.o"])
    return hashlib.sha256(header.read_bytes()).hexdigest()


def loader_memory(code: bytes, entry: int):
    cpu.require_module("tools.sharc_dev.sharc_run", "digikit")
    from tools.sharc_dev import sharcldr

    # A mapped zero endpoint keeps the all-address watch from canonicalizing
    # into the loader alias. Mapped low RAM exercises writes below that alias.
    image = code + bytes(4) + struct.pack("<I", GUARD)
    blocks = [
        {"target_address": sharcldr.sw_to_byte(entry), "byte_count": len(code),
         "fill": False, "payload_offset": 0, "payload_len": len(code)},
        {"target_address": 0, "byte_count": 4, "fill": False,
         "payload_offset": len(code), "payload_len": 4},
        {"target_address": 0x200000, "byte_count": 4, "fill": False,
         "payload_offset": len(code) + 4, "payload_len": 4},
    ]
    return sharcldr.LoadedMemory(image, blocks)


def validate_layout(layout: dict, code: bytes, entry: int) -> None:
    if entry != layout["code_pc16"] or len(code) + 64 > layout["code_bytes"]:
        raise AssertionError("callback code no longer fits the pinned SDK voice layout")
    if STATE != layout["data_address"] or STATE_BYTES > layout["data_bytes"]:
        raise AssertionError("callback state no longer fits the pinned SDK voice layout")


def negative_immediate_shifts(code: bytes) -> list[int]:
    """PRM Type6b DATAEX must sign-extend the immediate shift count."""
    offsets = []
    for offset in range(0, len(code) - 5, 2):
        a, b, c = struct.unpack_from("<3H", code, offset)
        word = (a << 32) | (b << 16) | c
        if word & 0xFFC187FF0000 == 0x020000000000:
            want = 15 if word & 0x8000 else 0
            if (word >> 27) & 15 != want:
                offsets.append(offset)
    return offsets


def decoded_instructions(code: bytes, entry: int) -> list[dict]:
    from tools.sharc_dev import sharc_trace as trace

    memory = loader_memory(code, entry)
    records = []
    pc, end = entry, entry + len(code) // 2
    while pc < end:
        record = trace.decode_at(memory, None, pc)
        if record.kind != "confident" or not record.length_bytes:
            raise AssertionError(f"instruction is not independently decoded at {pc:#x}")
        records.append({"pc16": pc, "form": record.type_name, "bytes": record.length_bytes})
        pc += record.length_bytes // 2
    if pc != end:
        raise AssertionError("decoded instructions do not cover the code exactly")
    if negative_immediate_shifts(code):
        raise AssertionError("malformed negative-immediate shift encoding")
    return records


class CallbackRunner:
    def __init__(self, code: bytes, entry: int):
        cpu.require_module("tools.sharc_dev.sharc_run", "digikit")
        from tools.sharc_dev import sharc_run, sharc_trace
        from tools.sharc_dev.sharc_core.state import (
            _mr_from_signed, _sync_empty_loop_registers, _sync_pc_stack, _sync_status_stack,
        )

        self.sr, self.trace = sharc_run, sharc_trace
        self.code, self.entry = code, entry
        self.memory = loader_memory(code, entry)
        self.words = {STATE + offset: 0 for offset in range(0, STATE_BYTES, 4)}
        self.calls = 0
        self.high_water_bytes = 0
        self.worst_instructions = 0
        self._mr = _mr_from_signed
        self._sync = (_sync_empty_loop_registers, _sync_pc_stack, _sync_status_stack)

    def call(self, slot: int, pitch: int, flags: int, params: list[int]) -> tuple[list[float], tuple[int, int]]:
        trace = self.trace
        pokes = {**self.words, **input_words(slot, pitch, flags, params),
                 STATE - 4: GUARD, STATE + STATE_BYTES: GUARD}
        registers = {name: 0x10203040 + index for index, name in enumerate(trace.UREG_NAMES)
                     if name.startswith(("R", "I", "M", "L", "B", "S")) and name[1:].isdigit()}
        registers.update(R4=INPUT, I6=FRAME, I7=FRAME - 8, MODE1=0x10000,
                         M5=0, M6=1, M7=0xFFFFFFFF, M13=0, M14=1, M15=0xFFFFFFFF,
                         **{f"L{i}": 0 for i in range(6)})
        registers.update(MODE2=0x10203040, IMASK=0x10203040, IMASKP=0x10203040,
                         PX1=0x5A, PX2=0x12345678, ASTATY=0x101, STKYY=0x202)
        runner = self.sr.Runner(self.memory, self.entry, regs=registers, pokes=pokes,
                                breakpoints=[RETURN], diagnose_unknown=True,
                                watchpoints=[self.sr.Watchpoint(0, 0x100000000,
                                                               on_read=False, stop=False)])
        runner.state.stack_model = True
        runner.state.pc_stack = [0x01000100, 0x100]
        runner.state.status_stack = [(trace.Const(0x303), trace.Const(0x404), trace.Const(0x10000))]
        runner.state.loops = [trace.Loop(0x100, 0x101, 3, 0)]
        runner.state.loop_depth = 1
        runner.state.loop_slots[0] = (trace.Const(0x101), trace.Const(3))
        runner.state.special.update({name: self._mr(0x123456789ABCDEF)
                                     for name in ("MRF", "MRB", "MSF", "MSB")})
        runner.state.special["BFFWRP"] = trace.Const(7)
        for sync in self._sync:
            sync(runner.state)
        before = copy.copy(runner.state)
        before.uregs = dict(runner.state.uregs)
        before.pc_stack = list(runner.state.pc_stack)
        before.status_stack = list(runner.state.status_stack)
        before.loops = copy.deepcopy(runner.state.loops)
        before.loop_slots = list(runner.state.loop_slots)
        before.special = dict(runner.state.special)
        before.mmrs = dict(runner.state.mmrs)
        deadline = time.monotonic() + CALL_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            try:
                runner.step()
            except self.sr.Halt as halt:
                outcome = halt
                break
            stack = runner.state.uregs[trace.UREG_CODES["I7"]]
            if not isinstance(stack, trace.Const):
                raise AssertionError("callback stack pointer became unknown")
            self.high_water_bytes = max(self.high_water_bytes, FRAME - 8 - stack.value)
        else:
            raise AssertionError("callback did not return before the test watchdog")
        if outcome.reason != "breakpoint" or runner.state.pc_sw != RETURN:
            raise AssertionError(f"callback failed to return through its C frame: {outcome}")
        self.worst_instructions = max(self.worst_instructions, runner.instructions)
        allowed = {*(f"R{i}" for i in range(16)), *(f"I{i}" for i in [0, 1, 2, 3, 4, 5, 12, 13]),
                   "ASTATX", "STKYX", "ASTATY", "STKYY", "PX", "PX1", "PX2"}
        for name, code in trace.UREG_CODES.items():
            if name not in allowed and name not in {"I6", "I7", "FADDR", "DADDR", "PC"}:
                if runner.state.uregs[code] != before.uregs[code]:
                    raise AssertionError(f"callback corrupted preserved {name}")
        if runner.state.uregs[trace.UREG_CODES["I6"]] != trace.Const(OLD_FRAME):
            raise AssertionError("callback did not restore caller I6")
        if runner.state.uregs[trace.UREG_CODES["I7"]] != trace.Const(FRAME):
            raise AssertionError("callback did not restore caller I7")
        if runner.state.pc_stack != before.pc_stack or runner.state.status_stack != before.status_stack:
            raise AssertionError("callback corrupted architectural stack contents/depth")
        if (runner.state.loops != before.loops or runner.state.special != before.special
                or runner.state.loop_slots != before.loop_slots or runner.state.loop_depth != before.loop_depth):
            raise AssertionError("callback corrupted loops, accumulators or FIFO state")
        if runner.state.mmrs != before.mmrs:
            raise AssertionError("callback changed a memory-mapped control register")
        from tools.sharc_dev.sharc_core.memory import _canonical_dm_address
        allowed_writes = [(STATE + slot * 8, STATE + slot * 8 + 8), (OUTPUT, OUTPUT + 128)]
        canonical = [(_canonical_dm_address(runner.state, low, 1, for_write=True),
                      _canonical_dm_address(runner.state, high, 1, for_write=True))
                     for low, high in allowed_writes]
        for event in runner.watch_log:
            if not any(low <= event.address and event.address + event.width <= high
                       for low, high in canonical):
                raise AssertionError(f"callback wrote outside its slot/output: {event}")
        read = lambda address: trace._dm_read(runner.state, trace.Const(address), 4)
        for address, value in pokes.items():
            if STATE <= address < STATE + STATE_BYTES or OUTPUT <= address < OUTPUT + 128:
                continue
            if read(address) != trace.Const(value):
                raise AssertionError(f"callback changed immutable input or guard at {address:#x}")
        words = [read(OUTPUT + i * 4) for i in range(32)]
        if any(not isinstance(value, trace.Const) or value.value == GUARD for value in words):
            raise AssertionError("callback left an output sample unwritten")
        samples = [struct.unpack("<f", struct.pack("<I", value.value))[0] for value in words]
        new_words = {STATE + i: read(STATE + i).value for i in range(0, STATE_BYTES, 4)}
        if any(new_words[address] != value for address, value in self.words.items()
               if not STATE + slot * 8 <= address < STATE + slot * 8 + 8):
            raise AssertionError("callback changed a different slot's state")
        self.words = new_words
        self.calls += 1
        return samples, (self.words[STATE + slot * 8], self.words[STATE + slot * 8 + 4])


def shift_regression(folder: Path) -> dict:
    from tools.sharc_dev import sharc_run, sharc_trace as trace
    base = ".SECTION/SW callback_code;\n.GLOBAL sharc_voice_render.;\nsharc_voice_render.:\nR0=0x80000000;\n"
    bad, good = folder / "bad-shift", folder / "register-shift"
    bad.mkdir()
    good.mkdir()
    bad_source, good_source = bad / "callback.s", good / "callback.s"
    bad_source.write_text(base + "R1=LSHIFT R0 BY -16;\nRTS;\n")
    good_source.write_text(base + "R7=-16;\nR1=LSHIFT R0 BY R7;\nRTS;\n")
    malformed, _, _ = build(bad, bad_source)
    bad_offsets = negative_immediate_shifts(malformed)
    if not bad_offsets:
        raise AssertionError("pinned Selache negative-immediate regression fixture changed")
    good_code, entry, _ = build(good, good_source)
    decoded_instructions(good_code, entry)
    runner = sharc_run.Runner(loader_memory(good_code, entry), entry)
    result = runner.run(max_steps=20)
    if (result.halt.reason != "return without followed call"
            or runner.state.uregs[trace.UREG_CODES["R1"]] != trace.Const(0x8000)):
        raise AssertionError("register-count shift workaround produced incorrect output")
    return {"malformed_immediate_rejected_at_bytes": bad_offsets,
            "register_count_workaround_executed": True, "expected_result": 0x8000}


def mutation_checks(folder: Path) -> list[dict]:
    changes = [("skipped-output", "R9=32;", "R9=31;"),
               ("slot-state-overrun", "R6=0x20092800;", "R6=0x20092880;"),
               ("callee-saved-register", "    R0=4;\n    R1=R4+R0;", "    M8=0;\n    R0=4;\n    R1=R4+R0;"),
               ("memory-mapped-control", "    R0=4;\n    R1=R4+R0;", "    R0=4;\n    DM(0x31400)=R0;\n    R1=R4+R0;"),
               ("low-ram-write", "    R0=4;\n    R1=R4+R0;", "    R0=4;\n    DM(0x200000)=R0;\n    R1=R4+R0;"),
               ("caller-frame-corruption", "    RFRAME;", "    I6=0;"),
               ("START-ignored", "    R6=0;", "    NOP;")]
    original = SOURCE.read_text()
    rejected = []
    for name, old, new in changes:
        if original.count(old) != 1:
            raise ValueError(f"mutation marker is not unique: {name}")
        work = folder / name
        work.mkdir()
        altered = work / "callback.s"
        altered.write_text(original.replace(old, new))
        code, entry, _ = build(work, altered)
        decoded_instructions(code, entry)
        runner = CallbackRunner(code, entry)
        try:
            runner.call(3, 12345, 1, [256] * 40)
            samples, state = runner.call(3, 12345, 1, [256] * 40)
            if samples != [256 / 32768] * 32 or state != (1, 12345):
                raise AssertionError("START did not reset this slot's diagnostic state")
        except AssertionError as error:
            rejected.append({"name": name, "reason": str(error)})
        else:
            raise AssertionError(f"callback accepted the defective {name} program")
    return rejected


def verify() -> dict:
    with tempfile.TemporaryDirectory(prefix="x0x-sharc-callback-") as tmp:
        folder = Path(tmp)
        code, entry, selache = build(folder)
        layout = voice_layout()
        validate_layout(layout, code, entry)
        header_sha = check_header(folder)
        records = decoded_instructions(code, entry)
        runner = CallbackRunner(code, entry)
        model = [0] * 16
        for slot in range(16):
            for flags, value in [(1, 0), (0, 128), (0, 32512), (1, 256)]:
                expected_count = 0 if flags else model[slot]
                params = [value] + [32512 - i for i in range(39)]
                pitch = (36 + slot) * 256 + 127
                samples, state = runner.call(slot, pitch, flags, params)
                expected = (value + expected_count) / 32768
                if samples != [expected] * 32 or state != (expected_count + 1, pitch):
                    raise AssertionError("callback output/state diverged from independent diagnostic arithmetic")
                model[slot] = expected_count + 1
        isolated, interleaved = CallbackRunner(code, entry), CallbackRunner(code, entry)
        for iteration in range(8):
            params = [12345] + [iteration] * 39
            a = isolated.call(7, 60 * 256 + 64, int(iteration == 0), params)
            for other in [0, 15, 3]:
                interleaved.call(other, 1000 + other, int(iteration == 0), [257 + other] * 40)
            b = interleaved.call(7, 60 * 256 + 64, int(iteration == 0), params)
            if a != b:
                raise AssertionError("unrelated slot interleaving changed output/state")
        unused_a, _ = runner.call(0, 1, 1, [128] + [0] * 39)
        unused_b, _ = runner.call(0, 0xFFFF, 1, [128] + [32512] * 39)
        if unused_a != unused_b:
            raise AssertionError("undeclared parameters changed diagnostic output")
        shift = shift_regression(folder)
        mutations = mutation_checks(folder)
        report = cpu.provenance("sharc", code, SOURCE, "digikit")
        report.update(kind="pr200-voice-callback", header_sha256=header_sha,
                      assembler_revision=cpu.revision(selache), input_bytes=20,
                      private_layout=layout,
                      slots=16, state_bytes=STATE_BYTES, calls=runner.calls + isolated.calls + interleaved.calls,
                      decoded_instructions=records,
                      kernel_stack_bytes=max(runner.high_water_bytes, isolated.high_water_bytes, interleaved.high_water_bytes),
                      worst_case_instructions=max(runner.worst_instructions, isolated.worst_instructions, interleaved.worst_instructions),
                      negative_shift_regression=shift, rejected_mutations=mutations,
                      adapter_call_frame_bytes=8,
                      checked=["actual 20-byte header layout", "all 16 slots", "START and repeated calls",
                               "fractional delivered parameters/pitch", "interleaving invariance",
                               "all 32 outputs", "guards and immutable inputs", "C software frame return",
                               "modeled preserved registers/architectural stacks/accumulators"],
                      unqualified=["physical instructions/timing", "native allocator and control transport",
                                   "40-bit register extension behavior not modeled by the runner"])
        return report


def main() -> int:
    try:
        result = verify()
    except cpu.Unavailable as error:
        print(json.dumps({"status": "unavailable", "reason": str(error)}))
        return 77
    except (AssertionError, OSError, RuntimeError, ValueError) as error:
        print(json.dumps({"status": "failed", "reason": str(error)}))
        return 1
    print(json.dumps({"status": "passed", **result}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
