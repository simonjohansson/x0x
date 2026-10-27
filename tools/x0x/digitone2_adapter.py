"""Compiled C bindings into the pinned SHARC callback; not native OS transport."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import struct
import sys
import tempfile

from . import cpu, sharc_callback

ROOT = cpu.ROOT
SOURCE = ROOT / "machines/digitone2/adapter.c"
CASES = ((15, 1, 1), (2, 1, 32512), (15, 0, 128),
         (15, 0, 12345), (15, 1, 0), (15, 0, 256))


def compile_host(folder: Path, source: Path = SOURCE) -> Path:
    compiler = shlex.split(os.environ.get("CC", "clang"))
    executable = folder / "digitone2-controls"
    cpu.command([*compiler, "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
                 "-I", ROOT / "include", "-I", SOURCE.parent,
                 "-I", ROOT / "vendor/elekloader/elekloader/sdk/include",
                 ROOT / "src/controls.c", source,
                 ROOT / "tests/ui/test_digitone2_adapter.c", "-o", executable])
    return executable


def validate_trace(trace: list[dict]) -> list[dict]:
    if not isinstance(trace, list) or len(trace) != len(CASES):
        raise ValueError("compiled C trace must have six callback snapshots")
    for index, (record, expected) in enumerate(zip(trace, CASES)):
        if not isinstance(record, dict) or set(record) != {"slot", "pitch", "flags", "params"}:
            raise ValueError("invalid C transport snapshot fields")
        params = record["params"]
        if (type(record["slot"]) is not int or type(record["pitch"]) is not int
                or type(record["flags"]) is not int
                or (record["slot"], record["flags"]) != expected[:2]
                or record["pitch"] != 60 * 256 + 127
                or not isinstance(params, list) or len(params) != 40
                or any(type(value) is not int or not 0 <= value <= 32512 for value in params)):
            raise ValueError("compiled C snapshot lost slot, pitch or delivered fractional values")
        if params[0] != expected[2] or params[8] != 257 + index:
            raise ValueError("C receiver altered a declared value")
        if any(value != 0 for position, value in enumerate(params) if position not in {0, 8}):
            raise ValueError("C receiver consumed an undeclared parameter")
    return trace


def host_check(folder: Path) -> tuple[dict, list[dict]]:
    executable = compile_host(folder)
    cpu.command([executable])
    trace = validate_trace([json.loads(line) for line in cpu.command([executable, "--trace"]).splitlines()])
    report = dict(kind="isolated-C-DN2-bindings", status="passed",
                  c_source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                  adapter_header_sha256=hashlib.sha256((SOURCE.parent / "adapter.h").read_bytes()).hexdigest(),
                  executable_sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),
                  host_compiler=cpu.command([*shlex.split(os.environ.get("CC", "clang")), "--version"]).splitlines()[0],
                  control_source_sha256=hashlib.sha256((ROOT / "src/controls.c").read_bytes()).hexdigest(),
                  callbacks=len(trace), trace=trace,
                  checked=["SDK page labels/defaults and empty slots", "declared values only",
                           "exact 8.8 fractions", "slot is not track", "parameters before START notice",
                           "rejected input has no partial notifications", "audio left untouched"],
                  input_origin="synthetic-delivered-parameter-snapshots",
                  unqualified=["native UI/MIDI/parameter locks", "OS smoothing/modulation",
                               "native allocator identity/retrigger semantics", "stock AMP routing"])
    return report, trace


def cross_check(folder: Path) -> dict:
    prefix = os.environ.get("ELEKLOADER_CROSS", "m68k-elf-")
    compiler = cpu.require_program(prefix + "gcc")
    objects = []
    for name, source in [("controls", ROOT / "src/controls.c"), ("adapter", SOURCE)]:
        obj = folder / (name + ".o")
        cpu.command([compiler, "-mcpu=54455", "-msoft-float", "-std=c99", "-O2",
                     "-ffreestanding", "-fno-builtin", "-Wall", "-Wextra", "-Werror",
                     "-I", ROOT / "include", "-I", SOURCE.parent,
                     "-I", ROOT / "vendor/elekloader/elekloader/sdk/include",
                     "-c", source, "-o", obj])
        objects.append(obj)
    linked = folder / "adapter-linked.o"
    cpu.command([cpu.require_program(prefix + "ld"), "-r", *objects, "-o", linked])
    imports = cpu.command([cpu.require_program(prefix + "nm"), "-u", linked]).strip()
    if imports:
        raise AssertionError("DN2 C plumbing has unexpected runtime imports: " + imports)
    return dict(compiler=cpu.command([compiler, "--version"]).splitlines()[0],
                unresolved_runtime_imports=[])


def rejected_c_mutations(folder: Path) -> list[dict]:
    original = SOURCE.read_text()
    changes = [
        ("fractional-value-truncation", "input->param[binding->parameter], 32512",
         "input->param[binding->parameter] & ~255u, 32512"),
        ("wrong-slot", "x0x_send_control(instrument, input->slot, binding->control,",
         "x0x_send_control(instrument, 0, binding->control,"),
        ("double-level-scaling", "input->param[binding->parameter], 32512",
         "input->param[binding->parameter] / 2, 32512"),
    ]
    rejected = []
    for name, old, new in changes:
        if original.count(old) != 1:
            raise AssertionError("C mutation marker must be unique: " + name)
        directory = folder / name
        directory.mkdir()
        altered = directory / "adapter.c"
        altered.write_text(original.replace(old, new))
        executable = compile_host(directory, altered)
        try:
            cpu.command([executable])
        except RuntimeError:
            rejected.append(dict(name=name, rejected=True))
        else:
            raise AssertionError("C transport tests accepted defective " + name)
    return rejected


def check_bridge_writes(writes, ranges, canonicalize) -> None:
    # The exclusive end may be unbacked and resolve to a different alias.
    # Resolve each region's start once, then retain its byte extent.
    allowed = [(canonicalize(low), high - low) for low, high in ranges]
    for write in writes:
        if not any(low <= write.address and write.address + write.width <= low + size
                   for low, size in allowed):
            raise AssertionError("upstream bridge wrote unowned memory: " + str(write))


def bridge_check(code: bytes, entry: int) -> dict:
    """Execute the pinned upstream bridge with synthetic native DSP frames."""
    cpu.require_module("tools.sharc_dev.sharc_run", "digikit")
    from tools.sharc_dev import sharcldr, sharc_run, sharc_trace as trace

    bridge_path = ROOT / "vendor/elekloader/elekloader/sdk/include/digitone-mk2/voice-bridge.json"
    bridge = bytes.fromhex(json.loads(bridge_path.read_text())["hex"])
    if len(bridge) != 2048:
        raise AssertionError("the pinned voice bridge extent changed")
    window = bytearray(16384)
    window[:len(bridge)] = bridge
    window[2048:8192] = code + b"\1\0" * ((6144 - len(code)) // 2)
    struct.pack_into("<II", window, 0x3e00, entry, 31)
    frame_base, output_base, stack = 0x25c48c, 0x804acf90, 0x20095000
    payload = bytes(window) + bytes(4096) + bytes(16 * 128) + bytes(4)
    pieces = [(0x20090000, len(window)), (frame_base, 4096), (output_base, 16 * 128), (0, 4)]
    blocks, offset = [], 0
    for address, size in pieces:
        blocks.append(dict(target_address=address, byte_count=size, fill=False,
                           payload_offset=offset, payload_len=size))
        offset += size
    memory = sharcldr.LoadedMemory.from_stream(payload, blocks)
    state = {address: 0 for address in range(0x20092000, 0x20092080, 4)}
    state.update({address: 0 for address in range(0x20093c00, 0x20094000, 4)})
    state.update({0x20093e00: entry, 0x20093e04: 31})
    expected_count = [0] * 16
    observations, worst = [], 0

    def call(slot, trigger, value, machine=31, second_caller=False):
        nonlocal state, worst
        frame = bytearray(4096)
        pitch = (36 + slot) * 256 + 127
        struct.pack_into("<H", frame, (74 + slot) * 2, machine)
        struct.pack_into("<H", frame, (slot + 1) * 2, pitch)
        params = [value] + [257 + slot + index for index in range(1, 39)] + [0xffff]
        for index, parameter in enumerate(params):
            struct.pack_into("<H", frame, (0x6d + 0x49 * slot + index) * 2, parameter)
        for index, address in enumerate((0x25c4ac, 0x25c4b0)):
            at = address - frame_base
            previous = struct.unpack_from("<I", frame, at)[0]
            struct.pack_into("<I", frame, at, (previous & 0xffff) | ((trigger << slot) << 16) if index == 0 else previous & 0xffff)
        output = output_base + slot * 128
        pokes = {**state, **{frame_base + index: struct.unpack_from("<I", frame, index)[0]
                            for index in range(0, len(frame), 4)},
                 **{output + index * 4: 0x3d800000 for index in range(32)},
                 output - 4: 0xa5a5a5a5, output + 128: 0xa5a5a5a5,
                 stack - 12: 0xa5a5a5a5, stack + 4: 0xa5a5a5a5}
        registers = {f"R{index}": 0x100000 + index for index in range(16)}
        registers.update(R8=output + int(second_caller), R12=output, R15=16 - slot,
                         I6=0x20095100, I7=stack, MODE1=0x10000, PX1=0, PX2=0)
        runner = sharc_run.Runner(memory, entry - 1024, regs=registers, pokes=pokes,
                                  breakpoints=[0xb8251e], diagnose_unknown=True,
                                  watchpoints=[sharc_run.Watchpoint(0, 0x100000000, on_read=False, stop=False)])
        runner.state.stack_model = True
        result = runner.run(max_steps=4000)
        if result.halt.reason != "breakpoint":
            raise AssertionError("upstream bridge failed: " + str(result.halt.to_json()))
        worst = max(worst, result.instructions)
        from tools.sharc_dev.sharc_core.memory import _canonical_dm_address
        allowed = [(0x20093c00, 0x20094000), (0x20092000 + slot * 8, 0x20092008 + slot * 8),
                   (output, output + 128), (stack - 4, stack + 4)]
        check_bridge_writes(runner.watch_log, allowed,
                            lambda address: _canonical_dm_address(runner.state, address, 1, for_write=True))
        read = lambda address: trace._dm_read(runner.state, trace.Const(address), 4)
        if any(read(address) != trace.Const(value) for address, value in pokes.items()
               if frame_base <= address < frame_base + len(frame)):
            raise AssertionError("bridge changed the immutable stock frame")
        for address in (output - 4, output + 128, stack - 12, stack + 4):
            if read(address) != trace.Const(0xa5a5a5a5):
                raise AssertionError("bridge changed a buffer/frame guard")
        for address, previous in state.items():
            if 0x20092000 <= address < 0x20092080 and not 0x20092000 + slot * 8 <= address < 0x20092008 + slot * 8:
                if read(address) != trace.Const(previous):
                    raise AssertionError("bridge changed an unrelated author slot")
        state = {address: read(address).value for address in state}
        if state[0x20093e00] != entry or state[0x20093e04] != 31:
            raise AssertionError("bridge changed its callback binding")
        words = [read(output + 4 * index) for index in range(32)]
        if any(not isinstance(word, trace.Const) for word in words):
            raise AssertionError("bridge left unknown output")
        samples = [struct.unpack("<f", struct.pack("<I", word.value))[0] for word in words]
        callback_count = state[0x20092000 + slot * 8]
        flags = state[0x20093d0c]
        return samples, callback_count, flags, pitch, params, read

    for slot in range(16):
        for block, (trigger, value) in enumerate(((1, 32512), (1, 1), (0, 128), (1, 12345), (1, 32512))):
            samples, count, flags, pitch, params, read = call(slot, trigger, value)
            edge = block in (0, 3)
            if edge:
                if samples != [0.0] * 32 or count != expected_count[slot]:
                    raise AssertionError("trigger edge must be silent without invoking the kernel")
            else:
                start = block in (1, 4)
                if start:
                    expected_count[slot] = 0
                expected = (value + expected_count[slot]) / 32768
                if samples != [expected] * 32 or flags != int(start):
                    raise AssertionError("bridge lost settled values or next-block START")
                expected_count[slot] += 1
                if count != expected_count[slot] or state[0x20092004 + slot * 8] != pitch:
                    raise AssertionError("bridge delivered incorrect slot or pitch")
                if [read(0x20093d14 + 4 * index).value for index in range(40)] != params:
                    raise AssertionError("bridge did not copy all forty packed parameter halfwords")
            observations.append(dict(slot=slot, block=block, trigger=trigger, raw=value,
                                     silent_edge=edge, callback_count=count,
                                     delivered_start=None if edge else flags))
    for machine, second in [(0, False), (31, True)]:
        samples, _, _, _, _, _ = call(3, 0, 12345, machine=machine, second_caller=second)
        if samples != [.0625] * 32:
            raise AssertionError("nonmatching stock caller was not preserved")
    return dict(kind="actual-pinned-SHARC-bridge-with-synthetic-stock-frames", calls=len(observations) + 2,
                temporary_test_machine=31, persistent_registration=False,
                bridge_sha256=hashlib.sha256(bridge).hexdigest(), observations=observations,
                worst_instructions=worst,
                checked=["silent trigger edge", "START in next settled block", "all sixteen slots",
                         "all forty packed halfwords including undeclared data", "raw fractional pitch/controls",
                         "stock/nonvoice caller pass-through", "write ownership and guards"],
                unqualified=["native ColdFire OS control delivery", "MIDI/encoder/parameter lock processing",
                             "OS smoothing and native allocator/retrigger identity"])


def diagnose(host_only=False) -> dict:
    with tempfile.TemporaryDirectory(prefix="x0x-dn2-adapter-") as tmp:
        folder = Path(tmp)
        report, trace = host_check(folder)
        report["rejected_c_mutations"] = rejected_c_mutations(folder)
        report["project_revision"] = cpu.revision(ROOT)
        report["project_dirty"] = bool(cpu.command(["git", "status", "--porcelain", "--untracked-files=normal"], cwd=ROOT).strip())
        report["elekloader_revision"] = cpu.revision(ROOT / "vendor/elekloader")
        if host_only:
            return report
        report["cross_compiled_C"] = cross_check(folder)
        code, entry, selache = sharc_callback.build(folder)
        sdk = cpu.require_module("elekloader.sdk.sharc", "elekloader")
        sharc_callback.validate_layout(sdk.machine_layout("voice"), code, entry)
        sharc_callback.decoded_instructions(code, entry)
        runner = sharc_callback.CallbackRunner(code, entry)
        counts = [0] * 16
        outputs = []
        for snapshot in trace:
            slot, flags, params = snapshot["slot"], snapshot["flags"], snapshot["params"]
            if flags:
                counts[slot] = 0
            expected = (params[0] + counts[slot]) / 32768
            samples, state = runner.call(slot, snapshot["pitch"], flags, params)
            if samples != [expected] * 32 or state != (counts[slot] + 1, snapshot["pitch"]):
                raise AssertionError("assembled SHARC output differs from compiled C delivery")
            counts[slot] += 1
            outputs.append(dict(slot=slot, flags=flags, delivered_raw=params[0],
                                first_sample=samples[0], sample_count=len(samples), state=list(state)))
        report.update(kind="compiled-C-to-Digikit-SHARC-component", emulator="digikit",
                      emulator_revision=cpu.revision(ROOT / "vendor/digikit"),
                      assembler_revision=cpu.revision(selache),
                      image_sha256=hashlib.sha256(code).hexdigest(), outputs=outputs,
                      header_sha256=sharc_callback.check_header(folder),
                      native_os_transport_status="unavailable",
                      trigger_edge_status="not observed; component consumes settled callback values only")
        report["upstream_bridge"] = bridge_check(code, entry)
        report["trigger_edge_status"] = "observed in actual pinned SHARC bridge with synthetic stock DSP frames"
        return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = diagnose(args.host)
    except cpu.Unavailable as error:
        print(json.dumps(dict(status="unavailable", reason=str(error))))
        return 77
    except (AssertionError, OSError, RuntimeError, ValueError) as error:
        print(json.dumps(dict(status="failed", reason=str(error))))
        return 1
    print(json.dumps(report, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
