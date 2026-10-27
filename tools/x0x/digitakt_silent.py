"""Check the DT silent mod with host fakes, actual ASM, or a full-OS smoke."""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import time

from . import cpu, firmware
from .digitakt_adapter import BASE, STACK, STOP

ROOT = cpu.ROOT
SOURCE = ROOT / "machines/digitakt/machine.c"
FOLDER = ROOT / "out/dt/silent"
FAKES = '''#include <stdint.h>
volatile uint8_t fw_render_machine[8];
volatile uint32_t fw_voice_start;
const char cm_ui_v3[] = "test";
int32_t values[8][8];
uint32_t reads[8];
int32_t blocks[256];
int32_t cm_src_value(int32_t track, int32_t parameter)
{ reads[track] |= 1u << parameter; return values[track][parameter]; }
'''


def host():
    FOLDER.mkdir(parents=True, exist_ok=True)
    binary = FOLDER / "host"
    cpu.command([os.environ.get("CC", "clang"), "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
                 "-I", ROOT / "vendor/elekloader/elekloader/sdk/include", SOURCE,
                 ROOT / "tests/ui/test_digitakt_silent.c", "-o", binary])
    cpu.command([binary])
    return dict(status="passed", scope="host declarations and dispatch with native/DSP fakes")


def component():
    harness = cpu.require_module("emu.harness", "digiemu")
    from unicorn import UC_HOOK_MEM_WRITE
    from unicorn.m68k_const import UC_M68K_REG_PC, UC_M68K_REG_SR

    FOLDER.mkdir(parents=True, exist_ok=True)
    fakes = FOLDER / "fakes.c"
    fakes.write_text(FAKES)
    linker = FOLDER / "component.ld"
    linker.write_text("SECTIONS { . = 0x47000000; .text : { *(.text*) } .rodata : { *(.rodata*) } .data : { *(.data*) } .bss : { *(.bss*) *(COMMON) } }")
    prefix = os.environ.get("ELEKLOADER_CROSS", "m68k-elf-")
    objects = []
    for source in (SOURCE, fakes, ROOT / "targets/coldfire/selector.s", ROOT / "targets/coldfire/silence.s"):
        obj = FOLDER / (source.stem + ".o")
        cpu.command([prefix + "gcc", "-mcpu=54455", "-O2", "-ffreestanding", "-fno-builtin",
                     "-Wall", "-Wextra", "-Werror", "-I", ROOT / "vendor/elekloader/elekloader/sdk/include",
                     "-c", source, "-o", obj])
        objects.append(obj)
    elf, binary = FOLDER / "component.elf", FOLDER / "component.bin"
    cpu.command([prefix + "ld", "-T", linker, "-e", "x0x_dt_render", *objects, "-o", elf])
    cpu.command([prefix + "objcopy", "-O", "binary", elf, binary])
    symbols = {words[2]: int(words[0], 16) for line in cpu.command([prefix + "nm", elf]).splitlines()
               if len(words := line.split()) == 3}
    machine = harness.Machine()
    machine.ensure(BASE)
    uc = machine.uc
    uc.mem_write(BASE, binary.read_bytes())
    uc.reg_write(UC_M68K_REG_SR, 0x2700)
    address = symbols.__getitem__
    active = [0] * 8
    active[0] = active[7] = 80
    uc.mem_write(address("fw_render_machine"), bytes(active))
    expected = [0] * 24
    traces = []
    # Same installed registration, two simultaneous models, pending edit and slot reuse.
    for label, starts, model0, model7 in (
            ("before START", 0, 0, 32512), ("mixed START", 129, 0, 32512),
            ("pending edit", 0, 32512, 0), ("invalid control", 1, 32512, 0),
            ("switch track 0", 1, 32512, 0),
            ("leave track 7", 0, 32512, 0), ("return without START", 0, 32512, 0),
            ("fresh track 7", 128, 32512, 0)):
        active[7] = 0 if label == "leave track 7" else 80
        uc.mem_write(address("fw_render_machine"), bytes(active))
        uc.mem_write(address("fw_voice_start"), struct.pack(">I", starts))
        for track, model in ((0, model0), (7, model7)):
            tone_tune = 32767 if label == "invalid control" else 16384
            uc.mem_write(address("values") + 32 * track, struct.pack(">8i", tone_tune, 12345, 16384, -1, -1, model, -1, -1))
        uc.mem_write(address("reads"), bytes(32))
        original = struct.pack(">256i", *range(1, 257))
        uc.mem_write(address("blocks"), original)
        allowed = [(address("selection"), address("selection") + 96),
                   (address("reads"), address("reads") + 32), (STACK - 2048, STACK)]
        allowed += [(address("blocks") + 128 * t, address("blocks") + 128 * (t + 1))
                    for t in range(8) if active[t] == 80]
        illegal = []
        def written(_uc, _access, at, size, _value, _data):
            if not any(lo <= at and at + size <= hi for lo, hi in allowed):
                illegal.append((at, size))
        hook = uc.hook_add(UC_HOOK_MEM_WRITE, written)
        try:
            harness.call(machine, address("x0x_dt_render"), [address("blocks")],
                         ret_magic=STOP, stack_top=STACK, limit=10000)
        finally:
            uc.hook_del(hook)
        assert uc.reg_read(UC_M68K_REG_PC) == STOP and not illegal, (label, illegal)
        for track in range(8):
            live = active[track] == 80
            raw = bytes(uc.mem_read(address("blocks") + track * 128, 128))
            assert raw == (bytes(128) if live else original[track * 128:(track + 1) * 128]), label
            assert int.from_bytes(uc.mem_read(address("reads") + 4 * track, 4), "big") == (0x27 if live else 0), label
            if not live:
                expected[3 * track:3 * track + 3] = [0, 0, 0]
            elif starts & (1 << track) and label != "invalid control":
                expected[3 * track:3 * track + 3] = [1, int((model0 if track == 0 else model7) >= 16384), 0]
        state = list(struct.unpack(">24I", uc.mem_read(address("selection"), 96)))
        assert state == expected, (label, state, expected)
        traces.append(label)
    report = dict(status="passed", scope="compiled DT C and actual ColdFire selector/silent ASM; native services are fakes",
                  scenarios=traces, unqualified=["OS selection/defaults", "native p-lock/LFO routing", "save/reload", "full-OS replacement audio"])
    (FOLDER / "component-report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def full_os():
    """Native panel/UART smoke using the approved x0x-only default correction."""
    cpu.require_module("emu.session", "digiemu")
    from emu import panel
    from emu.bootstrap import first_run
    from emu.fwcheck import prepare
    from emu.harness import call
    from emu.longrun import never_fake_set_posts
    from emu.midi import MidiIn
    from emu.session import Session
    from unicorn.m68k_const import UC_M68K_REG_A7, UC_M68K_REG_PC

    FOLDER.mkdir(parents=True, exist_ok=True)
    entries, revision = firmware.baseline()
    stock = firmware.verify_entry(entries["digitakt-mk1"], ROOT / "firmware", revision)
    companion = FOLDER / "machine-pages"
    original = ROOT / "vendor/elekloader/mods/machine-pages"
    patch = SOURCE.parent / "legacy-defaults.patch"
    shutil.copytree(original, companion, dirs_exist_ok=True)
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    compatibility = dict(sdk_revision=revision, patch=str(patch.relative_to(ROOT)),
                         patch_sha256=digest(patch),
                         base_sources={name: digest(original / name) for name in ("pages.c", "params.c")})
    cpu.command(["patch", "-p1", "--batch", "--forward", "--fuzz=0", "-i", patch], cwd=companion)
    compatibility["patched_sources"] = {name: digest(companion / name) for name in ("pages.c", "params.c")}
    logs, artifacts = [], []
    for source in (ROOT / "vendor/elekloader/mods/core", companion, SOURCE.parent):
        meta = json.loads((source / "mod.json").read_text())
        logs.append(cpu.command([sys.executable, "-m", "elekloader.sdk.build", source,
                                 "--stock", stock["image"], "--out", FOLDER / "deps"]))
        suffix = "-os" + stock["version"] if meta["os"] != stock["version"] else ""
        artifacts.append(FOLDER / "deps" / f'{meta["id"]}-{meta["version"]}{suffix}.elemod')
    image = FOLDER / "x0x.syx"
    command = [sys.executable, "-m", "elekloader.patch", "--stock", stock["image"]]
    for artifact in artifacts:
        command += ["--mod", artifact]
    logs.append(cpu.command([*command, "--out", image, "--version", "X0X0"]))
    (FOLDER / "build.log").write_text("\n".join(logs))
    names = {k: int(v, 0) for k, v in json.loads(Path(str(image) + ".map.json").read_text()).items()}
    report = dict(status="failed", scope="standard full-OS digiemu Session; native panel and UART",
                  stock=stock, firmware_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
                  digiemu_revision=cpu.revision(ROOT / "vendor/digiemu"),
                  companion_compatibility=compatibility,
                  unqualified=["p-lock/LFO delivery", "save/reload", "strict-model qualification", "kick audio"])
    session = None
    try:
        with (FOLDER / "native-boot.log").open("w") as log, contextlib.redirect_stdout(log):
            paths, device = prepare(str(image), str(FOLDER / "cache"))
            assert device.short == "dt1"
            os.environ.update(paths.env())
            start = time.monotonic()
            snap = first_run(paths, cancel=lambda: time.monotonic() - start > 120)
            session = Session(snap, paths.syx, hle=False)
            never_fake_set_posts(session.m, session.ev, session.profile.set_post)
        uc, midi = session.m.uc, MidiIn()
        state = dict(active=None, callbacks=0, selected_callbacks=0, violations=[], controls=[])
        returns = set()
        def checked(fn):
            def run(*args):
                try:
                    fn(*args)
                except Exception as error:
                    state["violations"].append(str(error))
                    uc.emu_stop()
            return run
        def returned(_uc, at, _size, _data):
            active = state["active"]
            if active is None or at != active["return"]:
                return
            after = bytes(uc.mem_read(names["fw_track_blocks"], 1024))
            for track, machine in enumerate(active["machines"]):
                lo, hi = 128 * track, 128 * (track + 1)
                assert after[lo:hi] == (bytes(128) if machine == 80 else active["before"][lo:hi]), "callback changed an unowned block or failed to silence x0x"
            state["callbacks"] += 1
            state["selected_callbacks"] += int(80 in active["machines"])
            if active["machines"][0] == 80:
                state["controls"].append(active["controls"])
            state["active"] = None
        def entered(_uc, _at, _size, _data):
            assert state["active"] is None, "nested callback"
            ret = int.from_bytes(uc.mem_read(uc.reg_read(UC_M68K_REG_A7), 4), "big")
            if ret not in returns:
                session.at(ret, checked(returned))
                returns.add(ret)
            state["active"] = dict(before=bytes(uc.mem_read(names["fw_track_blocks"], 1024)),
                                   machines=bytes(uc.mem_read(names["fw_render_machine"], 8)),
                                   controls=list(struct.unpack(">8h", uc.mem_read(names["fw_voice_params"], 16))))
            state["active"]["return"] = ret
        session.at(names["x0x_dt_render"], checked(entered))
        def wait(ms=80):
            session.run_ms(ms)
            assert not session.halted and not state["violations"], (session.halted, state["violations"])
        def tap(key):
            session.tap(session.code(key), hold_ms=40, after_ms=80)
            assert not session.halted and not state["violations"], (session.halted, state["violations"])
        def chord(modifier, key):
            session.press(session.code(modifier)); wait(40)
            try:
                tap(key)
            finally:
                session.release(session.code(modifier))
            wait(40)
        def stored(track=0):
            sound = int.from_bytes(uc.mem_read(names["fw_kit"], 4), "big") + 0x20 + 162 * track
            return sound, list(struct.unpack(">53h", uc.mem_read(sound + 20, 106)))
        def screen(name):
            panel.write_png(session.frames[-1][1], str(FOLDER / (name + ".png")), scale=4)
        def send(data):
            midi.put(bytes(data))
            for _ in range(1000):
                if midi.delivered == midi.received:
                    break
                if midi.deliver(session.m):
                    session.pc = uc.reg_read(UC_M68K_REG_PC)
                wait(5)
            else:
                raise AssertionError("native MIDI did not drain")
            wait()
        def selected(track=0):
            return list(struct.unpack(">3I", uc.mem_read(names["selection"] + 12 * track, 12)))
        wait()
        session.press(session.code("FUNC")); wait(40)
        tap("SRC"); session.release(session.code("FUNC")); wait(40)
        for _ in range(4):
            tap("DOWN")
        screen("machine-menu")
        tap("YES")
        sound, values = stored()
        assert bytes(uc.mem_read(sound + 126, 1)) == bytes([80]), "native menu did not select x0x"
        screen("default-controls")
        report["defaults"] = dict(actual=[values[i] for i in (17, 18, 19, 22)],
                                  expected=[16384, 16384, 16384, 0])
        report["defaults"]["status"] = "passed" if report["defaults"]["actual"] == report["defaults"]["expected"] else "failed"
        # Exercise control delivery even when the independent defaults check fails.
        send([0xb0, 16, 64, 0xb0, 17, 64, 0xb0, 18, 64, 0xb0, 21, 0])
        send([0x90, 60, 100]); report["808"] = selected()
        send([0xb0, 21, 127]); report["pending"] = selected()
        send([0x80, 60, 0]); send([0x90, 60, 100]); report["909"] = selected()
        screen("controls-909")
        assert report["808"] == [1, 0, 0] and report["pending"] == [1, 0, 0] and report["909"] == [1, 1, 0], report
        values = stored()[1]
        assert [values[i] for i in (17, 18, 19, 22)] == [16384, 16384, 16384, 32512]
        # Use the native destination list and depth control, not injected LFO state.
        tap("LFO")
        for _ in range(150):
            if stored()[1][4] >= 17 << 8:
                break
            session.turn(session.encoder("D"), 2, after_ms=80); tap("YES")
        report["lfo_destination"] = stored()[1][4]
        assert report["lfo_destination"] == 17 << 8, report
        tap("SRC")
        send([0xb0, 109, 127]); send([0x90, 60, 100])
        start = len(state["controls"])
        wait(1500)
        tone = sorted({words[0] for words in state["controls"][start:]})
        report["lfo"] = dict(destination=17, min=min(tone), max=max(tone), distinct=len(tone))
        assert len(tone) > 2 and min(tone) < 16384 < max(tone), report
        assert stored()[1][17] == 16384, "LFO changed the saved base control"
        send([0x80, 60, 0, 0xb0, 109, 64])
        tap("STOP"); tap("STOP"); tap("RECORD")
        tap("1")
        session.press(session.code("1")); wait(80)
        try:
            for _ in range(4):
                session.turn(session.encoder("B"), 8, after_ms=150)
        finally:
            session.release(session.code("1"))
        wait()
        screen("parameter-lock")
        report["lock_base"] = stored()[1][18]
        tap("RECORD")
        start = len(state["controls"])
        tap("PLAY"); wait(1500); tap("STOP")
        decay = sorted({words[1] for words in state["controls"][start:]})
        report["parameter_lock"] = dict(base=report["lock_base"], expected=21504,
                                        min=min(decay), max=max(decay), distinct=len(decay))
        assert report["lock_base"] == 16384 and 21504 in decay, report
        # The fresh factory project requires a native resave before quick reload.
        tap("GLOBAL"); tap("YES"); tap("DOWN"); tap("YES")
        tap("DOWN"); tap("YES"); tap("YES"); wait(2500)
        screen("project-saved")
        tap("NO"); tap("NO"); tap("NO")
        send([0xb0, 17, 64, 0xb0, 21, 127])
        chord("FUNC", "YES")
        expected = [stored()[1][i] for i in (17, 18, 19, 22)]
        send([0xb0, 17, 100, 0xb0, 21, 0])
        assert stored()[1][18] == 25600 and stored()[1][22] == 0
        chord("FUNC", "NO"); wait(500)
        screen("after-reload")
        actual = [stored()[1][i] for i in (17, 18, 19, 22)]
        report["save_reload"] = dict(expected=expected, actual=actual, restored=actual == expected,
                                    machine=int.from_bytes(uc.mem_read(stored()[0] + 126, 1), "big"))
        assert report["save_reload"]["restored"] and report["save_reload"]["machine"] == 80, report
        send([0xb0, 21, 127, 0x90, 60, 100])
        first_sound = bytes(uc.mem_read(stored()[0], 162))
        chord("TRK", "2"); chord("FUNC", "SRC")
        for _ in range(4):
            tap("DOWN")
        tap("YES")
        assert bytes(uc.mem_read(stored(1)[0] + 126, 1)) == bytes([80])
        send([0xb1, 16, 64, 0xb1, 17, 64, 0xb1, 18, 64, 0xb1, 21, 0, 0x91, 60, 100])
        report["mixed_tracks"] = [selected(0), selected(1)]
        assert report["mixed_tracks"] == [[1, 1, 0], [1, 0, 0]], report
        assert bytes(uc.mem_read(stored()[0], 162)) == first_sound, "second track changed the first sound"
        # Check the approved ID80 exception against stock and unrelated legacy IDs.
        context = uc.context_save()
        scratch = 0x10010000
        session.m.ensure(scratch)
        scope = []
        try:
            for machine in (80, 3, 122):
                original_sound = bytearray(first_sound)
                original_sound[126] = machine
                for parameter, value in zip((17, 18, 19, 22), (12345, 23456, 3456, 25600)):
                    struct.pack_into(">h", original_sound, 20 + 2 * parameter, value)
                uc.mem_write(scratch, bytes(original_sound))
                session.m._fast_stepper_obj.left = 200000
                call(session.m, names["mp_sound_defaults"], [scratch])
                expected_sound = bytearray(original_sound)
                if machine == 80:
                    for parameter, value in zip((17, 18, 19, 22), (16384, 16384, 16384, 0)):
                        struct.pack_into(">h", expected_sound, 20 + 2 * parameter, value)
                assert bytes(uc.mem_read(scratch, 162)) == bytes(expected_sound), machine
                uc.mem_write(scratch + 256, struct.pack(">3i", -7, 777, 999))
                session.m._fast_stepper_obj.left = 200000
                call(session.m, names["mp_reset_range"], [133, scratch + 256, machine])
                expected_range = (0, 32512, 16384) if machine == 80 else (-7, 777, 999)
                assert struct.unpack(">3i", uc.mem_read(scratch + 256, 12)) == expected_range, machine
                scope.append(machine)
        finally:
            uc.context_restore(context)
        report["defaults_scope"] = dict(machine_ids=scope, other_sound_bytes_preserved=True,
                                        mode="bounded actual companion helpers on private buffers")
        chord("TRK", "1")
        send([0xb0, 17, 100])
        chord("B", "NO")
        reset = stored()[1][18]
        report["parameter_reset"] = dict(actual=reset, expected=16384,
                                          status="passed" if reset == 16384 else "failed")
        send([0xb0, 16, 100, 0xb0, 17, 100, 0xb0, 18, 100, 0xb0, 21, 127])
        chord("SRC", "PLAY")
        reset = [stored()[1][i] for i in (17, 18, 19, 22)]
        report["page_reset"] = dict(actual=reset, expected=[16384, 16384, 16384, 0],
                                     status="passed" if reset == [16384, 16384, 16384, 0] else "failed")
        assert state["active"] is None and state["selected_callbacks"] > 0 and not state["violations"], state
        report.update(callbacks=state["callbacks"], selected_callbacks=state["selected_callbacks"],
                      checked=["native machine selection", "native UART control delivery", "next-START MODEL latch",
                               "x0x blocks zero", "other track blocks preserved",
                               "native LFO destination and modulation", "native sequencer parameter lock",
                               "x0x-only defaults helper scope"])
        restored = report["save_reload"]["restored"]
        if restored:
            report["checked"].append("native project save and pattern reload")
        report["checked"].append("native mixed 808/909 tracks")
        report["unqualified"] = ["strict-model qualification", "kick audio"] + ([] if restored else ["save/reload"])
        report["failed_checks"] = [name for name in ("defaults", "parameter_reset", "page_reset")
                                   if report[name]["status"] == "failed"]
        report["status"] = "passed" if not report["failed_checks"] and restored else "failed"
    finally:
        if session is not None:
            session.close()
        (FOLDER / "native-report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--host", action="store_true")
    mode.add_argument("--full-os", action="store_true")
    args = parser.parse_args()
    report = host() if args.host else full_os() if args.full_os else component()
    print(json.dumps(report))
    return int(report["status"] != "passed")


if __name__ == "__main__":
    sys.exit(main())
