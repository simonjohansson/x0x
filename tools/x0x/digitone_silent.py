"""Build the DN mod and exercise native controls with both provisional bodies."""
import argparse
import contextlib
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import sys
import time
import wave

from . import body909, coupling808, cpu, firmware

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
    image = FOLDER / "x0x.syx"
    command = [sys.executable, "-m", "elekloader.patch", "--stock", stock["image"]]
    for artifact in artifacts:
        command += ["--mod", artifact]
    logs.append(cpu.command([*command, "--out", image, "--version", "X0X0"], cwd=ROOT))
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
    report = dict(status="failed", failed_checks=[], capture_baselines={}, scope="standard full-OS digiemu Session; native panel/encoder",
                  stock=stock, firmware_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
                  digiemu_revision=cpu.revision(ROOT / "vendor/digiemu"),
                  unqualified=["strict-model qualification", "faithful 808 timbre, retrigger and pot tapers",
                               "complete loaded 808 output network including C49/buffer and C50",
                               "909 shaping, pitch envelope and Tune/Attack response, complete VCA and Decay taper"])
    state = dict(active=None, callbacks=0, starts=[], violations=[], observations=[], phase="", samples=[], decay_text=[],
                 body_nonzero=0, body_peak=0, triangle_nonzero=0, triangle_peak=0,
                 triangle_error=0.0, triangle_samples=[None] * 8, triangle_attenuation=[0.0] * 8, audio_capture=None,
                 coupling_blocks=0, coupling_error=0.0, coupling_difference=0)
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
                    state["violations"].append(str(error))
                    session.halted = "x0x callback assertion: " + str(error)
                    uc.emu_stop()
            return run
        def returned(_uc, at, _size, _data):
            active = state["active"]
            if active is None or at != active["return"]: return
            after = bytes(uc.mem_read(names["fw_voices"], 1024))
            lo, hi = active["slot"] * 128, (active["slot"] + 1) * 128
            assert after[:lo] == active["before"][:lo] and after[hi:] == active["before"][hi:], "x0x wrote another voice"
            selection = list(struct.unpack(">3I", uc.mem_read(names["selection"] + active["slot"] * 12, 12)))
            assert selection[0] == 1, "real callback did not consume a settled frame/START"
            words = struct.unpack(">32i", after[lo:hi])
            peak = max(abs(v) for v in words)
            if selection[1] == 0:
                # The coupling HP has L1 gain below two for quarter-scale input.
                assert peak <= 1 << 30, "808 coupling output exceeded its half-scale bound"
                assert not active.get("triangle"), "808 selected the 909 renderer"
                coupling = active.get("coupling")
                assert coupling is not None, "808 did not enter its actual coupling ASM"
                error = max(abs(actual / 2**31 - wanted) for actual, wanted in zip(words, coupling["expected"]))
                assert error <= 1e-5, ("808 native coupling differs from its entry-state recurrence", error)
                assert struct.unpack(">2i", uc.mem_read(coupling["state"], 8)) == (coupling["input"][-1], words[-1]), "808 coupling did not retain its last input/output"
                state["coupling_blocks"] += 1
                state["coupling_error"] = max(state["coupling_error"], error)
                state["coupling_difference"] = max(state["coupling_difference"], max(abs(a-b) for a,b in zip(words,coupling["input"])))
                state["triangle_samples"][active["slot"]] = None
                state["body_peak"] = max(state["body_peak"], peak)
                state["body_nonzero"] += peak != 0
            else:
                assert peak <= 1 << 29, "909 body exceeded its quarter-scale bound"
                assert not active.get("coupling"), "909 entered the 808 coupling stage"
                assert active.get("triangle"), "909 did not enter its actual ASM renderer"
                offset = 0 if active["fresh"] else state["triangle_samples"][active["slot"]]
                assert offset is not None, "909 continuation has no observed START"
                attenuation = 0.0 if active["fresh"] else state["triangle_attenuation"][active["slot"]]
                loss = -1 / (body909.SAMPLE_RATE * body909.decay_tau(active["decay909"]))
                expected = [body909.GAIN * math.exp(attenuation+(j+1)*loss)
                            * body909.triangle(body909.FREQUENCY*(offset+j+1)/body909.SAMPLE_RATE)
                            for j in range(32)]
                state["triangle_attenuation"][active["slot"]] = attenuation+32*loss
                error = max(abs(actual / 2**31 - wanted) for actual, wanted in zip(words, expected))
                assert error <= 1e-5, ("909 native output differs from the triangle reference", error)
                state["triangle_samples"][active["slot"]] = offset + 32
                state["triangle_error"] = max(state["triangle_error"], error)
                state["triangle_peak"] = max(state["triangle_peak"], peak)
                state["triangle_nonzero"] += peak != 0
            capture = state["audio_capture"]
            if capture is not None and active["track"] == capture.get("track", 0):
                if active["fresh"]:
                    assert capture["slot"] is None, "audio capture unexpectedly retriggered"
                    capture["slot"] = active["slot"]
                if active["slot"] == capture["slot"]:
                    assert selection[1] == capture.get("model", 0), ("audio capture selected the wrong model",
                        {key: active[key] for key in ("slot", "track", "fresh", "raw_model", "previous_selection")}, selection)
                    capture["words"].extend(words)
            event = dict(slot=active["slot"], track=active["track"], fresh=active["fresh"], model=selection[1])
            state["callbacks"] += 1
            state["observations"].append(event)
            if active["fresh"]: state["starts"].append(event)
            state["active"] = None
        def entered(_uc, _at, _size, _data):
            assert state["active"] is None, "nested x0x callback"
            sp = uc.reg_read(UC_M68K_REG_A7)
            ret, slot, output, voice = struct.unpack(">4I", uc.mem_read(sp, 16))
            assert output == names["fw_voices"] + slot * 128, "companion output pointer differs"
            if ret not in returns:
                session.at(ret, checked(returned)); returns.add(ret)
            info = struct.unpack(">5I", uc.mem_read(voice, 20))
            state["active"] = dict(before=bytes(uc.mem_read(names["fw_voices"], 1024)), slot=slot,
                                   fresh=info[2], track=info[3])
            state["active"]["raw_model"] = int.from_bytes(uc.mem_read(word(names["frame"]) + (slot * 79 + 32) * 2, 2), "big", signed=True)
            state["active"]["previous_selection"] = list(struct.unpack(">3I", uc.mem_read(names["selection"] + slot * 12, 12)))
            state["active"]["return"] = ret
        session.at(names["x0x_dn_machine_render"], checked(entered))
        def triangle_entered(_uc, _at, _size, _data):
            active = state["active"]
            assert active is not None, "909 ASM ran outside the machine callback"
            sp = uc.reg_read(UC_M68K_REG_A7)
            saved, output, start, decay = struct.unpack(">4I", uc.mem_read(sp + 4, 16))
            assert saved == names["body"] + active["slot"] * 8 and output == names["fw_voices"] + active["slot"] * 128
            assert start == active["fresh"], "909 lost the native START flag"
            active["triangle"] = True
            active["decay909"] = decay
            capture = state["audio_capture"]
            if capture is not None and active["track"] == capture.get("track", 0) and capture.get("model") == 1 and (active["fresh"] or active["slot"] == capture["slot"]):
                capture["decay_words"].append(decay)
        session.at(names["x0x_909_body"], checked(triangle_entered))
        def coupling_entered(_uc, _at, _size, _data):
            active = state["active"]
            assert active is not None and active.get("tone") and not active.get("coupling"), "coupling must follow Tone once per 808 block"
            sp = uc.reg_read(UC_M68K_REG_A7)
            saved, output = struct.unpack(">2I", uc.mem_read(sp + 4, 8))
            assert saved == names["coupling_state"] + active["slot"] * 8, "wrong voice's coupling state"
            assert output == names["fw_voices"] + active["slot"] * 128, "wrong coupling output buffer"
            previous = struct.unpack(">2i", uc.mem_read(saved, 8))
            if active["fresh"]:
                assert previous == (0,0), "808 START did not clear coupling state"
            inputs = struct.unpack(">32i", uc.mem_read(output, 128))
            assert max(abs(v) for v in inputs) <= 1 << 29, "coupling input exceeded quarter scale"
            x, y = (v / 2**31 for v in previous)
            expected = []
            for value in inputs:
                current = value / 2**31
                y = coupling808.B * (current-x) + coupling808.A * y
                x = current
                expected.append(y)
            active["coupling"] = dict(state=saved, input=inputs, expected=expected)
        session.at(names["x0x_808_coupling"], checked(coupling_entered))
        def receive(_uc, _at, _size, _data):
            source = word(uc.reg_read(UC_M68K_REG_A7) + 8)
            if word(source + 8) == 0 and state["phase"]:
                values = [struct.unpack(">6I",uc.mem_read(source + 36 + 24 * i,24)) for i in range(word(source + 32))]
                state["samples"].append((state["phase"],[(v[0],v[1],v[4],v[5]) for v in values]))
        session.at(names["render_body"],checked(receive))
        def tone_entered(_uc, at, _size, _data):
            capture, active = state["audio_capture"], state["active"]
            if at == names["x0x_808_tone"]:
                assert active is not None, "Tone ASM ran outside the machine callback"
                active["tone"] = True
            if capture is None or "tone_words" not in capture or active["track"] != capture["track"]:
                return
            if active["slot"] != capture["slot"] and not (capture["slot"] is None and active["fresh"]):
                return
            sp = uc.reg_read(UC_M68K_REG_A7)
            if at == names["x0x_808_body"]:
                capture["decay_words"].append(word(sp + 16))
                return
            saved, output, raw = struct.unpack(">3I", uc.mem_read(sp + 4, 12))
            assert saved == names["tone_state"] + active["slot"] * 4, "wrong voice's Tone capacitor"
            capture["tone_words"].append(raw)
            capture["dry"].extend(struct.unpack(">32i", uc.mem_read(output, 128)))
        session.at(names["x0x_808_tone"], checked(tone_entered))
        session.at(names["x0x_808_body"], checked(tone_entered))
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
            brain = word(names["x0x_dn_brain"])
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
        quiet_begin = len(session.pcm)
        wait(100)
        quiet = bytes(session.pcm[quiet_begin:])
        assert quiet and not any(quiet), "isolated 808 capture must begin with silent native output"
        capture_begin = len(session.pcm)
        body_before = state["body_nonzero"]
        session.press(session.code("9")); wait(1200)
        session.release(session.code("9")); wait(200)
        pcm = bytes(session.pcm[capture_begin:])
        assert pcm and len(pcm) % 4 == 0 and session.audio_cfg["rate"] == 48000
        pcm_peak = max(abs(v[0]) for v in struct.iter_unpack("<h", pcm))
        assert 0 < pcm_peak < 32767 and state["body_nonzero"] > body_before, "808 must reach both owned output and native stereo PCM"
        capture = FOLDER / "808-native.wav"
        with wave.open(str(capture), "wb") as wav:
            wav.setparams((2, 2, 48000, 0, "NONE", "not compressed"))
            wav.writeframes(pcm)
        report["audio"] = dict(path=str(capture), sample_rate=48000, channels=2, frames=len(pcm)//4,
                               peak_pcm16=pcm_peak, normalization="none", source="isolated native note on the 808 track")
        assert state["starts"], "native key produced no x0x START"
        report["808"] = state["starts"][-1]
        # The same isolated note at both native Decay endpoints, before adding locks or LFOs.
        response = {}
        for name, target, detents in (("short", 0, -320), ("long", 32512, 320)):
            turn("B", detents)
            assert stored()[2] == target, (name, stored())
            wait(500)
            state["phase"] = "decay-" + name
            state["audio_capture"] = dict(slot=None, words=[])
            begin = len(session.pcm)
            session.press(session.code("9")); wait(800)
            raw = state["audio_capture"]["words"]
            state["audio_capture"] = None
            native = bytes(session.pcm[begin:])
            session.release(session.code("9")); wait(300)
            values = [v[1] for phase, controls in state["samples"] if phase == "decay-" + name
                      for v in controls if v[0] == 1]
            assert values and set(values) == {target}, (name, sorted(set(values)))
            pcm_words = [v[0] for v in struct.iter_unpack("<h", native)]
            def ratio(samples, channels):
                assert len(samples) >= 36000 * channels, "decay capture is too short"
                early, late = samples[2400 * channels:7200 * channels], samples[28800 * channels:36000 * channels]
                early_power = sum(v * v for v in early) / len(early)
                assert early_power > 0, "decay capture has no attack"
                return math.sqrt(sum(v * v for v in late) / len(late) / early_power)
            response[name] = dict(raw=target, raw_late_early_rms=ratio(raw, 1),
                                  native_late_early_rms=ratio(pcm_words, 2), raw_frames=len(raw),
                                  native_frames=len(native)//4)
            for kind, data, channels, width in (("raw", struct.pack("<" + "i" * len(raw), *raw), 1, 4),
                                                ("native", native, 2, 2)):
                path = FOLDER / f"808-decay-{name}-{kind}.wav"
                with wave.open(str(path), "wb") as wav:
                    wav.setparams((channels, width, 48000, 0, "NONE", "not compressed"))
                    wav.writeframes(data)
                response[name][kind + "_path"] = str(path)
        state["phase"] = ""
        assert response["long"]["raw_late_early_rms"] > 4 * response["short"]["raw_late_early_rms"], response
        assert response["long"]["native_late_early_rms"] > 4 * response["short"]["native_late_early_rms"], response
        report["decay_response"] = response
        turn("B", -80)
        assert 0 < stored()[2] < 32512, "restore an editable Decay base for the lock scenario"
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
        tap("STOP"); tap("STOP")
        # A fresh third track has no LFO assignment from the earlier modulation check.
        session.press(session.code("T3")); wait(600); session.release(session.code("T3")); wait()
        tap("YES"); tap("RIGHT"); tap("YES"); controls()
        assert stored(2) == [80 << 8,16384,16384,16384,0], stored(2)
        tone_response, heads = {}, {}
        for name, target, detents in (("dark", 0, -320), ("bright", 32512, 320)):
            turn("A", detents)
            assert stored(2)[1] == target, (name, stored(2))
            wait(500)
            quiet_peaks = []
            # Retain exact silence and report the settling history without blocking independent checks.
            for quiet_wait in range(60):
                quiet_begin = len(session.pcm); wait(100)
                quiet = bytes(session.pcm[quiet_begin:])
                quiet_peaks.append(max(abs(v[0]) for v in struct.iter_unpack("<h", quiet)))
                if not any(quiet): break
            report["tone_pre_capture_peak_trace"] = quiet_peaks
            report["tone_pre_capture_pcm16_peak"] = quiet_peaks[-1]
            if any(quiet):
                report["tone_pre_capture_body_state"] = list(struct.unpack(">16i",uc.mem_read(names["body"],64)))
                report["tone_pre_capture_selection"] = list(struct.unpack(">24I",uc.mem_read(names["selection"],96)))
            report["tone_pre_capture_wait_ms"] = (quiet_wait+1)*100
            report["capture_baselines"]["tone_"+name] = dict(peak_pcm16=quiet_peaks[-1],
                wait_ms=(quiet_wait+1)*100, peak_trace=quiet_peaks)
            if any(quiet):
                report["failed_checks"].append("tone_"+name+"_exact_zero_baseline")
            capture = dict(track=2, slot=None, words=[], tone_words=[], decay_words=[], dry=[])
            state["audio_capture"] = capture
            begin = len(session.pcm)
            session.press(session.code("9")); wait(800)
            native = bytes(session.pcm[begin:])
            state["audio_capture"] = None
            session.release(session.code("9")); wait(300)
            raw = capture["words"]
            assert capture["tone_words"] and set(capture["tone_words"]) == {target}, capture["tone_words"]
            assert capture["decay_words"] and set(capture["decay_words"]) == {16384}, capture["decay_words"]
            assert len(raw) >= 8192 and len(capture["dry"]) == len(raw)
            assert raw[1024:8192] != capture["dry"][1024:8192], "Tone ASM did not filter the body output"
            assert native and any(native), "Tone endpoint produced no native PCM"
            heads[name] = dict(filtered=raw[1024:8192], dry=capture["dry"][1024:8192])
            tone_response[name] = dict(raw=target, decay_raw=16384, calls=len(capture["tone_words"]), raw_frames=len(raw),
                                       native_frames=len(native)//4)
            for kind, data, channels, width in (("raw", struct.pack(f"<{len(raw)}i", *raw), 1, 4),
                                                ("native", native, 2, 2)):
                path = FOLDER / f"808-tone-{name}-{kind}.wav"
                with wave.open(str(path), "wb") as wav:
                    wav.setparams((channels, width, 48000, 0, "NONE", "not compressed"))
                    wav.writeframes(data)
                tone_response[name][kind + "_path"] = str(path)
        assert heads["dark"]["dry"] == heads["bright"]["dry"], "Tone comparison changed the underlying body"
        difference = max(abs(a-b) for a,b in zip(heads["dark"]["filtered"], heads["bright"]["filtered"]))
        assert difference > 0.001 * (1 << 31), "native Tone endpoints did not change the settled filtered output"
        tone_response["max_difference_q31_after_sample_1024"] = difference
        report["tone_response"] = tone_response
        # A fresh fourth track isolates the unshaped 909 triangle from prior sounds/effects.
        tap("STOP"); tap("STOP")
        session.press(session.code("T4")); wait(600); session.release(session.code("T4")); wait()
        tap("YES"); tap("RIGHT"); tap("YES"); controls()
        assert stored(3) == [80 << 8,16384,16384,16384,0], stored(3)
        turn("F", 320)
        assert stored(3)[4] == 32512
        wait(500)
        quiet_begin = len(session.pcm); wait(100)
        quiet = bytes(session.pcm[quiet_begin:])
        baseline909 = max(abs(v[0]) for v in struct.iter_unpack("<h",quiet))
        report["capture_baselines"]["909"] = dict(peak_pcm16=baseline909, wait_ms=100)
        if any(quiet):
            report["failed_checks"].append("909_exact_zero_baseline")
        report["decay_909"] = {}
        for label, detents, raw in (("default", 0, 16384), ("short", -320, 0), ("long", 320, 32512)):
            if detents:
                turn("B", detents)
            assert stored(3)[2] == raw, stored(3)
            capture = dict(track=3, model=1, slot=None, words=[], decay_words=[])
            state["audio_capture"] = capture
            begin = len(session.pcm)
            session.press(session.code("9")); wait(800)
            native = bytes(session.pcm[begin:])
            state["audio_capture"] = None
            session.release(session.code("9")); wait(1200)
            words = capture["words"]
            assert len(words) >= 36000 and any(words), "909 raw triangle capture is missing"
            assert set(capture["decay_words"]) == {raw}, (label, capture["decay_words"])
            samples = [v/2**31 for v in words]
            error = max(abs(a-b) for a,b in zip(samples,body909.reference(len(samples),raw)))
            assert error <= 1e-5, (label,error)
            pcm_peak = max(abs(v[0]) for v in struct.iter_unpack("<h", native))
            assert 0 < pcm_peak < 32767, "909 must reach native PCM without clipping"
            audio909 = dict(raw_frames=len(words), native_frames=len(native)//4, peak_pcm16=pcm_peak,
                            decay_raw=raw, expected_tau_s=body909.decay_tau(raw), maximum_error_fs=error,
                            controls=stored(3), normalization="none", source="native 909 note",
                            pre_capture_pcm16_peak=baseline909)
            for kind, data, channels, width in (("raw", struct.pack(f"<{len(words)}i", *words), 1, 4),
                                                ("native", native, 2, 2)):
                path = FOLDER / (f"909-{kind}.wav" if label == "default" else f"909-decay-{label}-{kind}.wav")
                with wave.open(str(path), "wb") as wav:
                    wav.setparams((channels, width, 48000, 0, "NONE", "not compressed"))
                    wav.writeframes(data)
                audio909[kind + "_path"] = str(path)
            report["decay_909"][label] = audio909
        report["audio_909"] = report["decay_909"]["default"]
        assert not state["active"] and state["callbacks"] > 0 and state["body_nonzero"] > 0 and state["triangle_nonzero"] > 0
        report["render_audio"] = dict(nonzero_808_blocks=state["body_nonzero"], peak_q31=state["body_peak"],
                                      nonzero_909_blocks=state["triangle_nonzero"], peak_909_q31=state["triangle_peak"],
                                      maximum_909_reference_error_fs=state["triangle_error"])
        assert state["coupling_blocks"] > 0 and state["coupling_difference"] > 0
        report["coupling_808"] = dict(blocks=state["coupling_blocks"], maximum_entry_recurrence_error_fs=state["coupling_error"],
                                       maximum_input_output_difference_q31=state["coupling_difference"],
                                       output_bound_fs=0.5, scope="actual native call, per-voice state, START reset and entry-state recurrence")
        report.update(status="passed" if not report["failed_checks"] else "failed", callbacks=state["callbacks"], starts=state["starts"],
                      checked=["native menu/defaults", "native first-page controls", "native encoder MODEL delivery",
                               "next-START MODEL latch", "real companion fresh/settled frame",
                               "bounded nonzero 808 voice output", "native Decay changes raw and downstream decay time", "native Tone endpoints reach actual ASM and change filtered output", "808 coupling ASM after Tone with per-voice state and START reset", "909 ASM routing and analytic triangle output with native Decay endpoints", "downstream stereo PCM for both models with recorded pre-capture baselines", "other voices preserved", "native p-lock and held-lock display", "native LFO delivery", "native save/reload", "mixed 808/909 tracks"])
        if report["failed_checks"]:
            report["unqualified"].append("exact-zero native pre-capture baseline / complete downstream capture isolation")
    except (AssertionError, ValueError) as error:
        report["reason"] = str(error)
    finally:
        report["callbacks"] = state["callbacks"]
        report["starts"] = state["starts"]
        report["violations"] = state["violations"]
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
