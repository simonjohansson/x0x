"""Build the real silent DN mod and exercise native selection and MODEL delivery."""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import time

from . import cpu, firmware

ROOT = cpu.ROOT
SOURCE = ROOT / "machines/digitone/machine.c"
FOLDER = ROOT / "out/dn/silent"


def host():
    FOLDER.mkdir(parents=True, exist_ok=True)
    binary = FOLDER / "host"
    cpu.command([os.environ.get("CC", "clang"), "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
                 "-I", ROOT / "vendor/elekloader/elekloader/sdk/include", "-I", ROOT / "include",
                 SOURCE, SOURCE.parent / "adapter.c", ROOT / "src/controls.c",
                 ROOT / "tests/ui/test_digitone_silent.c", "-o", binary])
    cpu.command([binary])
    return dict(status="passed", scope="DN production declarations/frame dispatch; native and DSP services are fakes")


def build():
    FOLDER.mkdir(parents=True, exist_ok=True)
    entries, revision = firmware.baseline()
    stock = firmware.verify_entry(entries["digitone-mk1"], ROOT / "firmware", revision)
    artifacts, logs = [], []
    for source in (ROOT / "vendor/elekloader/mods/core-dn1", ROOT / "vendor/elekloader/mods/machines-dn1", SOURCE.parent):
        meta = json.loads((source / "mod.json").read_text())
        logs.append(cpu.command([sys.executable, "-m", "elekloader.sdk.build", source,
                                 "--stock", stock["image"], "--out", FOLDER / "deps"], cwd=ROOT))
        suffix = "-os" + stock["version"] if meta["os"] != stock["version"] else ""
        artifacts.append(FOLDER / "deps" / f'{meta["id"]}-{meta["version"]}{suffix}.elemod')
    image = FOLDER / "x0z.syx"
    command = [sys.executable, "-m", "elekloader.patch", "--stock", stock["image"]]
    for artifact in artifacts:
        command += ["--mod", artifact]
    logs.append(cpu.command([*command, "--out", image, "--version", "X0Z0"], cwd=ROOT))
    (FOLDER / "build.log").write_text("\n".join(logs))
    return image, stock


def full_os():
    cpu.require_module("emu.session", "digiemu")
    from emu import panel
    from emu.bootstrap import first_run
    from emu.fwcheck import prepare
    from emu.longrun import never_fake_set_posts
    from emu.session import Session
    from unicorn.m68k_const import UC_M68K_REG_A7

    image, stock = build()
    names = {k: int(v, 0) for k, v in json.loads(Path(str(image) + ".map.json").read_text()).items()}
    report = dict(status="failed", scope="standard full-OS digiemu Session; native panel/encoder",
                  stock=stock, firmware_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
                  digiemu_revision=cpu.revision(ROOT / "vendor/digiemu"),
                  unqualified=["strict-model qualification", "kick audio"])
    state = dict(active=None, callbacks=0, starts=[], violations=[], observations=[], phase="", samples=[], decay_text=[])
    session = None
    try:
        with (FOLDER / "native-boot.log").open("w") as log, contextlib.redirect_stdout(log):
            paths, device = prepare(str(image), str(FOLDER / "cache"))
            assert device.short == "dn1"
            os.environ.update(paths.env())
            start = time.monotonic()
            snap = first_run(paths, cancel=lambda: time.monotonic() - start > 90)
            session = Session(snap, paths.syx, hle=False)
            never_fake_set_posts(session.m, session.ev, session.profile.set_post)
        uc = session.m.uc
        returns = set()
        word = lambda at: int.from_bytes(uc.mem_read(at, 4), "big")
        def checked(fn):
            def run(*args):
                try: fn(*args)
                except Exception as error:
                    state["violations"].append(str(error)); uc.emu_stop()
            return run
        def returned(_uc, at, _size, _data):
            active = state["active"]
            if active is None or at != active["return"]: return
            after = bytes(uc.mem_read(names["fw_voices"], 1024))
            lo, hi = active["slot"] * 128, (active["slot"] + 1) * 128
            assert after[lo:hi] == bytes(128), "x0z did not silence its voice"
            assert after[:lo] == active["before"][:lo] and after[hi:] == active["before"][hi:], "x0z wrote another voice"
            selection = list(struct.unpack(">3I", uc.mem_read(names["selection"] + active["slot"] * 12, 12)))
            assert selection[0] == 1, "real callback did not consume a settled frame/START"
            event = dict(slot=active["slot"], track=active["track"], fresh=active["fresh"], model=selection[1])
            state["callbacks"] += 1
            state["observations"].append(event)
            if active["fresh"]: state["starts"].append(event)
            state["active"] = None
        def entered(_uc, _at, _size, _data):
            assert state["active"] is None, "nested x0z callback"
            sp = uc.reg_read(UC_M68K_REG_A7)
            ret, slot, output, voice = struct.unpack(">4I", uc.mem_read(sp, 16))
            assert output == names["fw_voices"] + slot * 128, "companion output pointer differs"
            if ret not in returns:
                session.at(ret, checked(returned)); returns.add(ret)
            info = struct.unpack(">5I", uc.mem_read(voice, 20))
            state["active"] = dict(before=bytes(uc.mem_read(names["fw_voices"], 1024)), slot=slot,
                                   fresh=info[2], track=info[3])
            state["active"]["return"] = ret
        session.at(names["x0z_dn_machine_render"], checked(entered))
        def receive(_uc, _at, _size, _data):
            source = word(uc.reg_read(UC_M68K_REG_A7) + 8)
            if word(source + 8) == 0 and state["phase"]:
                values = [struct.unpack(">6I",uc.mem_read(source + 36 + 24 * i,24)) for i in range(word(source + 32))]
                state["samples"].append((state["phase"],[(v[0],v[1],v[4],v[5]) for v in values]))
        session.at(names["render_silence"],checked(receive))
        def text(_uc, _at, _size, _data):
            if state["phase"] != "lock-edit": return
            sp = uc.reg_read(UC_M68K_REG_A7)
            if word(sp + 12) == 58 and word(sp + 16) == 40:
                state["decay_text"].append(bytes(uc.mem_read(word(sp + 36),8)).split(b"\0",1)[0].decode("ascii"))
        session.at(names["fw_textbox"],checked(text))
        def wait(ms=80):
            session.run_ms(ms)
            assert not session.halted and not state["violations"], (session.halted, state["violations"])
        def tap(key):
            session.tap(session.code(key), hold_ms=100, after_ms=300)
            assert not session.halted and not state["violations"], (session.halted, state["violations"])
        def turn(knob, detents):
            while detents:
                amount = max(-8,min(8,detents))
                session.turn(session.encoder(knob),amount,after_ms=150)
                detents -= amount
            wait()
        def screen(name):
            panel.write_png(session.frames[-1][1], str(FOLDER / (name + ".png")), scale=4)
        def stored(track=0):
            kit = word(names["fw_kit"]) + 326 * track
            return [int.from_bytes(uc.mem_read(kit + 0x2c + 2 * slot, 2), "big", signed=True) for slot in (0,27,28,29,32)]
        def controls():
            # Re-select from another page: a second SYN2 press toggles to its blank second page.
            tap("SYN1"); tap("SYN2")
            brain = word(names["x0z_dn_brain"])
            bottom, top = word(brain + 0x54), word(brain + 0x5c)
            view = word(word(bottom + 8) + 0xc0)
            assert word(0x41368ce4) == 2 and bottom == top and word(view + 144) == 0, "not on SYN2 first page"
        wait()
        session.press(session.code("T1")); wait(600); session.release(session.code("T1")); wait()
        screen("mod-menu"); tap("YES"); screen("machine-menu"); tap("RIGHT"); tap("YES")
        report["defaults"] = stored()
        assert report["defaults"] == [80 << 8,16384,16384,16384,0], report["defaults"]
        controls(); screen("default-controls")
        for knob in ("A", "B", "C"): turn(knob,16)
        report["edited"] = stored()
        assert all(value > 16384 for value in report["edited"][1:4]), report["edited"]
        tap("9")
        assert state["starts"], "native key produced no x0z START"
        report["808"] = state["starts"][-1]
        controls()
        for _ in range(16):
            if stored()[4] >= 16384: break
            turn("F",8)
        else: raise AssertionError("native MODEL encoder did not cross threshold")
        slot = report["808"]["slot"]
        report["pending"] = list(struct.unpack(">3I", uc.mem_read(names["selection"] + 12 * slot,12)))
        screen("controls-909")
        starts = len(state["starts"])
        tap("9")
        assert len(state["starts"]) > starts, "native key produced no new START"
        report["909"] = state["starts"][-1]
        assert report["808"]["model"] == 0 and report["pending"][1] == 0 and report["909"]["model"] == 1
        # One ordinary sequencer lock, including the value painted while its step is held.
        tap("STOP"); tap("STOP"); controls(); tap("RECORD"); tap("1")
        session.press(session.code("1")); wait()
        state["phase"] = "lock-edit"
        for _ in range(4): turn("B",8)
        pattern = word(names["fw_pattern"])
        locked = int.from_bytes(uc.mem_read(pattern + 0x1e80 + 2 * 28,2),"big",signed=True)
        screen("lock-edit")
        report["lock_edit"] = dict(raw=locked, base=stored()[2], shown=state["decay_text"][-8:])
        assert locked >= 0 and str(locked >> 8) in state["decay_text"], report["lock_edit"]
        session.release(session.code("1")); wait(); tap("RECORD")
        state["phase"] = "lock-play"; tap("PLAY"); wait(1500); tap("STOP")
        observed = [v[1] for phase,values in state["samples"] if phase == "lock-play" for v in values if v[0] == 1]
        report["lock_play"] = dict(expected=locked, observed=sorted(set(observed)))
        assert locked in observed and stored()[2] == report["lock_edit"]["base"], report["lock_play"]
        state["phase"] = ""
        # One native LFO destination: the selected 808 Tone / 909 Tune control.
        tap("AMP"); tap("LFO")
        kit = word(names["fw_kit"])
        read_slot = lambda slot: int.from_bytes(uc.mem_read(word(names["fw_kit"]) + 0x2c + 2 * slot,2),"big",signed=True)
        choices = []
        for _ in range(32):
            destination = read_slot(4) >> 8
            if destination == 27: break
            turn("D",max(-8,min(8,27 - destination))); tap("YES")
            choices.append(read_slot(4))
        else: raise AssertionError("native LFO destination did not select Tone/Tune: " + str(choices))
        report["lfo_destination"] = dict(raw=read_slot(4), choices=choices)
        for _ in range(4): turn("H",8)
        report["lfo_depth"] = read_slot(8)
        tone_base = stored()[1]
        session.press(session.code("9")); wait()
        state["phase"] = "lfo"; wait(1500)
        session.release(session.code("9")); wait()
        tone = [values[0][1] for phase,values in state["samples"] if phase == "lfo"]
        report["lfo"] = dict(base=tone_base, minimum=min(tone), maximum=max(tone), samples=len(tone))
        assert len(set(tone)) > 2 and stored()[1] == tone_base, report["lfo"]
        state["phase"] = ""
        # Persist the project first; a fresh factory project rejects temporary saves.
        tap("GLOBAL"); tap("YES"); tap("DOWN"); tap("YES"); tap("DOWN"); tap("YES"); tap("YES")
        wait(2500)
        for _ in range(3): tap("NO")
        controls()
        def chord(key):
            session.press(session.code("FUNC")); wait(40); tap(key)
            session.release(session.code("FUNC")); wait()
        saved = stored()
        chord("YES")
        turn("B",16)
        turn("F",-32)
        report["persistence"] = dict(saved=saved, changed=stored())
        assert stored() != saved, "native persistence edit changed no control"
        chord("NO"); wait(500)
        report["persistence"]["restored"] = stored()
        screen("reloaded-controls")
        assert stored() == saved, report["persistence"]
        # Overlap notes on two native tracks choosing different models.
        controls()
        for _ in range(16):
            if stored()[4] < 16384: break
            turn("F",-8)
        session.press(session.code("9")); wait()
        old = state["starts"][-1]
        assert old["track"] == 0 and old["model"] == 0, old
        track0 = stored()
        session.press(session.code("T2")); wait(600); session.release(session.code("T2")); wait()
        tap("YES"); tap("RIGHT"); tap("YES"); controls()
        assert stored(1) == [80 << 8,16384,16384,16384,0], stored(1)
        for _ in range(16):
            if stored(1)[4] >= 16384: break
            turn("F",8)
        mixed_begin = len(state["observations"])
        session.press(session.code("11")); wait(150)
        mixed = {(v["track"],v["model"]) for v in state["observations"][mixed_begin:]}
        report["mixed_tracks"] = sorted(mixed)
        assert {(0,0),(1,1)} <= mixed and stored() == track0, (mixed,stored(),track0)
        session.release(session.code("11")); session.release(session.code("9")); wait()
        assert not state["active"] and state["callbacks"] > 0
        report.update(status="passed", callbacks=state["callbacks"], starts=state["starts"],
                      checked=["native menu/defaults", "native first-page controls", "native encoder MODEL delivery",
                               "next-START MODEL latch", "real companion fresh/settled frame",
                               "zero owned voice output", "other voices preserved", "native p-lock and held-lock display", "native LFO delivery", "native save/reload", "mixed 808/909 tracks"])
    except (AssertionError, ValueError) as error:
        report["reason"] = str(error)
    finally:
        report["callbacks"] = state["callbacks"]
        report["starts"] = state["starts"]
        if session is not None: session.close()
        (FOLDER / "native-report.json").write_text(json.dumps(report,indent=2) + "\n")
    return report

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", action="store_true")
    parser.add_argument("--build", action="store_true")
    args = parser.parse_args()
    if args.host: report = host()
    elif args.build:
        image, stock = build(); report = dict(status="passed", scope="firmware package only", image=str(image), stock=stock)
    else: report = full_os()
    print(json.dumps(report))
    return int(report["status"] != "passed")


if __name__ == "__main__":
    sys.exit(main())
