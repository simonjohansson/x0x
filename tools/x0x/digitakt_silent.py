"""Check the DT combined mod with host fakes, actual ASM, or a full-OS smoke."""
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
import wave

from . import audio, coupling808, cpu, firmware
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
    for source in (SOURCE, fakes, ROOT / "targets/coldfire/selector.s", ROOT / "targets/coldfire/silence.s", ROOT / "targets/coldfire/body808.s", ROOT / "targets/coldfire/tone808.s", ROOT / "targets/coldfire/body909.s", ROOT / "targets/coldfire/coupling808.s"):
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
                   (address("reads"), address("reads") + 32),
                   (address("body_state"), address("body_state") + 64),
                   (address("tone_state"), address("tone_state") + 32),
                   (address("coupling_state"), address("coupling_state") + 64), (STACK - 2048, STACK)]
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
            audible = live and expected[3 * track] and label != "invalid control"
            # START can initialize or switch this lane in the current call.
            if live and starts & (1 << track) and label != "invalid control":
                audible = True
            if audible:
                samples = struct.unpack(">32i", raw)
                assert 0 < max(abs(x) for x in samples) < 0x40000000, (label, track, "missing/bounded body")
                if starts & (1 << track) and (model0 if track == 0 else model7) >= 16384:
                    from .body909 import reference
                    assert max(abs(x/2**31-y) for x,y in zip(samples,reference(32, 12345))) <= 1e-5
            else:
                assert raw == (bytes(128) if live else original[track * 128:(track + 1) * 128]), label
            assert int.from_bytes(uc.mem_read(address("reads") + 4 * track, 4), "big") == (0x27 if live else 0), label
            if not live:
                expected[3 * track:3 * track + 3] = [0, 0, 0]
            elif starts & (1 << track) and label != "invalid control":
                expected[3 * track:3 * track + 3] = [1, int((model0 if track == 0 else model7) >= 16384), 0]
        state = list(struct.unpack(">24I", uc.mem_read(address("selection"), 96)))
        assert state == expected, (label, state, expected)
        traces.append(label)
    report = dict(status="passed", scope="compiled DT C and actual ColdFire selector/body ASM; native services are fakes",
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
                  unqualified=["p-lock/LFO delivery", "save/reload", "strict-model qualification", "808 circuit fidelity/pot calibration", "909 diode shaping, Tune/Attack, complete VCA and Decay taper"])
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
        word = lambda at: int.from_bytes(uc.mem_read(at,4),"big")
        state = dict(active=None, callbacks=0, selected_callbacks=0, violations=[], controls=[],
                     body_peak=0, body909_peak=0, body909_callbacks=0, mixed_audible_blocks=0,
                     capture909=False, started909=False, samples909=[], words909=[], lock_edit=False, lock_display=[],
                     decay_phase=None, decay_started=False, decay_samples=[], decay_words=[], tone_words=[])
        state.update(coupling_blocks=0, coupling_error=0.0, coupling_difference=0)
        returns = set()
        def checked(fn):
            def run(*args):
                try:
                    fn(*args)
                except Exception as error:
                    state["violations"].append(str(error))
                    session.halted = True
                    uc.emu_stop()
            return run
        def returned(_uc, at, _size, _data):
            active = state["active"]
            if active is None or at != active["return"]:
                return
            after = bytes(uc.mem_read(names["fw_track_blocks"], 1024))
            for track, machine in enumerate(active["machines"]):
                lo, hi = 128 * track, 128 * (track + 1)
                if machine != 80:
                    assert after[lo:hi] == active["before"][lo:hi], "callback changed an unowned block"
                    continue
                initialized, model, _ = struct.unpack(">3I", uc.mem_read(names["selection"] + 12 * track, 12))
                if initialized and model == 0:
                    peak = max(abs(x) for x in struct.unpack(">32i", after[lo:hi]))
                    coupling = active["coupling"].get(track)
                    assert coupling is not None, "808 omitted its coupling stage"
                    words = struct.unpack(">32i", after[lo:hi])
                    error = max(abs(a/2**31-b) for a,b in zip(words,coupling["expected"]))
                    assert error <= 1e-5, ("native coupling recurrence",error)
                    assert struct.unpack(">2i",uc.mem_read(coupling["state"],8)) == (coupling["input"][-1],words[-1])
                    state["coupling_blocks"] += 1
                    state["coupling_error"] = max(state["coupling_error"],error)
                    state["coupling_difference"] = max(state["coupling_difference"],max(abs(a-b) for a,b in zip(words,coupling["input"])))
                    state["body_peak"] = max(state["body_peak"], peak)
                    assert peak < 0x40000000, "808 body exceeded fixed internal headroom"
                    if track == 0 and state["decay_phase"] and state["decay_started"]:
                        state["decay_samples"].extend(struct.unpack(">32i", after[lo:hi]))
                elif initialized and model == 1:
                    words = struct.unpack(">32i",after[lo:hi])
                    peak = max(abs(x) for x in words)
                    assert peak <= 1 << 29, "909 body exceeded its quarter-scale bound"
                    state["body909_peak"] = max(state["body909_peak"],peak)
                    state["body909_callbacks"] += 1
                    if track == 0 and state["capture909"] and state["started909"]:
                        state["samples909"].extend(words)
                else:
                    assert after[lo:hi] == bytes(128), "inactive callback was not silent"
            audible_models = set()
            for track,machine in enumerate(active["machines"]):
                if machine == 80 and any(after[128*track:128*(track+1)]):
                    initialized,model,_ = struct.unpack(">3I",uc.mem_read(names["selection"]+12*track,12))
                    if initialized: audible_models.add(model)
            state["mixed_audible_blocks"] += int(audible_models == {0,1})
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
            state["active"].update(tones=set(),coupling={})
            state["active"]["return"] = ret
        session.at(names["x0x_dt_render"], checked(entered))
        def body_entered(_uc, _at, _size, _data):
            if not state["decay_phase"]:
                return
            sp = uc.reg_read(UC_M68K_REG_A7)
            owner, _output, start, decay = struct.unpack(">4I", uc.mem_read(sp + 4, 16))
            if owner != names["body_state"]:
                return
            if start:
                state["decay_started"] = True
                state["decay_samples"] = []
                state["decay_words"] = []
            if state["decay_started"]:
                state["decay_words"].append(decay)
        session.at(names["x0x_808_body"], checked(body_entered))
        def body909_entered(_uc, _at, _size, _data):
            if not state["capture909"]:
                return
            sp = uc.reg_read(UC_M68K_REG_A7)
            owner, _output, start, decay = struct.unpack(">4I",uc.mem_read(sp+4,16))
            if owner == names["body_state"] and start:
                state["started909"] = True
                state["samples909"] = []
                state["words909"] = []
            if owner == names["body_state"] and state["started909"]:
                state["words909"].append(decay)
        session.at(names["x0x_909_body"],checked(body909_entered))
        def coupling_entered(_uc, _at, _size, _data):
            active = state["active"]
            assert active is not None
            sp = uc.reg_read(UC_M68K_REG_A7)
            owner, output = struct.unpack(">2I",uc.mem_read(sp+4,8))
            track, remainder = divmod(owner-names["coupling_state"],8)
            assert not remainder and 0 <= track < 8 and track in active["tones"] and track not in active["coupling"]
            assert output == names["fw_track_blocks"] + 128*track
            previous = struct.unpack(">2i",uc.mem_read(owner,8))
            if word(names["fw_voice_start"]) & (1 << track):
                assert previous == (0,0), "START did not reset coupling"
            inputs = struct.unpack(">32i",uc.mem_read(output,128))
            assert max(map(abs,inputs)) <= 1 << 29
            x,y = (value/2**31 for value in previous)
            expected=[]
            for value in inputs:
                current=value/2**31
                y=coupling808.A*y+coupling808.B*(current-x)
                x=current
                expected.append(y)
            active["coupling"][track]=dict(state=owner,input=inputs,expected=expected)
        session.at(names["x0x_808_coupling"],checked(coupling_entered))
        def tone_entered(_uc, _at, _size, _data):
            sp = uc.reg_read(UC_M68K_REG_A7)
            owner = word(sp+4)
            track,remainder = divmod(owner-names["tone_state"],4)
            assert state["active"] is not None and not remainder and 0 <= track < 8
            state["active"]["tones"].add(track)
            if not state["decay_phase"] or not state["decay_started"]:
                return
            sp = uc.reg_read(UC_M68K_REG_A7)
            owner, _output, tone = struct.unpack(">3I", uc.mem_read(sp + 4, 12))
            if owner == names["tone_state"]:
                state["tone_words"].append(tone)
        session.at(names["x0x_808_tone"], checked(tone_entered))
        def shown_value(_uc, _at, _size, _data):
            if state["lock_edit"]:
                sp = uc.reg_read(UC_M68K_REG_A7)
                parameter, value = struct.unpack(">2i",uc.mem_read(sp+4,8))
                if parameter == 133:  # SRC B / DECAY, before borrowed graphics.
                    state["lock_display"].append(value)
        session.at(names["mp_value_text"],checked(shown_value))
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
        pcm_start = len(session.pcm)
        send([0x90, 60, 100]); report["808"] = selected()
        wait(400)
        pcm = bytes(session.pcm[pcm_start:])
        pcm_peak = max(abs(x) for x in struct.unpack("<" + "h" * (len(pcm) // 2), pcm))
        assert state["body_peak"] > 0 and pcm_peak > 0, "808 did not reach native audio output"
        with wave.open(str(FOLDER / "native-808.wav"), "wb") as wav:
            wav.setparams((2, 2, session.audio_cfg["rate"], 0, "NONE", "not compressed"))
            wav.writeframes(pcm)
        report["body_audio"] = dict(raw_peak_q31=state["body_peak"], downstream_pcm_peak=pcm_peak,
                                    capture=str(FOLDER / "native-808.wav"), scope="isolated native 808 note")
        send([0xb0, 21, 127]); report["pending"] = selected()
        send([0x80, 60, 0])
        state["capture909"] = True
        send([0x90, 60, 100]); report["909"] = selected()
        # Capture downstream PCM after START delivery; the raw capture retains onset.
        pcm_start = len(session.pcm)
        wait(400)
        state["capture909"] = False
        samples909 = [x/2**31 for x in state["samples909"]]
        from .body909 import reference
        assert len(samples909) >= 19200 and state["started909"]
        error909 = max(abs(x-y) for x,y in zip(samples909,reference(len(samples909))))
        assert error909 <= 1e-5 and set(state["words909"]) == {16384}, error909
        pcm = bytes(session.pcm[pcm_start:])
        pcm_peak = max(abs(x) for x in struct.unpack("<"+"h"*(len(pcm)//2),pcm))
        assert 0 < pcm_peak < 32767 and state["body909_peak"] > 0
        with wave.open(str(FOLDER / "native-909.wav"),"wb") as wav:
            wav.setparams((2,2,session.audio_cfg["rate"],0,"NONE","not compressed"))
            wav.writeframes(pcm)
        audio.write_wav(FOLDER / "raw-909.wav",samples909,48000)
        (FOLDER / "raw-909.json").write_text(json.dumps(samples909)+"\n")
        report["body909_audio"] = dict(raw_peak_q31=state["body909_peak"],downstream_pcm_peak=pcm_peak,
            frames=len(samples909),waveform_peak_error_fs=error909,
            capture=str(FOLDER / "native-909.wav"),raw_capture=str(FOLDER / "raw-909.wav"),
            scope="isolated native 909 PCM after START delivery; raw capture includes onset")
        screen("controls-909")
        assert report["808"] == [1, 0, 0] and report["pending"] == [1, 0, 0] and report["909"] == [1, 1, 0], report
        values = stored()[1]
        assert [values[i] for i in (17, 18, 19, 22)] == [16384, 16384, 16384, 32512]
        report["decay_909"] = {}
        for label, position in (("short",0),("long",127)):
            send([0x80,60,0]); wait(1200)
            send([0xb0,17,position]); wait(300)
            state["started909"] = False
            state["capture909"] = True
            begin = len(session.pcm)
            send([0x90,60,100]); wait(600)
            state["capture909"] = False
            samples = [v/2**31 for v in state["samples909"]]
            assert len(samples) >= 28800 and set(state["words909"]) == {position*256}, label
            error = max(abs(a-b) for a,b in zip(samples,reference(len(samples),position*256)))
            assert error <= 1e-5, (label,error)
            pcm = bytes(session.pcm[begin:])
            peak = max(abs(v[0]) for v in struct.iter_unpack("<h",pcm))
            assert 0 < peak < 32767, (label,peak)
            path = FOLDER / f"909-decay-{label}-native.wav"
            with wave.open(str(path),"wb") as wav:
                wav.setparams((2,2,session.audio_cfg["rate"],0,"NONE","not compressed")); wav.writeframes(pcm)
            audio.write_wav(FOLDER / f"909-decay-{label}-raw.wav",samples,48000)
            report["decay_909"][label] = dict(raw=position*256,frames=len(samples),maximum_error_fs=error,
                native_peak_pcm16=peak,native_wav=str(path))
        send([0x80,60,0,0xb0,17,64])
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
        state["lock_edit"] = True
        try:
            for _ in range(4):
                session.turn(session.encoder("B"), 8, after_ms=150)
        finally:
            state["lock_edit"] = False
            session.release(session.code("1"))
        wait()
        assert state["lock_display"], "native lock editor did not display DECAY"
        locked_value = state["lock_display"][-1]
        assert 16384 < locked_value <= 32512, state["lock_display"]
        screen("parameter-lock")
        report["lock_base"] = stored()[1][18]
        tap("RECORD")
        start = len(state["controls"])
        tap("PLAY"); wait(1500); tap("STOP")
        decay = sorted({words[1] for words in state["controls"][start:]})
        report["parameter_lock"] = dict(base=report["lock_base"], expected=locked_value,
                                        min=min(decay), max=max(decay), distinct=len(decay),
                                        expected_source="native held-step DECAY display")
        assert report["lock_base"] == 16384 and locked_value in decay, report
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
        assert state["mixed_audible_blocks"] > 0, "808/909 never produced audio in the same callback"
        report["mixed_audible_blocks"] = state["mixed_audible_blocks"]
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
        # Same native track/AMP/velocity, different B values; compare actual DSP tails.
        send([0x80, 60, 0, 0x81, 60, 0])
        report["decay_audio"] = {}
        for label, position in (("short", 0), ("long", 127)):
            send([0xb0, 16, 64, 0xb0, 17, position, 0xb0, 18, 64, 0xb0, 21, 0])
            wait(600)
            state["decay_phase"] = label
            state["decay_started"] = False
            state["decay_samples"] = []
            state["decay_words"] = []
            begin_pcm = len(session.pcm)
            send([0x90, 60, 100]); wait(750)
            state["decay_phase"] = None
            samples = state["decay_samples"]
            assert len(samples) >= 19200 and state["decay_words"], label
            early = sum(x*x for x in samples[:4800])
            late = sum(x*x for x in samples[14400:19200])
            assert early > 0
            pcm = bytes(session.pcm[begin_pcm:])
            with wave.open(str(FOLDER / f"decay-{label}-native.wav"), "wb") as wav:
                wav.setparams((2, 2, session.audio_cfg["rate"], 0, "NONE", "not compressed"))
                wav.writeframes(pcm)
            audio.write_wav(FOLDER / f"decay-{label}-raw.wav", [x/2**31 for x in samples], 48000)
            pcm_peak = max(abs(x) for x in struct.unpack("<"+"h"*(len(pcm)//2), pcm))
            assert 0 < pcm_peak < 32767, label
            report["decay_audio"][label] = dict(target=position, delivered_min=min(state["decay_words"]),
                delivered_max=max(state["decay_words"]), frames=len(samples),
                late_early_energy_ratio=late/early, native_pcm_peak=pcm_peak,
                native_wav=str(FOLDER / f"decay-{label}-native.wav"),
                raw_wav=str(FOLDER / f"decay-{label}-raw.wav"))
            send([0x80, 60, 0])
        assert (report["decay_audio"]["long"]["late_early_energy_ratio"] >
                4 * report["decay_audio"]["short"]["late_early_energy_ratio"]), report["decay_audio"]
        send([0xb0, 17, 64])
        report["tone_audio"] = {}
        tone_samples = []
        for label, position in (("dark", 0), ("bright", 127)):
            send([0xb0, 16, position, 0xb0, 17, 64, 0xb0, 21, 0]); wait(600)
            state["decay_phase"] = "tone-" + label
            state["decay_started"] = False
            state["decay_samples"] = []
            state["decay_words"] = []
            state["tone_words"] = []
            pcm_at = len(session.pcm)
            send([0x90, 60, 100]); wait(300)
            state["decay_phase"] = None
            samples = state["decay_samples"]
            assert len(samples) >= 8192 and state["tone_words"], label
            assert set(state["decay_words"]) == {16384}, state["decay_words"]
            assert set(state["tone_words"]) == {position << 8}, state["tone_words"]
            tone_samples.append(samples[1024:8192])
            pcm = bytes(session.pcm[pcm_at:])
            with wave.open(str(FOLDER / f"tone-{label}-native.wav"), "wb") as wav:
                wav.setparams((2, 2, session.audio_cfg["rate"], 0, "NONE", "not compressed"))
                wav.writeframes(pcm)
            audio.write_wav(FOLDER / f"tone-{label}-raw.wav", [x/2**31 for x in samples],48000)
            peak=max(abs(x) for x in struct.unpack("<"+"h"*(len(pcm)//2),pcm))
            assert 0 < peak < 32767
            report["tone_audio"][label] = dict(target=position, delivered=sorted(set(state["tone_words"])),
                decay_raw=16384, raw_frames=len(samples), native_peak=peak,
                native_wav=str(FOLDER / f"tone-{label}-native.wav"))
            send([0x80, 60, 0])
        difference=max(abs(a-b) for a,b in zip(*tone_samples)) / 2**31
        assert difference > .001, "Tone did not change actual ASM output after filter settling"
        report["tone_audio"]["settled_peak_difference_fs"] = difference
        send([0xb0, 16, 64])
        assert state["active"] is None and state["selected_callbacks"] > 0 and not state["violations"], state
        report.update(callbacks=state["callbacks"], selected_callbacks=state["selected_callbacks"],
                      checked=["native machine selection", "native UART control delivery", "next-START MODEL latch",
                               "808 body reaches native PCM", "native Decay changes the actual ASM tail", "native Tone changes actual filtered ASM output", "909 unshaped body and native Decay endpoints reach PCM", "other track blocks preserved",
                               "native LFO destination and modulation", "native sequencer parameter lock",
                               "x0x-only defaults helper scope"])
        restored = report["save_reload"]["restored"]
        if restored:
            report["checked"].append("native project save and pattern reload")
        report["checked"].append("native mixed 808/909 tracks")
        assert state["coupling_blocks"] > 0 and state["coupling_difference"] > 0
        report["coupling_808"] = dict(blocks=state["coupling_blocks"],
            maximum_entry_recurrence_error_fs=state["coupling_error"],
            maximum_input_output_difference_q31=state["coupling_difference"],
            scope="actual coupling after Tone, owned state and START reset")
        report["unqualified"] = ["strict-model qualification", "808 circuit fidelity/pot calibration", "909 diode shaping, Tune/Attack, complete VCA and Decay taper"] + ([] if restored else ["save/reload"])
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
