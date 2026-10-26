"""Native DT panel PLAY -> OS START -> C capture -> ASM observation.

The generated test subscriber owns no machine ID and never replaces stock audio.
Run native JIT execution outside restricted sandboxes on hosts that require it.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import time

from . import cpu, digitakt_adapter, firmware

ROOT = cpu.ROOT
CAPACITY, RECORD_BYTES = 64, 184
GUARDS = (0x13579BDF, 0x2468ACE0)
DRIVER = r'''
#include <stdint.h>
#include "digitakt-mk1/core3.h"
#include "machines/digitakt/adapter.h"
extern void x0z_diagnostic(int32_t *, int32_t);
struct observation {
    uint32_t valid, calls;
    struct x0z_dt_snapshot snapshot;
    enum x0z_control control;
    struct x0z_position position;
    int32_t output[32];
};
struct record { uint32_t block, before; struct observation observation; uint32_t after; };
struct record transport_records[64];
uint32_t transport_counters[3]; /* callbacks, START records, overflow */
static void receive(void *context, uint32_t track, enum x0z_control control,
                    struct x0z_position position)
{
    struct observation *o = context;
    (void)track;
    ++o->calls;
    o->control = control;
    o->position = position;
    x0z_diagnostic(o->output, (int32_t)(position.numerator << 16));
}
void transport_render(int32_t *blocks)
{
    static const struct x0z_dt_binding binding = {0, X0Z_DECAY, 0, 32512};
    (void)blocks;
    ++transport_counters[0];
    uint32_t starts = fw_voice_start;
    for (uint32_t track = 0; track < 8; ++track) {
        if (!(starts & (1u << track))) continue;
        if (transport_counters[1] >= 64) { ++transport_counters[2]; continue; }
        struct record *r = &transport_records[transport_counters[1]++];
        r->block = transport_counters[0];
        r->before = 0x13579bdf;
        r->after = 0x2468ace0;
        r->observation.calls = 0;
        r->observation.valid = x0z_dt_capture(track, X0Z_808, &binding, 1,
            &r->observation.snapshot, receive, &r->observation);
    }
}
'''


def decode_record(raw: bytes) -> dict:
    if len(raw) != RECORD_BYTES:
        raise ValueError("transport record must contain exactly 184 bytes")
    block, before = struct.unpack_from(">2I", raw)
    after = struct.unpack_from(">I", raw, RECORD_BYTES - 4)[0]
    if (before, after) != GUARDS:
        raise AssertionError("diagnostic output crossed a buffer guard")
    return dict(block=block, **digitakt_adapter.decode_observation(raw[8:-4]))


def build(folder: Path) -> tuple[Path, dict]:
    entries, revision = firmware.baseline()
    stock = firmware.verify_entry(entries["digitakt-mk1"], ROOT / "firmware", revision)
    if stock["version"] != "1.54":
        raise ValueError("transport probe requires the reviewed DT OS 1.54")
    mod = folder / "mod"
    mod.mkdir(parents=True, exist_ok=True)
    (mod / "driver.c").write_text(DRIVER)
    descriptor = dict(id="x0z-transport-probe", version="0.0", title="Transport probe",
                      device="digitakt-mk1", os="1.54", license="GPL-2.0-or-later",
                      sources=["driver.c", str(ROOT / "machines/digitakt/adapter.c"),
                               str(ROOT / "src/controls.c"), str(ROOT / "targets/coldfire/diagnostic.s")],
                      cflags=["-I", str(ROOT), "-I", str(ROOT / "include")],
                      subscribe=[dict(event="ev_render_voices", fn="transport_render", order=20)],
                      requires=["core", "machine-pages"])
    (mod / "mod.json").write_text(json.dumps(descriptor, indent=2) + "\n")
    cpu.command([sys.executable, "-m", "elekloader.sdk.build", mod,
                 "--stock", stock["image"], "--out", folder / "deps"])
    image = folder / "transport.syx"
    artifacts = [ROOT / "out/dt/deps/core-4.1-os1.54.elemod",
                 ROOT / "out/dt/deps/machine-pages-1.5-os1.54.elemod",
                 folder / "deps/x0z-transport-probe-0.0.elemod"]
    command = [sys.executable, "-m", "elekloader.patch", "--stock", stock["image"]]
    for artifact in artifacts:
        command += ["--mod", artifact]
    cpu.command([*command, "--out", image, "--version", "X0ZT"])
    return image, stock


def verify() -> dict:
    cpu.require_module("emu.session", "digiemu")
    from emu.bootstrap import first_run
    from emu.fwcheck import prepare
    from emu.longrun import never_fake_set_posts
    from emu.session import Session
    from unicorn import UC_HOOK_MEM_WRITE
    from unicorn.m68k_const import UC_M68K_REG_A7

    folder = ROOT / "out/dt/transport"
    folder.mkdir(parents=True, exist_ok=True)
    image, stock = build(folder)
    symbols = json.loads(Path(str(image) + ".map.json").read_text())
    address = lambda name: int(symbols[name], 0)
    started = time.monotonic()
    session = None
    with (folder / "boot.log").open("w") as log, contextlib.redirect_stdout(log):
        paths, device = prepare(str(image), str(folder / "cache"))
        if device.short != "dt1":
            raise AssertionError("transport image is not a Digitakt")
        snap = first_run(paths, cancel=lambda: time.monotonic() - started > 120)
        try:
            session = Session(snap, paths.syx, hle=False)
            never_fake_set_posts(session.m, session.ev, session.profile.set_post)
            uc = session.m.uc
            counters, records = address("transport_counters"), address("transport_records")
            read32 = lambda at: int.from_bytes(uc.mem_read(at, 4), "big")
            initial_blocks = read32(counters)
            if read32(counters + 4) or read32(counters + 8):
                raise AssertionError("boot unexpectedly triggered/overflowed the observation log")
            active = None
            returns, expected, observed, violations = set(), [], [], []
            writes, callbacks = 0, 0

            def checked_hook(fn):
                # ctypes hook exceptions are otherwise printed and ignored.
                def checked(*args):
                    try:
                        fn(*args)
                    except Exception as error:
                        violations.append(str(error))
                        uc.emu_stop()
                return checked

            def returned(uc_, at, size, data):
                nonlocal active, callbacks
                if active is None or at != active["return"]:
                    return
                if bytes(uc.mem_read(address("fw_track_blocks"), 1024)) != active["audio"]:
                    raise AssertionError("observer changed unrelated stock track audio")
                if read32(counters + 8):
                    raise AssertionError("observation log overflowed")
                count = read32(counters + 4)
                for index in range(active["count"], count):
                    record = decode_record(bytes(uc.mem_read(records + index * RECORD_BYTES, RECORD_BYTES)))
                    exp = expected[len(observed)]
                    for key, value in exp["values"].items():
                        if record[key] != value:
                            raise AssertionError("native transport mismatch: " + key)
                    if record["output_q31"] != [record["numerator"] << 16] * 32:
                        raise AssertionError("actual diagnostic ASM output differs from delivered value")
                    observed.append(dict(chunk_ms=exp["chunk_ms"], render_block=record["block"],
                                         track=record["track"], native_start=record["native_start"],
                                         note=record["note"], numerator=record["numerator"]))
                active = None
                callbacks += 1

            def entered(uc_, at, size, data):
                nonlocal active
                if active is not None:
                    raise AssertionError("nested observer callback")
                sp = uc.reg_read(UC_M68K_REG_A7)
                ret = read32(sp)
                if ret not in returns:
                    session.at(ret, checked_hook(returned))
                    returns.add(ret)
                starts = read32(address("fw_voice_start"))
                for track in range(8):
                    if starts & (1 << track):
                        raw = int.from_bytes(uc.mem_read(address("fw_voice_params") + 106 * track, 2), "big", signed=True)
                        expected.append(dict(chunk_ms=session.ms, values=dict(
                            valid=1, calls=1, track=track, native_start=1, control=1,
                            note=int.from_bytes(uc.mem_read(address("fw_voice_note") + 4 * track, 4), "big", signed=True),
                            velocity=int.from_bytes(uc.mem_read(address("fw_voice_vel") + 2 * track, 2), "big"),
                            amp_phase=int.from_bytes(uc.mem_read(address("fw_amp_env") + 12 * track, 4), "big", signed=True),
                            amp_level=int.from_bytes(uc.mem_read(address("fw_amp_env") + 12 * track + 4, 4), "big", signed=True),
                            numerator=raw, denominator=32512)))
                active = dict(stack=sp, count=read32(counters + 4),
                              audio=bytes(uc.mem_read(address("fw_track_blocks"), 1024)))
                active["return"] = ret

            def written(uc_, access, at, size, value, data):
                nonlocal writes
                if active is None:
                    return
                writes += 1
                allowed = ((counters, counters + 12), (records, records + CAPACITY * RECORD_BYTES),
                           (active["stack"] - 4096, active["stack"]))
                if not any(lo <= at and at + size <= hi for lo, hi in allowed):
                    violations.append(dict(address=hex(at), bytes=size))

            session.at(address("transport_render"), checked_hook(entered))
            uc.hook_add(UC_HOOK_MEM_WRITE, written)
            session.run_ms(100)
            if violations:
                raise AssertionError(str(violations))
            idle_records = len(observed)
            event = dict(requested="panel PLAY", chunk_ms=session.ms,
                         render_block=read32(counters))
            session.tap(session.code("PLAY"), hold_ms=40, after_ms=100)
            session.run_ms(300)
            session.tap(session.code("STOP"), hold_ms=40, after_ms=100)
            if session.halted or active is not None or violations:
                raise AssertionError("native callback halted or exceeded write ownership: " + str(violations))
            if idle_records or not observed or len(expected) != len(observed):
                raise AssertionError("panel PLAY did not deliver native START snapshots to C and ASM")
            if observed[0]["render_block"] <= event["render_block"]:
                raise AssertionError("recorded START preceded requested PLAY")
            report = dict(status="passed", kind="DT-native-panel-event-observer",
                          stock=stock, firmware_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
                          digiemu_revision=cpu.revision(ROOT / "vendor/digiemu"),
                          project_revision=cpu.revision(ROOT), input_event=event,
                          compiled_sources=json.loads((folder / "deps/x0z-transport-probe-0.0.elemod").read_text())["build"]["sources"],
                          delivered=observed, callbacks=callbacks, guest_writes_checked=writes,
                          render_blocks=read32(counters) - initial_blocks,
                          emulated_ms=session.ms, pcm_bytes=len(session.pcm),
                          wall_seconds=time.monotonic() - started,
                          timing="chunk_ms is the Session chunk start; render_block identifies the native callback; no sample onset claim",
                          checked=["native panel PLAY dispatch", "native START and note at render event",
                                   "production C adapter", "actual assembled output stores",
                                   "exact delivered value", "output guards", "callback write ownership",
                                   "stock track audio unchanged across every observer callback"],
                          unqualified=["machine selection/registration", "replacement audio routing",
                                       "MIDI notes", "parameter locks/live edits", "retrigger/note-off policy",
                                       "sample-accurate onset", "hardware and kick fidelity"])
        finally:
            if session is not None:
                session.close()
    (folder / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> int:
    try:
        report = verify()
    except cpu.Unavailable as error:
        print(json.dumps(dict(status="unavailable", reason=str(error))))
        return 77
    except (AssertionError, OSError, RuntimeError, ValueError) as error:
        print(json.dumps(dict(status="failed", reason=str(error))))
        return 1
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
