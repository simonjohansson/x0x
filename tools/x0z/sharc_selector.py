"""Execute the combined DN2 selector ASM against the host C policy reference.

Synthetic raw SDK callbacks, not native UI transport, kick audio or firmware.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import shlex
import struct
import subprocess
import sys
import tempfile

from . import cpu, sharc_callback as callback

ROOT = cpu.ROOT
SOURCE = ROOT / "targets/sharc/selector.s"
REFERENCE = ROOT / "tests/ui/sharc_selector_reference.c"
BOUND = 1000


def case(label, slot=0, flags=1, model=0, pitch=15487):
    params = [0xffffffff] * 40
    params[:3] = [1 + slot, 128 + slot, 12345 - slot]
    params[5] = model
    return dict(label=label, slot=slot, pitch=pitch, flags=flags, params=params,
                params_present=True, input_present=True)


def cases() -> list[dict]:
    result = []
    bad = case("invalid-before-initialization", model=32512)
    bad["params"][2] = 32513
    result.append(bad)
    for phase in ("inactive", "first", "pending", "same", "switch", "repeat"):
        for slot in range(16):
            initial = 16383 if slot % 2 == 0 else 16384
            opposite = 16384 if initial == 16383 else 16383
            model = opposite if phase in ("pending", "switch", "repeat") else initial
            flags = int(phase not in ("inactive", "pending"))
            result.append(case(f"{phase}-{slot}", slot, flags, model,
                               pitch=0xffff if slot % 2 else 0))
    for threshold in (0, 16383, 16384, 32512):
        for slot in range(16):
            result.append(case(f"threshold-{threshold}-{slot}", slot, model=threshold))
    for slot in (0, 15):
        for parameter in (0, 1, 2, 5):
            for invalid in (32513, 0xffffffff):
                row = case(f"invalid-parameter-{slot}-{parameter}-{invalid}", slot)
                row["params"][parameter] = invalid
                result.append(row)
    for field, value in (("slot", 16), ("slot", 0xffffffff), ("pitch", 65536),
                         ("pitch", 0xffffffff), ("flags", 2), ("flags", 0xffffffff),
                         ("params_present", False), ("input_present", False)):
        row = case(f"invalid-{field}-{value}", 1)
        row[field] = value
        result.append(row)
    # Both models' ignored words and 808's semantically inert ATTK are explicit.
    for model in (0, 32512):
        row = case(f"ignored-base-{model}", 7, model=model)
        result.append(row)
        changed = copy.deepcopy(row)
        changed["label"] = f"ignored-change-{model}"
        for index in [3, 4, 6, 7, *range(8, 40)]:
            changed["params"][index] = index
        if model == 0:
            changed["params"][2] = 32512
        result.append(changed)
    return result


def parse_reference(text: str, count: int) -> list[dict]:
    rows = []
    for line in text.splitlines():
        words = [int(value) for value in line.split()]
        if len(words) != 39 or any(not 0 <= value <= 0xffffffff for value in words):
            raise ValueError("C selector trace must have 39 unsigned words per callback")
        if any(words[index] not in (0, 1) for index in (0, 1, 3, 4, 5)) or words[2] > 3:
            raise ValueError("C selector trace has invalid policy metadata")
        if any(words[index] > 2 for index in range(8, 39, 2)):
            raise ValueError("C selector trace has an invalid selected model")
        rows.append(dict(valid=words[0], notices=words[1], controls=words[2],
                         initialize=words[3], changed=words[4], clear=words[5],
                         numerator=words[6], state=words[7:]))
    if len(rows) != count:
        raise ValueError("C selector trace omitted or added a callback")
    return rows


def c_reference(folder: Path, inputs: list[dict]) -> tuple[list[dict], dict]:
    compiler = shlex.split(os.environ.get("CC", "clang"))
    executable = folder / "selector-reference"
    sources = [ROOT / "src/controls.c", ROOT / "machines/digitone2/adapter.c",
               ROOT / "machines/digitone2/controls.c", REFERENCE]
    cpu.command([*compiler, "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
                 "-I", ROOT / "include", "-I", ROOT / "machines/digitone2",
                 "-I", ROOT / "vendor/elekloader/elekloader/sdk/include",
                 *sources, "-o", executable])
    stream = "".join(" ".join(map(str, [row["slot"], row["pitch"], row["flags"],
                          int(row["params_present"]), int(row["input_present"]), *row["params"]])) + "\n"
                     for row in inputs)
    result = subprocess.run([executable], input=stream, text=True, capture_output=True,
                            check=True, timeout=20)
    return parse_reference(result.stdout, len(inputs)), dict(
        compiler=cpu.command([*compiler, "--version"]).splitlines()[0],
        executable_sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),
        sources={str(source.relative_to(ROOT)): hashlib.sha256(source.read_bytes()).hexdigest()
                 for source in sources}, input_origin="host-executed-C-reference-with-fake-DSP")


def raw_words(row: dict) -> dict[int, int]:
    # Start from the existing validated SDK fixture, then supply deliberate bad
    # raw fields. The ASM must reject these; Python must not filter them out.
    words = callback.input_words(0, 0, 0, [0] * 40)
    words.update({callback.INPUT + 4: row["slot"], callback.INPUT + 8: row["pitch"],
                  callback.INPUT + 12: row["flags"],
                  callback.INPUT + 16: callback.PARAM if row["params_present"] else 0})
    words.update({callback.PARAM + 4 * index: value for index, value in enumerate(row["params"])})
    return words


class SelectorRunner(callback.CallbackRunner):
    """The existing SDK callback memory/context fixture, with raw invalid inputs."""

    def call_raw(self, row: dict, state_writable: bool) -> tuple[list[float] | None, list[int]]:
        trace = self.trace
        pokes = {**self.words, **raw_words(row), callback.STATE - 4: callback.GUARD,
                 callback.STATE + callback.STATE_BYTES: callback.GUARD}
        registers = {name: 0x10203040 + index for index, name in enumerate(trace.UREG_NAMES)
                     if name.startswith(("R", "I", "M", "L", "B", "S")) and name[1:].isdigit()}
        registers.update(R4=callback.INPUT if row["input_present"] else 0,
                         I6=callback.FRAME, I7=callback.FRAME - 8, MODE1=0x10000,
                         M5=0, M6=1, M7=0xffffffff, M13=0, M14=1, M15=0xffffffff,
                         **{f"L{i}": 0 for i in range(6)})
        registers.update(MODE2=0x10203040, IMASK=0x10203040, IMASKP=0x10203040,
                         PX1=0x5a, PX2=0x12345678, ASTATY=0x101, STKYY=0x202)
        machine = self.sr.Runner(self.memory, self.entry, regs=registers, pokes=pokes,
                                 breakpoints=[callback.RETURN], diagnose_unknown=True,
                                 watchpoints=[self.sr.Watchpoint(0, 0x100000000,
                                                                on_read=False, stop=False)])
        machine.state.stack_model = True
        machine.state.pc_stack = [0x01000100, 0x100]
        machine.state.status_stack = [(trace.Const(0x303), trace.Const(0x404), trace.Const(0x10000))]
        machine.state.loops = [trace.Loop(0x100, 0x101, 3, 0)]
        machine.state.loop_depth = 1
        machine.state.loop_slots[0] = (trace.Const(0x101), trace.Const(3))
        machine.state.special.update({name: self._mr(0x123456789abcdef)
                                       for name in ("MRF", "MRB", "MSF", "MSB")})
        machine.state.special["BFFWRP"] = trace.Const(7)
        for sync in self._sync:
            sync(machine.state)
        before = copy.copy(machine.state)
        for name in ("uregs", "special", "mmrs"):
            setattr(before, name, dict(getattr(machine.state, name)))
        for name in ("pc_stack", "status_stack", "loops", "loop_slots"):
            setattr(before, name, copy.deepcopy(getattr(machine.state, name)))
        for _ in range(BOUND):
            try:
                machine.step()
            except self.sr.Halt as halt:
                if halt.reason != "breakpoint" or machine.state.pc_sw != callback.RETURN:
                    raise AssertionError("selector did not return through the SDK C frame: " + str(halt))
                break
            stack = machine.state.uregs[trace.UREG_CODES["I7"]]
            if not isinstance(stack, trace.Const):
                raise AssertionError("selector stack pointer became unknown")
            self.high_water_bytes = max(self.high_water_bytes, callback.FRAME - 8 - stack.value)
        else:
            raise AssertionError("selector exceeded its instruction bound")
        self.worst_instructions = max(self.worst_instructions, machine.instructions)
        allowed = {*(f"R{i}" for i in range(16)), *(f"I{i}" for i in (0, 1, 2, 3, 4, 5, 12, 13)),
                   "ASTATX", "STKYX", "ASTATY", "STKYY", "PX", "PX1", "PX2"}
        for name, code in trace.UREG_CODES.items():
            if name not in allowed and name not in {"I6", "I7", "FADDR", "DADDR", "PC"}:
                if machine.state.uregs[code] != before.uregs[code]:
                    raise AssertionError("selector corrupted preserved " + name)
        for name, value in (("I6", callback.OLD_FRAME), ("I7", callback.FRAME)):
            if machine.state.uregs[trace.UREG_CODES[name]] != trace.Const(value):
                raise AssertionError("selector corrupted caller " + name)
        for name in ("pc_stack", "status_stack", "loops", "loop_slots", "loop_depth", "special", "mmrs"):
            if getattr(machine.state, name) != getattr(before, name):
                raise AssertionError("selector corrupted architectural " + name)
        from tools.sharc_dev.sharc_core.memory import _canonical_dm_address
        ranges = [(callback.OUTPUT, 128)] if row["input_present"] else []
        if state_writable and row["input_present"] and row["slot"] < 16:
            ranges.append((callback.STATE + 8 * row["slot"], 8))
        owned = [(_canonical_dm_address(machine.state, low, 1, for_write=True), size)
                 for low, size in ranges]
        for event in machine.watch_log:
            if not any(low <= event.address and event.address + event.width <= low + size
                       for low, size in owned):
                raise AssertionError("selector wrote outside its slot/output: " + str(event))
        read = lambda at: trace._dm_read(machine.state, trace.Const(at), 4)
        for at, value in pokes.items():
            if callback.STATE <= at < callback.STATE + callback.STATE_BYTES:
                continue
            if callback.OUTPUT <= at < callback.OUTPUT + 128 and row["input_present"]:
                continue
            if read(at) != trace.Const(value):
                raise AssertionError("selector changed immutable input/guard at " + hex(at))
        self.words = {callback.STATE + offset: read(callback.STATE + offset).value
                      for offset in range(0, callback.STATE_BYTES, 4)}
        samples = None
        if row["input_present"]:
            words = [read(callback.OUTPUT + index * 4) for index in range(32)]
            if any(not isinstance(word, trace.Const) or word.value == callback.GUARD for word in words):
                raise AssertionError("selector left an output sample unwritten")
            samples = [struct.unpack("<f", struct.pack("<I", word.value))[0] for word in words]
        self.calls += 1
        return samples, list(self.words.values())


def compare(code: bytes, entry: int, inputs: list[dict], reference: list[dict]) -> SelectorRunner:
    runner = SelectorRunner(code, entry)
    for row, expected in zip(inputs, reference, strict=True):
        samples, state = runner.call_raw(row, state_writable=expected["notices"] == 1)
        if state != expected["state"]:
            raise AssertionError(row["label"] + ": selector state differs from the C policy reference")
        if row["input_present"] and samples != [expected["numerator"] / 131072] * 32:
            raise AssertionError(row["label"] + ": diagnostic output differs from C-delivered controls/tail")
    return runner


def mutations(folder: Path, inputs: list[dict], reference: list[dict]) -> list[dict]:
    early_store = """R3=LSHIFT R2 BY 3;
    R6=0x20092000;
    R3=R3+R6;
    I4=R3;
    R0=DM(I4,M5);
    R1=R0+1;
    DM(I4,M5)=R1;
    DM(I4,M5)=R0;
    R9=R15;"""
    changes = [("wrong-threshold", "R0=16384;", "R0=16383;"),
               ("unconditional-tail-reset", "IF EQ JUMP selected;", "NOP;"),
               ("wrong-slot", "R3=LSHIFT R2 BY 3;", "R3=0;"),
               ("output-overrun", "R9=32;", "R9=33;"),
               ("out-of-range-accepted", "IF GT JUMP silent;", "NOP;"),
               ("state-write-before-validation", "R9=R15;", early_store)]
    original = SOURCE.read_text()
    rejected = []
    for name, old, new in changes:
        if original.count(old) != 1:
            raise AssertionError("selector mutation marker is not unique: " + name)
        work = folder / name
        work.mkdir()
        altered = work / "selector.s"
        altered.write_text(original.replace(old, new))
        code, entry, _ = callback.build(work, altered)
        callback.decoded_instructions(code, entry)
        try:
            compare(code, entry, inputs, reference)
        except AssertionError as error:
            rejected.append(dict(name=name, reason=str(error)))
        else:
            raise AssertionError("selector accepted defective program: " + name)
    return rejected


def verify() -> dict:
    with tempfile.TemporaryDirectory(prefix="x0z-sharc-selector-") as tmp:
        folder = Path(tmp)
        inputs = cases()
        reference, provenance = c_reference(folder, inputs)
        code, entry, selache = callback.build(folder, SOURCE)
        layout = cpu.require_module("elekloader.sdk.sharc", "elekloader").machine_layout("voice")
        callback.validate_layout(layout, code, entry)
        header = callback.check_header(folder)
        decoded = callback.decoded_instructions(code, entry)
        runner = compare(code, entry, inputs, reference)
        rejected = mutations(folder, inputs, reference)
        report = cpu.provenance("sharc", code, SOURCE, "digikit")
        report.update(kind="combined-DN2-SHARC-selector-diagnostic", c_reference=provenance,
                      header_sha256=header, assembler_revision=cpu.revision(selache),
                      sdk_layout=layout, state_bytes=callback.STATE_BYTES, slots=16,
                      calls=runner.calls, initialized_callbacks=sum(row["notices"] for row in reference),
                      rejected_inputs=sum(not row["valid"] for row in reference),
                      kernel_stack_bytes=runner.high_water_bytes, adapter_call_frame_bytes=8,
                      instruction_bound=BOUND, worst_case_instructions=runner.worst_instructions,
                      decoded_instructions=decoded, rejected_mutations=rejected,
                      input_origin="synthetic-raw-SDK-callbacks; compiled C is a host policy reference",
                      checked=["MODEL threshold and START-only latch", "all 16 independent slots",
                               "first/model-change clear only own diagnostic tail",
                               "same-model START preserves tail", "inactive continuation stays inactive",
                               "all declared raw words validate before state writes", "blank words ignored",
                               "C control mapping checksum", "all 32 diagnostic floats", "output and state guards",
                               "bounded write ownership", "modeled SDK context and software-frame return"],
                      unqualified=["kick synthesis and fidelity", "native UI/control transport and registration",
                                   "native logical ownership and lifecycle", "downstream AMP/filter",
                                   "upstream bridge integration with selector", "hardware instructions/deadlines",
                                   "40-bit register extension behavior not modeled by runner"])
        return report


def main() -> int:
    try:
        report = verify()
    except cpu.Unavailable as error:
        print(json.dumps(dict(status="unavailable", reason=str(error))))
        return 77
    except (AssertionError, OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(json.dumps(dict(status="failed", reason=str(error))))
        return 1
    print(json.dumps(dict(status="passed", **report)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
