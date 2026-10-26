"""Probe existing DN Core events; no production adapter or firmware API changes.

Default: bounded native stages with explicitly injected state. --full-os:
40 ms of the standard non-strict Session, separately from strict qualification.
Generated subscribers, firmware, private emulator cards and reports stay in out/dn.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
from pathlib import Path
import signal
import struct
import sys
import time

from . import cpu, firmware

ROOT = cpu.ROOT
FOLDER = ROOT / "out/dn/transport"
FRAME_BYTES = 8 * 79 * 2
POINTERS = (0x80002006, 0x80002A96)
ORDER = ["in", "pre", "controller", "lfo", "final", "late", "out"]
LIMIT, RETURN, STACK = 200000, 0xDEADBEE0, 0x470F0000
STRICT_LIMIT = ("Unqualified: under the separate strict-stop model, both baseline and observer "
                "stop at stock PC 0x4009de90 (b6a8012a), reading 0x12a with A0=0; "
                "the standard Session result is not a strict-model pass.")
DRIVER = r'''
#include <stdint.h>
#include "digitone-mk1/core3.h"
volatile uint32_t probe_count[6], probe_pending, probe_capture_block, probe_pre_value;
volatile int16_t probe_copy[632];
void probe_in(void) { probe_pending = 0; ++probe_count[0]; }
void probe_pre(int16_t *words)
{
    probe_pending = (uint32_t)words;
    probe_capture_block = probe_count[0];
    probe_pre_value = (uint16_t)words[79 * 3 + 27];
    ++probe_count[1];
}
void probe_late(int32_t *voices)
{
    const volatile int16_t *words = (const volatile int16_t *)probe_pending;
    uint32_t i;
    (void)voices;
    if (!words || probe_capture_block != probe_count[0]) {
        ++probe_count[3]; probe_pending = 0; return;
    }
    for (i = 0; i < 632; ++i) probe_copy[i] = words[i];
    ++probe_count[2];
    probe_pending = 0;
}
void probe_out(void)
{
    if (probe_pending) ++probe_count[5];
    probe_pending = 0; ++probe_count[4];
}
'''


def validate_trace(traces):
    """Reject early/target frames, changed banks and incomplete event cycles."""
    if not traces:
        raise AssertionError("no complete DN event cycles observed")
    previous, previous_block = None, None
    for trace in traces:
        pointer = trace.get("pointer")
        if trace.get("order") != ORDER or pointer not in POINTERS or pointer == previous:
            raise AssertionError("DN event order or alternating frame bank diverged")
        block = trace.get("block")
        if type(block) is not int or block < 1 or previous_block is not None and block != previous_block + 1:
            raise AssertionError("DN captured block identity diverged")
        if any(type(trace.get(key)) is not int or not 0 <= trace[key] <= 65535 for key in ("pre", "final")):
            raise AssertionError("DN frame trace lost its native word")
        if trace.get("late_pointer") not in (0, pointer):
            raise AssertionError("DN observer consumed a different block's bank")
        if not trace.get("late_pointer") and trace.get("late") is not None:
            raise AssertionError("DN observer reported a value without a capture")
        if trace.get("late_pointer") and trace.get("late") != trace.get("final"):
            raise AssertionError("DN late capture differs from the actual final word")
        previous, previous_block = pointer, block


def build():
    entries, revision = firmware.baseline()
    stock = firmware.verify_entry(entries["digitone-mk1"], ROOT / "firmware", revision)
    if stock["version"] != "1.44":
        raise ValueError("DN transport sites require the reviewed latest OS 1.44")
    mod = FOLDER / "observer"
    mod.mkdir(parents=True, exist_ok=True)
    (mod / "probe.c").write_text(DRIVER)
    descriptor = dict(id="x0z-dn-transport-probe", version="0.0", title="DN test observer",
                      device="digitone-mk1", os="1.44", license="GPL-2.0-or-later",
                      sources=["probe.c"], requires=["core"], subscribe=[
                          dict(event=event, fn=fn, order=order) for event, fn, order in (
                              ("ev_render_in", "probe_in", 10), ("ev_render_params", "probe_pre", 100),
                              ("ev_render_voices", "probe_late", 40), ("ev_render_out", "probe_out", 90))])
    (mod / "mod.json").write_text(json.dumps(descriptor, indent=2) + "\n")
    artifacts, logs = [], []
    # Build every dependency here: no prerequisite baseline/prototype artifacts.
    for source in (ROOT / "vendor/elekloader/mods/core-dn1",
                   ROOT / "vendor/elekloader/mods/machines-dn1", mod):
        metadata = json.loads((source / "mod.json").read_text())
        output = FOLDER / "deps" / metadata["id"]
        logs.append(cpu.command([sys.executable, "-m", "elekloader.sdk.build", source,
                                 "--stock", stock["image"], "--out", output]))
        suffix = "-os1.44" if metadata["os"] != "1.44" else ""
        artifact = output / f'{metadata["id"]}-{metadata["version"]}{suffix}.elemod'
        if not artifact.is_file():
            raise ValueError("SDK did not produce the expected DN dependency: " + str(artifact))
        artifacts.append(artifact)
    image = FOLDER / "transport.syx"
    command = [sys.executable, "-m", "elekloader.patch", "--stock", stock["image"]]
    for artifact in artifacts:
        command += ["--mod", artifact]
    logs.append(cpu.command([*command, "--out", image, "--version", "X0ZR"]))
    (FOLDER / "build.log").write_text("\n".join(logs))
    names = {key: int(value, 0) for key, value in json.loads(
        image.with_suffix(".syx.map.json").read_text()).items()}
    return image, names, stock


def observe(machine, names, at):
    """Instrument only this probe's four C callbacks; fail closed on ctypes errors."""
    from unicorn import UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
    from unicorn.m68k_const import UC_M68K_REG_A7

    uc = machine.uc
    state = dict(active=None, current=None, traces=[], violations=[], reads=0)
    returns = set()
    objects = [("probe_count", 24), ("probe_pending", 4), ("probe_capture_block", 4),
               ("probe_pre_value", 4), ("probe_copy", FRAME_BYTES)]
    owned_state = [(names[name], names[name] + length) for name, length in objects]
    word = lambda address: int.from_bytes(uc.mem_read(address, 4), "big")
    raw = lambda pointer: int.from_bytes(uc.mem_read(pointer + 2 * (79 * 3 + 27), 2), "big")

    def checked(function):
        def callback(*args):
            try:
                function(*args)
            except Exception as error:
                state["violations"].append(str(error))
                uc.emu_stop()
        return callback

    def returned(_uc, address, _size, _data):
        active = state["active"]
        if active is None or active["return"] != address:
            return
        if active.get("pointer"):
            if bytes(uc.mem_read(active["pointer"], FRAME_BYTES)) != active["frame"]:
                raise AssertionError("DN observer wrote the parameter frame")
            if bytes(uc.mem_read(names["fw_voices"], 1024)) != active["audio"]:
                raise AssertionError("DN observer wrote stock voice audio")
            if bytes(uc.mem_read(names["probe_copy"], FRAME_BYTES)) != active["frame"]:
                raise AssertionError("DN observer copy differs from the current final frame")
        if active["name"] in ("probe_in", "probe_late", "probe_out") and word(names["probe_pending"]):
            raise AssertionError("DN observer did not invalidate its frame pointer")
        state["active"] = None

    def entered(name):
        def callback(_uc, _address, _size, _data):
            if state["active"]:
                raise AssertionError("nested DN observer callback")
            sp = uc.reg_read(UC_M68K_REG_A7)
            ret = word(sp)
            if ret not in returns:
                at(ret, checked(returned))
                returns.add(ret)
            active = state["active"] = dict(name=name, stack=sp, **{"return": ret})
            if name == "probe_in":
                state["current"] = dict(block=word(names["probe_count"]) + 1, order=["in"])
                state["traces"].append(state["current"])
                return
            current = state["current"]
            if current is None:
                raise AssertionError("DN callback preceded render entry")
            current["order"].append({"probe_pre": "pre", "probe_late": "late", "probe_out": "out"}[name])
            if name == "probe_pre":
                pointer = word(sp + 4)
                if pointer not in POINTERS:
                    raise AssertionError("DN parameter callback supplied an unexpected SRAM bank")
                current.update(pointer=pointer, pre=raw(pointer))
            elif name == "probe_late":
                pointer = word(names["probe_pending"])
                if pointer and (pointer != current.get("pointer") or word(names["probe_capture_block"]) != current["block"]):
                    raise AssertionError("DN observer attempted to read a stale/different bank")
                current.update(late_pointer=pointer, late=raw(pointer) if pointer else None)
                if pointer:
                    active.update(pointer=pointer, frame=bytes(uc.mem_read(pointer, FRAME_BYTES)),
                                  audio=bytes(uc.mem_read(names["fw_voices"], 1024)))
        return callback

    for name in ("probe_in", "probe_pre", "probe_late", "probe_out"):
        at(names[name], checked(entered(name)))

    def stage(name):
        def callback(_uc, _address, _size, _data):
            current = state["current"]
            if current is not None:
                current["order"].append(name)
                if name == "final":
                    current["final"] = raw(current["pointer"])
        return callback

    for address, name in ((0x4009C078, "controller"), (0x400FED62, "lfo"), (0x4009DF38, "final")):
        at(address, checked(stage(name)))

    def written(_uc, _access, address, size, _value, _data):
        active = state["active"]
        if active is None:
            return
        owned = [*owned_state, (active["stack"] - 2048, active["stack"])]
        if not any(first <= address and address + size <= last for first, last in owned):
            raise AssertionError(f"DN observer wrote outside its state/stack: {address:#x}")

    def read(_uc, _access, address, size, _value, _data):
        active = state["active"]
        if active is None:
            return
        current = state["current"]
        pointer = current.get("pointer") if current else None
        owned = [*owned_state, (active["stack"] - 2048, active["stack"] + 8)]
        if pointer is not None and active["name"] in ("probe_pre", "probe_late"):
            owned.append((pointer, pointer + FRAME_BYTES))
            if pointer <= address and address + size <= pointer + FRAME_BYTES:
                state["reads"] += 1
        if not any(first <= address and address + size <= last for first, last in owned):
            raise AssertionError(f"DN observer read outside state/stack/current frame: {address:#x}")

    uc.hook_add(UC_HOOK_MEM_WRITE, checked(written))
    uc.hook_add(UC_HOOK_MEM_READ, checked(read))
    return state


def bounded(image_path, names, stock):
    from elekloader import formats
    harness = cpu.require_module("emu.harness", "digiemu")
    from unicorn import UC_HOOK_CODE
    from unicorn import m68k_const as regs

    _, device, _ = formats.load(Path(stock["image"]))
    image = formats.main_image(formats.parse(image_path, device), device)
    machine = harness.Machine()
    try:
        machine.load(image, device.main_load)
        machine.install_isa_patches_scoped(image, device.main_load)
        for address in (0x47000000, 0x80000000, 0x43400000, 0x431F2928,
                        names["fw_lfo_state"], names["__run_start"]):
            machine.ensure(address)
        uc = machine.uc
        offset = names["__run_load"] - device.main_load
        run_bytes = 4 * names["__run_words"]
        if offset < 0 or offset + run_bytes > len(image):
            raise ValueError("linked DN run image exceeds its firmware extent")
        uc.mem_write(names["__run_start"], image[offset:offset + run_bytes])
        uc.mem_write(names["__bss_start"], bytes(4 * names["__bss_words"]))
        uc.reg_write(regs.UC_M68K_REG_SR, 0x2700)
        state = observe(machine, names, lambda address, fn: uc.hook_add(UC_HOOK_CODE, fn, begin=address, end=address))

        def execute(first, last, count=LIMIT):
            uc.emu_start(first, last, count=count)
            if state["violations"] or uc.reg_read(regs.UC_M68K_REG_PC) != last:
                raise AssertionError("DN native stage stopped/violated its bound: " + str(state["violations"]))

        def native(address, args):
            harness.call(machine, address, args, ret_magic=RETURN, stack_top=STACK, limit=LIMIT)
            if state["violations"] or uc.reg_read(regs.UC_M68K_REG_PC) != RETURN:
                raise AssertionError("DN native call stopped/violated its bound: " + str(state["violations"]))

        # All addresses below are reviewed 1.44 test fixtures, never mod exports.
        target = names["fw_voice_params"]
        voice_base = target + 18 + 158 * 3
        for voice in range(8):
            uc.mem_write(0x80005444 + 20 * voice, struct.pack(">I", 0x43400000 + 512 * voice))
        uc.mem_write(names["fw_voice_track"], bytes(32))
        settings = {1: 0x5000, 2: 0, 4: 27 << 8, 5: 2 << 8, 6: 64 << 8,
                    7: 1 << 8, 8: 72 << 8, 12: 0, 16: 64 << 8}
        for slot, value in {**settings, 27: 12345}.items():
            uc.mem_write(voice_base + 2 * slot, struct.pack(">h", value))
        uc.mem_write(target + 1449 + 148 * 3, struct.pack(">4I", (0x1000 << 16) | 27, 0, 0, 0))
        uc.mem_write(0x431F2928 + 2 * 3, struct.pack(">h", 0x3F80))
        uc.mem_write(names["fw_lfo_state"], bytes(8 * 80))
        results = []
        for block in range(6):
            bank = 0x80001FA4 + 0xA90 * (block % 2)
            frame = bank + 80
            word = lambda: int.from_bytes(uc.mem_read(frame + 18 + 158 * 3 + 54, 2), "big")
            uc.reg_write(regs.UC_M68K_REG_A6, 0x470E0000)
            native(names["core_render_in"], [])
            execute(0x4009D1DE, 0x4009D1E4, 1)  # stock MACSR=0x20
            native(0x4009BF86, [frame, target])
            pre = word()
            # Explicit settled LFO configuration injection, not native UI delivery.
            for slot, value in settings.items():
                uc.mem_write(frame + 18 + 158 * 3 + 2 * slot, struct.pack(">h", value))
            native(names["core_render_params"], [frame])
            controller = word()
            native(0x400FED62, [frame, 14400, 8 if block == 0 else 0, 0, 0xFFFFFFFF, 0xFFFFFFFF])
            lfo = word()
            uc.reg_write(regs.UC_M68K_REG_A6, 0x470E0000)
            uc.reg_write(regs.UC_M68K_REG_A2, bank)
            uc.reg_write(regs.UC_M68K_REG_D6, 0)
            uc.mem_write(0x470E0000 - 108, struct.pack(">I", frame))
            uc.reg_write(regs.UC_M68K_REG_A7, STACK)
            execute(0x4009DE1A, 0x4009DF52)  # remaining pitch/pan/gain and gain-vector helper
            final = word()
            previous_copy = bytes(uc.mem_read(names["probe_copy"], FRAME_BYTES))
            if block == 2:
                uc.mem_write(names["probe_pending"], bytes(4))  # missing-capture fault
            native(names["core_render_voices"], [frame, 0, 0])
            if block == 2 and bytes(uc.mem_read(names["probe_copy"], FRAME_BYTES)) != previous_copy:
                raise AssertionError("DN missing-capture callback changed its previous copy")
            uc.reg_write(regs.UC_M68K_REG_A6, 0x470E0000)
            native(names["core_render_out"], [])
            results.append(dict(block=block, pre=pre, controller=controller, lfo=lfo, final=final,
                                target=int.from_bytes(uc.mem_read(voice_base + 54, 2), "big")))
        validate_trace(state["traces"])
        for key, expected in (("pre", [370, 730, 1078, 1416, 1744, 2062]),
                              ("controller", [2402, 2762, 3110, 3448, 3776, 4094]),
                              ("final", [2402, 2761, 3109, 3447, 3775, 4093]), ("target", [12345] * 6)):
            if [row[key] for row in results] != expected:
                raise AssertionError("native DN " + key + " trace diverged")
        counters = list(struct.unpack(">6I", uc.mem_read(names["probe_count"], 24)))
        if counters != [6, 6, 5, 1, 6, 0] or state["reads"] != 6 + 5 * 632:
            raise AssertionError("DN missing-capture/read-extent guard did not match")
        return dict(mode="bounded native calls with injected state", results=results, traces=state["traces"],
                    counters=counters, guarded_frame_reads=state["reads"], frame_extent_bytes=FRAME_BYTES,
                    injection="target; controller mapping/value; settled LFO settings; zeroed LFO/voice state; block 2 capture cleared",
                    instructions_per_call_or_stage=LIMIT)
    finally:
        machine.close()


def full_os(image, names):
    cpu.require_module("emu.session", "digiemu")
    from emu.bootstrap import Cancelled, first_run
    from emu.fwcheck import prepare
    from emu.longrun import never_fake_set_posts
    from emu.session import Session

    started, session = time.monotonic(), None
    with (FOLDER / "boot.log").open("w") as log, contextlib.redirect_stdout(log):
        paths, device = prepare(str(image), str(FOLDER / "cache"))
        if device.short != "dn1":
            raise ValueError("DN observer firmware resolved to a different device")
        try:
            snap = first_run(paths, cancel=lambda: time.monotonic() - started > 90)
        except Cancelled as error:
            raise cpu.Unavailable("DN bootstrap exceeded its 90-second wall bound") from error
        try:
            session = Session(snap, paths.syx, hle=False)  # standard pattern; explicitly non-strict
            never_fake_set_posts(session.m, session.ev, session.profile.set_post)
            state = observe(session.m, names, session.at)
            session.run_ms(40)
            if session.halted or state["active"] or state["violations"]:
                raise AssertionError("DN Session/observer stopped: " + str(session.halted or state["violations"]))
            validate_trace(state["traces"])
            counters = list(struct.unpack(">6I", session.m.uc.mem_read(names["probe_count"], 24)))
            n = len(state["traces"])
            if n < 2 or counters != [n, n, n, 0, n, 0] or state["reads"] != n * 633:
                raise AssertionError("DN full-OS event/read/invalidation counters diverged")
            return dict(mode="full OS standard Session", configuration="hle=False, strict=None; no DDR override",
                        session_ms=40, bootstrap_wall_limit_seconds=90, traces=state["traces"], counters=counters,
                        guarded_frame_reads=state["reads"], frame_extent_bytes=FRAME_BYTES,
                        strict_model=dict(status="unavailable", reason=STRICT_LIMIT))
        finally:
            if session is not None:
                session.close()


def verify(use_full_os=False):
    cpu.require_module("emu.harness", "digiemu")
    image, names, stock = build()
    result = full_os(image, names) if use_full_os else bounded(image, names, stock)
    result.update(kind="DN existing-event observer prototype", stock=stock,
                  elekloader_revision=stock["sdk_revision"], emulator_revision=cpu.revision(ROOT / "vendor/digiemu"),
                  project_revision=cpu.revision(ROOT), source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  observer_sha256=hashlib.sha256(DRIVER.encode()).hexdigest(),
                  firmware_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
                  production_adapter_consumption=False, process_wall_limit_seconds=150,
                  unqualified=["production adapter delivery", "locks and native allocation/lifecycle",
                               "UI/MIDI control sources", "DSP two-block audio timing", "physical deadlines/kick fidelity"])
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full-os", action="store_true")
    args = parser.parse_args(argv)
    signal.alarm(150)
    try:
        result = verify(args.full_os)
        report = dict(status="passed", **result)
        name = "full-os-report.json" if args.full_os else "bounded-report.json"
        (FOLDER / name).write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))
        return 0
    except cpu.Unavailable as error:
        print(json.dumps(dict(status="unavailable", reason=str(error))))
        return 77
    except (AssertionError, RuntimeError, ValueError, OSError) as error:
        print(json.dumps(dict(status="failed", reason=str(error))))
        return 1
    finally:
        signal.alarm(0)


if __name__ == "__main__":
    sys.exit(main())
