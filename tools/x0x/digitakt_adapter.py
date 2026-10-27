"""Bounded latest-Digitakt native routines -> C adapter -> assembled diagnostic.

This does not boot the OS, register a machine, or exercise panel/MIDI dispatch.
It uses real stock sound/lock/smoothing/LFO routines and the linked SDK's final
value accessor, then runs the production adapter and actual ASM writes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile

from . import cpu, firmware
from .fixtures import load_json

ROOT = cpu.ROOT
BASE = 0x47000000
STACK = 0x470F0000
STOP = 0xDEADBEE0
LIMIT = 200000
SOUND_INIT, MAP_INIT, ENGINE_SOUND = 0x40084EF6, 0x40078B20, 0x40077282
LOCK_RESOLVE, LOCK_APPLY, LOCK_RESTORE = 0x4006F46E, 0x40074B0A, 0x40074A40
SMOOTH, LFO, LFO_STATE = 0x40074B9E, 0x400ED766, 0x421F4E10
ENGINE = 0x800014F0

DRIVER = '''#include <stdint.h>
#include "machines/digitakt/adapter.h"
extern void x0x_diagnostic(int32_t *output, int32_t sample);
struct configuration { uint32_t track; enum x0x_instrument instrument; struct x0x_dt_binding binding; };
struct observation { uint32_t valid, calls; struct x0x_dt_snapshot snapshot;
                     enum x0x_control control; struct x0x_position position; int32_t output[32]; };
volatile struct configuration probe_config;
struct observation probe_observation;
static void receive(void *context, uint32_t track, enum x0x_control control, struct x0x_position position)
{
    struct observation *observation = context;
    (void)track;
    ++observation->calls;
    observation->control = control;
    observation->position = position;
    x0x_diagnostic(observation->output, (int32_t)(position.numerator << 16));
}
void x0x_dt_probe(void)
{
    struct configuration config = probe_config;
    probe_observation.calls = 0;
    probe_observation.valid = x0x_dt_capture(config.track, config.instrument, &config.binding, 1,
                                           &probe_observation.snapshot, receive, &probe_observation);
}
'''

FAKE_NATIVE = '''
volatile int16_t fw_voice_params[53 * 8];
volatile int32_t fw_voice_note[8];
volatile int16_t fw_voice_vel[8];
volatile uint32_t fw_voice_start;
volatile int32_t fw_amp_env[3 * 8];
int32_t cm_src_value(int32_t track, int32_t parameter)
{ return fw_voice_params[53 * track + parameter]; }
'''


def build(folder: Path, exports: dict | None = None) -> tuple[bytes, dict]:
    driver = folder / "driver.c"
    driver.write_text(DRIVER + (FAKE_NATIVE if exports is None else ""))
    linker_script = folder / "adapter.ld"
    linker_script.write_text("SECTIONS { . = 0x47000000; .text : { *(.text*) } .rodata : { *(.rodata*) } .data : { *(.data*) } .bss : { *(.bss*) *(COMMON) } }")
    prefix = os.environ.get("ELEKLOADER_CROSS", "m68k-elf-")
    objects = []
    for index, source in enumerate([ROOT / "src/controls.c", ROOT / "machines/digitakt/adapter.c", driver]):
        obj = folder / f"source{index}.o"
        cpu.command([cpu.require_program(prefix + "gcc"), "-mcpu=54455", "-std=c99", "-O2",
                     "-ffreestanding", "-fno-builtin", "-fno-pic", "-fno-pie", "-fomit-frame-pointer",
                     "-Wall", "-Wextra", "-Werror", "-I", ROOT, "-I", ROOT / "include",
                     "-I", ROOT / "vendor/elekloader/elekloader/sdk/include", "-c", source, "-o", obj])
        objects.append(obj)
    asm = folder / "diagnostic.o"
    cpu.command([cpu.require_program(prefix + "as"), "-mcpu=54455", ROOT / "targets/coldfire/diagnostic.s", "-o", asm])
    elf, binary = folder / "adapter.elf", folder / "adapter.bin"
    definitions = []
    if exports is not None:
        for name in ("cm_src_value", "fw_voice_note", "fw_voice_vel", "fw_voice_start", "fw_amp_env"):
            definitions += ["--defsym", f"{name}={exports[name]}"]
    cpu.command([cpu.require_program(prefix + "ld"), "-T", linker_script, "-e", "x0x_dt_probe",
                 *definitions, *objects, asm, "-o", elf])
    cpu.command([cpu.require_program(prefix + "objcopy"), "-O", "binary", elf, binary])
    symbols = {}
    for line in cpu.command([cpu.require_program(prefix + "nm"), "-S", elf]).splitlines():
        words = line.split()
        if len(words) == 4:
            symbols[words[3]] = (int(words[0], 16), int(words[1], 16))
    return binary.read_bytes(), symbols


def decode_observation(raw: bytes) -> dict:
    if len(raw) != 172:
        raise ValueError("compiled observation must contain exactly 172 bytes")
    values = struct.unpack(">4IiI2i3I32i", raw)
    return dict(valid=values[0], calls=values[1], track=values[2], native_start=values[3],
                note=values[4], velocity=values[5], amp_phase=values[6], amp_level=values[7],
                control=values[8], numerator=values[9], denominator=values[10],
                output_q31=list(values[11:]))


def verify_host() -> dict:
    output = ROOT / "out/host/test_digitakt_adapter"
    output.parent.mkdir(parents=True, exist_ok=True)
    compiler = cpu.require_program(os.environ.get("CC", "clang"))
    cpu.command([compiler, "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
                 "-I", ROOT, "-I", ROOT / "include", "-I", ROOT / "vendor/elekloader/elekloader/sdk/include",
                 ROOT / "src/controls.c", ROOT / "machines/digitakt/adapter.c",
                 ROOT / "tests/ui/test_digitakt_adapter.c", "-o", output])
    cpu.command([output])
    return dict(kind="digitakt-C-adapter", mode="host with native services/receiver fakes",
                checked=["fractional endpoints", "signed native ranges", "track isolation",
                         "START/note/velocity/AMP metadata", "atomic invalid-frame rejection"],
                unqualified=["native firmware delivery", "audio DSP", "machine registration"])


def verify_component() -> dict:
    harness = cpu.require_module("emu.harness", "digiemu")
    from unicorn import UC_HOOK_MEM_WRITE
    from unicorn.m68k_const import UC_M68K_REG_PC, UC_M68K_REG_SR
    with tempfile.TemporaryDirectory(prefix="x0x-dt-component-") as temporary:
        code, symbols = build(Path(temporary))
        machine = harness.Machine()
        machine.ensure(BASE)
        uc = machine.uc
        uc.mem_write(BASE, code)
        uc.reg_write(UC_M68K_REG_SR, 0x2700)
        traces = []
        target, size = symbols["probe_observation"]
        if size != 172:
            raise AssertionError("compiled observation layout changed")
        for track in (0, 7):
            for value in (0, 1, 16257, 32512):
                inputs = [(symbols["fw_voice_params"][0] + 2 * (53 * track + 2), struct.pack(">h", value)),
                          (symbols["fw_voice_start"][0], struct.pack(">I", 1 << track)),
                          (symbols["fw_voice_vel"][0] + 2 * track, struct.pack(">h", 12345)),
                          (symbols["fw_voice_note"][0] + 4 * track, struct.pack(">I", (60 << 16) + 127)),
                          (symbols["fw_amp_env"][0] + 12 * track, struct.pack(">3i", 3, 0x12345678, 0))]
                for pointer, raw in inputs:
                    uc.mem_write(pointer, raw)
                uc.mem_write(symbols["probe_config"][0], struct.pack(">6I", track, 0, 2, 1, 0, 32512))
                uc.mem_write(target, b"\xa5" * size)
                illegal = []
                def write(_uc, _access, at, length, _value, _data):
                    if not (target <= at and at + length <= target + size or STACK - 2048 <= at and at + length <= STACK):
                        illegal.append((at, length))
                hook = uc.hook_add(UC_HOOK_MEM_WRITE, write)
                try:
                    harness.call(machine, symbols["x0x_dt_probe"][0], [], ret_magic=STOP, stack_top=STACK, limit=LIMIT)
                finally:
                    uc.hook_del(hook)
                if illegal or uc.reg_read(UC_M68K_REG_PC) != STOP:
                    raise AssertionError("compiled adapter/ASM corrupted memory or failed to return")
                if any(bytes(uc.mem_read(pointer, len(raw))) != raw for pointer, raw in inputs):
                    raise AssertionError("compiled adapter changed native fixture inputs")
                observation = decode_observation(bytes(uc.mem_read(target, size)))
                if (observation["valid"], observation["calls"], observation["track"], observation["native_start"],
                    observation["control"], observation["numerator"], observation["denominator"]) != (1, 1, track, 1, 1, value, 32512):
                    raise AssertionError("compiled adapter lost the exact native control or track metadata")
                if observation["output_q31"] != [value << 16] * 32:
                    raise AssertionError("actual ASM did not write the encoded diagnostic value")
                traces.append(observation)
        report = cpu.provenance("coldfire", code, ROOT / "machines/digitakt/adapter.c", "digiemu")
        report.update(kind="digitakt-adapter-component", traces=traces,
                      checked=["compiled production C adapter", "actual ASM output", "track identity",
                               "fractional controls", "read-only native fixture inputs", "owned writes"],
                      unqualified=["native control delivery (services are fakes)", "firmware boot/selection",
                                   "locks and modulation", "device timing and kick fidelity"])
        return report


def verify() -> dict:
    from elekloader import formats
    harness = cpu.require_module("emu.harness", "digiemu")
    from unicorn import UC_HOOK_MEM_WRITE
    from unicorn.m68k_const import UC_M68K_REG_PC, UC_M68K_REG_SR

    entries, sdk_revision = firmware.baseline()
    stock_report = firmware.verify_entry(entries["digitakt-mk1"], ROOT / "firmware", sdk_revision)
    if stock_report["version"] != "1.54":
        raise ValueError("the bounded Digitakt native probe requires the latest OS 1.54 profile")
    baseline = ROOT / "out/dt/x0x-baseline.syx"
    mapping_path = baseline.with_suffix(".syx.map.json")
    if not baseline.is_file() or not mapping_path.is_file():
        raise cpu.Unavailable("build the latest baseline with mise run firmware:dt")
    baseline_report = load_json(ROOT / "out/dt/baseline-build.json")
    baseline_hash = hashlib.sha256(baseline.read_bytes()).hexdigest()
    if baseline_hash != baseline_report["baseline_sha256"]:
        raise ValueError("baseline firmware identity differs from its build report")
    _, device, _ = formats.load(stock_report["image"])
    image = formats.main_image(formats.parse(baseline, device), device)
    exports = load_json(mapping_path)
    address = {name: int(value, 0) for name, value in exports.items()}
    with tempfile.TemporaryDirectory(prefix="x0x-digitakt-adapter-") as temporary:
        code, symbols = build(Path(temporary), exports)
        machine = harness.Machine()
        machine.load(image, device.main_load)
        machine.install_isa_patches_scoped(image, device.main_load)
        for region in (BASE, STACK, 0x43000000, 0x43400000, 0x43500000, 0x80000000, address["fw_amp_env"]):
            machine.ensure(region)
        run_source = address["__run_load"] - device.main_load
        run_bytes = address["__run_words"] * 4
        if not 0 <= run_source < run_source + run_bytes <= len(image):
            raise ValueError("linked SDK run image is outside the baseline")
        machine.ensure(address["__run_start"])
        machine.uc.mem_write(address["__run_start"], image[run_source:run_source + run_bytes])
        machine.uc.mem_write(address["__bss_start"], bytes(address["__bss_words"] * 4))
        machine.uc.mem_write(BASE, code)
        machine.uc.reg_write(UC_M68K_REG_SR, 0x2700)
        uc = machine.uc
        native_calls = []

        def native(function, arguments):
            result = harness.call(machine, function, arguments, ret_magic=STOP, stack_top=STACK, limit=LIMIT)
            if uc.reg_read(UC_M68K_REG_PC) != STOP:
                raise AssertionError(f"native routine {function:#x} failed to return")
            native_calls.append(function)
            return result

        def mode(value):
            start = {0x20: 0x4006A868, 0xA0: 0x40074732}[value]
            if image[start - device.main_load:start - device.main_load + 6] != b"\xa9\x3c" + struct.pack(">I", value):
                raise AssertionError("stock MACSR setup instruction does not match the pinned release")
            uc.emu_start(start, start + 6, count=1)
            if uc.reg_read(UC_M68K_REG_PC) != start + 6:
                raise AssertionError("stock MACSR setup failed")

        native(MAP_INIT, [])
        kit = 0x43000000
        uc.mem_write(address["FW_KIT"], struct.pack(">I", kit))
        sounds = [kit + 0x20 + 162 * track for track in range(8)]
        for track, sound in enumerate(sounds):
            native(SOUND_INIT, [sound, 0, 3])
            params = list(struct.unpack(">53h", uc.mem_read(sound + 20, 106)))
            params[19] = 8001 + track
            uc.mem_write(sound + 20, struct.pack(">53h", *params))
            native(ENGINE_SOUND, [sound, track])
        uc.mem_write(address["fw_voice_start"], struct.pack(">I", 1 << 3))
        uc.mem_write(address["fw_voice_note"], struct.pack(">8i", *[(60 << 16) + track for track in range(8)]))
        uc.mem_write(address["fw_voice_vel"], struct.pack(">8h", *[20001 + track for track in range(8)]))
        uc.mem_write(address["fw_amp_env"], struct.pack(">24i", *[i * 4097 for i in range(24)]))
        trace = []

        def capture(track, phase):
            config = struct.pack(">6I", track, 0, 2, 1, 0, 32512)
            uc.mem_write(symbols["probe_config"][0], config)
            target, size = symbols["probe_observation"]
            if size != 172:
                raise AssertionError("compiled trace structure has an unexpected layout")
            uc.mem_write(target, b"\xa5" * size)
            immutable = [(address["fw_voice_params"], 8 * 53 * 2),
                         (address["fw_voice_note"], 32), (address["fw_voice_vel"], 16),
                         (address["fw_voice_start"], 4), (address["fw_amp_env"], 96)]
            before = [bytes(uc.mem_read(start, length)) for start, length in immutable]
            expected = struct.unpack(">h", uc.mem_read(address["fw_voice_params"] + (53 * track + 2) * 2, 2))[0]
            writes = []
            allowed = [(target, target + size), (STACK - 2048, STACK)]
            def write(_uc, _access, at, length, _value, _data):
                if not any(first <= at and at + length <= last for first, last in allowed):
                    writes.append((at, length))
            hook = uc.hook_add(UC_HOOK_MEM_WRITE, write)
            try:
                native(symbols["x0x_dt_probe"][0], [])
            finally:
                uc.hook_del(hook)
            if writes:
                raise AssertionError(f"adapter/ASM wrote outside its trace/stack: {writes}")
            if before != [bytes(uc.mem_read(start, length)) for start, length in immutable]:
                raise AssertionError("adapter changed native parameters, velocity, pitch or AMP")
            result = decode_observation(bytes(uc.mem_read(target, size)))
            if (result["valid"], result["calls"], result["track"], result["control"]) != (1, 1, track, 1):
                raise AssertionError("compiled C adapter rejected/misrouted the native frame")
            if (result["numerator"], result["denominator"]) != (expected, 32512):
                raise AssertionError("compiled C adapter changed the delivered fractional value")
            expected_metadata = {
                "native_start": (int.from_bytes(uc.mem_read(address["fw_voice_start"], 4), "big") >> track) & 1,
                "note": struct.unpack(">i", uc.mem_read(address["fw_voice_note"] + 4 * track, 4))[0],
                "velocity": struct.unpack(">h", uc.mem_read(address["fw_voice_vel"] + 2 * track, 2))[0],
                "amp_phase": struct.unpack(">i", uc.mem_read(address["fw_amp_env"] + 12 * track, 4))[0],
                "amp_level": struct.unpack(">i", uc.mem_read(address["fw_amp_env"] + 12 * track + 4, 4))[0],
            }
            if any(result[name] != value for name, value in expected_metadata.items()):
                raise AssertionError("compiled adapter changed native lifecycle/AMP metadata")
            if result["output_q31"] != [expected << 16] * 32:
                raise AssertionError("actual ASM did not render the delivered diagnostic value")
            result["phase"] = phase
            trace.append(result)
            return result

        def smooth():
            mode(0xA0)
            if native(SMOOTH, [ENGINE]) != 0x80002760:
                raise AssertionError("native smoother returned a different render frame")

        smooth()
        for track in range(8):
            if capture(track, "native-base")["numerator"] != 8001 + track:
                raise AssertionError("native base sound did not reach its own track")
        native(address["fw_set_param"], [16001, 0, 19])
        edits = []
        for block in range(8):
            smooth()
            edits.append(capture(0, f"native-parameter-edit-{block}")["numerator"])
        if not 8001 < edits[0] < edits[-1] <= 16001 or edits != sorted(edits):
            raise AssertionError("native parameter target did not produce the expected monotonic delivered ramp")
        native(address["fw_set_param"], [8001, 0, 19])
        restored_edits = []
        for block in range(3):
            smooth()
            restored_edits.append(capture(0, f"native-parameter-restore-{block}")["numerator"])
        if not 8001 <= restored_edits[-1] < restored_edits[0] < edits[-1]:
            raise AssertionError("native parameter restoration did not reverse the delivered ramp")
        # Each later case starts from a new stock note snapshot, not a live-ramp remainder.
        native(ENGINE_SOUND, [sounds[0], 0])
        smooth()
        if capture(0, "native-parameter-restored")["numerator"] != 8001:
            raise AssertionError("native note snapshot did not restore the base render value")
        locks, resolved, step = 0x43400000, 0x43500000, 3
        uc.mem_write(locks, struct.pack(">h", -1) * (54 * 64))
        uc.mem_write(locks + 108 * step + 2 * 19, struct.pack(">h", 12345))
        native(LOCK_RESOLVE, [resolved, locks, 0, step])
        if struct.unpack(">I", uc.mem_read(resolved + 8, 4))[0] != 1:
            raise AssertionError("native lock resolver did not deliver one declared lock")
        if bytes(uc.mem_read(resolved + 20, 4)) != struct.pack(">Hh", 19, 12345):
            raise AssertionError("native lock resolver changed the slot/fractional lock")
        native(LOCK_APPLY, [0, resolved, ENGINE])
        smooth()
        locked = capture(0, "native-lock")
        if locked["numerator"] != 12345:
            raise AssertionError("native lock did not reach the actual render frame")
        for track in range(1, 8):
            if capture(track, "other-track-during-lock")["numerator"] != 8001 + track:
                raise AssertionError("a lock changed an unrelated track's control")
        native(LOCK_RESTORE, [0, ENGINE, sounds[0]])
        smooth()
        restored = capture(0, "native-lock-restored")
        if restored["numerator"] != 8001:
            raise AssertionError("native lock restoration did not restore the base control")

        machine.ensure(LFO_STATE)
        uc.mem_write(LFO_STATE, bytes(8 * 2 * 40))
        for track, sound in enumerate(sounds):
            params = list(struct.unpack(">53h", uc.mem_read(sound + 20, 106)))
            params[4], params[12] = 19 << 8, 24 << 8
            params[1] = params[9] = 0x5000
            params[5] = params[13] = 2 << 8
            params[6] = params[14] = 0x4000
            params[7] = params[15] = 1 << 8
            params[8] = params[16] = 0x4800
            uc.mem_write(sound + 20, struct.pack(">53h", *params))
            native(ENGINE_SOUND, [sound, track])
        modulation = []
        for block in range(3):
            smooth()
            mode(0x20)
            native(LFO, [0x80002760, 14400, 0xFF if block == 0 else 0])
            modulation.append([capture(track, f"native-lfo-{block}")["numerator"] for track in range(8)])
        if modulation[0][0] != 8001 + 4095 or modulation[1][0] != 8001 - 4096:
            raise AssertionError("native LFO did not produce the independent expected modulation")
        if modulation[0] != [8001 + track + 4095 for track in range(8)] or modulation[1] != [8001 + track - 4096 for track in range(8)]:
            raise AssertionError("native LFO delivery leaked across track identities")
        report = cpu.provenance("coldfire", code, ROOT / "machines/digitakt/adapter.c", "digiemu")
        report.update(kind="digitakt-native-adapter", device="digitakt-mk1", os="1.54",
                      baseline_sha256=baseline_hash, stock_sha256=stock_report["image_sha256"],
                      mode="bounded native routines; no full boot or panel/MIDI dispatch",
                      native_call_bound=LIMIT, native_calls=len(native_calls), traces=trace,
                      native_parameter_ramp_8_8=edits, native_parameter_restore_8_8=restored_edits,
                      modulation_8_8=modulation,
                      checked=["compiled C adapter", "linked SDK cm_src_value", "all eight tracks",
                               "native parameter edit", "native lock resolve/apply/restore", "native smoothing and LFO delivery",
                               "fractional values", "actual assembled output", "native input preservation",
                               "adapter-owned write ranges"],
                      unqualified=["full firmware boot and render-hook dispatch", "native panel/MIDI UI",
                                   "real-time onset latency", "native allocator/retrigger policy",
                                   "stock downstream audio response", "hardware and kick fidelity"])
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--host", action="store_true")
    mode.add_argument("--native", action="store_true")
    args = parser.parse_args()
    try:
        report = verify_host() if args.host else verify() if args.native else verify_component()
    except cpu.Unavailable as error:
        print(json.dumps(dict(status="unavailable", reason=str(error))))
        return 77
    except (AssertionError, OSError, RuntimeError, ValueError) as error:
        print(json.dumps(dict(status="failed", reason=str(error))))
        return 1
    print(json.dumps(dict(status="passed", **report)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
