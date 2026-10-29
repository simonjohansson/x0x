"""Bounded native-panel smoke of the normal DT1/DN1 mod packages."""

from pathlib import Path
import contextlib
import ctypes
import json
import os
import struct
import time
import wave
from . import build, cpu, coldfire_field808 as dsp, coldfire_field909 as dsp909


def smoke(device="dt"):
    folder = cpu.ROOT / "out" / device
    cpu.require_module("emu.session", "digiemu")
    from emu.bootstrap import first_run
    from emu.fwcheck import prepare
    from emu.longrun import never_fake_set_posts
    from emu.session import Session
    from emu import panel
    from unicorn.m68k_const import UC_M68K_REG_A7

    folder = Path(folder)
    built = build.build(device, folder)
    session = None
    report = dict(
        status="failed",
        scope=device
        + " normal-package full-OS wiring smoke; no physical or platform-wide qualification",
        trigger_source="native panel trig 1"
        if device == "dt"
        else "native panel trig 9",
        package=built,
        emulator_revision=cpu.revision(cpu.ROOT / "vendor/digiemu"),
        hle=False,
    )
    try:
        with (folder / "boot.log").open("w") as log, contextlib.redirect_stdout(log):
            paths, profile = prepare(built["firmware"], str(folder / "cache"))
            assert profile.short == ("dt1" if device == "dt" else "dn1")
            os.environ.update(paths.env())
            began = time.monotonic()
            snap = first_run(paths, cancel=lambda: time.monotonic() - began > 120)
            session = Session(snap, paths.syx, hle=False)
            never_fake_set_posts(session.m, session.ev, session.profile.set_post)
        names = json.loads((folder / "link-map.json").read_text())
        uc = session.m.uc
        names = {k: int(v, 0) if isinstance(v, str) else v for k, v in names.items()}
        oracles = {1: dsp.Reference(folder / "integer-reference"),
                   2: dsp909.Reference(folder / 'integer-reference909')}
        references = [(ctypes.c_int32 * dsp.WORDS)() for _ in range(8)]
        active = None
        returns = set()
        checks = dict(callbacks=0, starts=0, nonzero_blocks=0, render_notifications=0)
        failures = []
        report["checks"] = checks
        report["failures"] = failures
        checks['by_model'] = {kind: dict(callbacks=0, starts=0, start_controls=[])
                              for kind in (1, 2)}

        def checked(fn):
            def hook(*args):
                if failures:
                    return
                try:
                    fn(*args)
                except Exception as e:
                    failures.append(repr(e))
                    session.halted = "mod smoke: " + repr(e)
                    uc.emu_stop()

            return hook

        def returned(_uc, pc, *_):
            nonlocal active
            if active is None or pc != active[-1]:
                return
            owner, out, slot, expected, kind, _ret = active
            actual = list(struct.unpack(">32i", uc.mem_read(out, 128)))
            assert actual == expected, (
                "Native callback output differs from integer reference"
            )
            assert bytes(uc.mem_read(owner, dsp.WORDS * 4)) == struct.pack(
                ">352i", *references[slot]
            ), "Native callback state differs"
            checks["callbacks"] += 1
            checks['by_model'][kind]['callbacks'] += 1
            checks["nonzero_blocks"] += int(any(actual))
            active = None

        def entered(kind, *_):
            nonlocal active
            assert active is None, "Nested mod callback"
            sp = uc.reg_read(UC_M68K_REG_A7)
            ret = int.from_bytes(uc.mem_read(sp, 4), "big")
            owner, out, start, tone, decay, extra = struct.unpack(
                ">6I", uc.mem_read(sp + 4, 24)
            )
            slot, offset = divmod(owner - names["voices"] - 4, (dsp.WORDS + 1) * 4)
            assert (
                offset == 0
                and 0 <= slot < 8
                and out
                == names["fw_track_blocks" if device == "dt" else "fw_voices"]
                + 128 * slot
            )
            assert ret in returns, ("Unobserved caller return", hex(ret))
            reference = oracles[kind]
            reference.state = references[slot]
            expected = (reference.call(tone, decay, start, model=extra) if kind == 1
                        else reference.call(tone, extra, decay, start))
            checks["starts"] += int(bool(start))
            if start:
                controls = dict(tone=tone, decay=decay, attack=extra if kind == 2 else None)
                checks['by_model'][kind]['starts'] += 1
                checks['by_model'][kind]['start_controls'].append(controls)
            active = (owner, out, slot, expected, kind, ret)

        # Install return probes before execution: adding a hook at entry can
        # invalidate the current Unicorn block and report the same entry twice.
        start = built["linked_layout"]["sections"]["x0x .run"]
        symbol = next(
            line.split()
            for line in cpu.command(
                ["m68k-elf-nm", "-S", folder / "deps/x0x.work/field808.s.o"]
            ).splitlines()
            if line.split()[-1:] == ["x0x_field808"]
        )
        end = names["x0x_field808"] + int(symbol[1], 16)
        code = bytes(uc.mem_read(start, end - start))
        for i in range(0, len(code) - 1, 2):
            op = int.from_bytes(code[i : i + 2], "big")
            length = 0
            if op & 0xFFF8 == 0x4E90:
                length = 2
            elif op == 0x4EB9:
                length = 6
            elif op >> 8 == 0x61:
                length = 4 if op & 255 == 0 else 6 if op & 255 == 255 else 2
            if length:
                returns.add(start + i + length)
        for ret in returns:
            session.at(ret, checked(returned))
        session.at(names['x0x_field808'], checked(lambda *args: entered(1, *args)))
        session.at(names['x0x_field909'], checked(lambda *args: entered(2, *args)))

        def notified(*_):
            checks["render_notifications"] += 1

        session.at(
            names["x0x_dt_render" if device == "dt" else "x0x_dn_begin"], notified
        )

        def wait(ms=80):
            session.run_ms(ms)
            assert not session.halted and not failures, (session.halted, failures)

        def tap(key):
            session.tap(session.code(key), hold_ms=40, after_ms=80)
            assert not session.halted

        def endpoint(knob, direction):
            # Drain each bounded encoder packet before raising the next panel interrupt.
            for _ in range(64):
                session.turn(session.encoder(knob), 16 if direction > 0 else -16, after_ms=20)
                assert not session.halted and not failures, (session.halted, failures)

        # Verified native menu sequences, sent in one bounded script.
        wait()
        if device == "dt":
            session.press(session.code("FUNC"))
            wait(40)
            tap("SRC")
            session.release(session.code("FUNC"))
            wait(40)
            for _ in range(4):
                tap("DOWN")
            tap("YES")
            sound = int.from_bytes(uc.mem_read(names["fw_kit"], 4), "big") + 0x20
            assert bytes(uc.mem_read(sound + 126, 1)) == bytes([20]), (
                "X0X machine not selected"
            )
        else:
            session.press(session.code("T1"))
            wait(600)
            session.release(session.code("T1"))
            wait()
            tap("YES")
            tap("RIGHT")
            tap("YES")
            kit = int.from_bytes(uc.mem_read(names["fw_kit"], 4), "big")
            assert int.from_bytes(uc.mem_read(kit + 0x2C, 2), "big") == 20 << 8, (
                "X0X machine not selected"
            )
        tap('SRC' if device == 'dt' else 'SYN2')
        cases = []
        report['cases'] = cases
        for name, kind, model_turn, attack_turn, expected_attack in (
            ('808', 1, -127, 0, None),
            ('909-attack-min', 2, 127, -127, 0),
            ('909-attack-max', 2, 0, 127, 32512),
            ('808-return', 1, -127, 0, None),
        ):
            if cases:
                # Finish the isolated tail before the next native UI edit.
                wait(6000)
            if model_turn:
                endpoint('F', model_turn)
            if attack_turn:
                endpoint('C', attack_turn)
            before = checks['by_model'][kind]['starts']
            pcm_start = len(session.pcm)
            tap('1' if device == 'dt' else '9')
            wait(250)
            # A time budget may stop inside the callback; finish that observation.
            for _ in range(20):
                if active is None:
                    break
                wait(0.05)
            pcm = bytes(session.pcm[pcm_start:])
            peak = max(abs(x) for x in struct.unpack('<'+'h'*(len(pcm)//2), pcm))
            assert checks['by_model'][kind]['starts'] > before and peak > 0 and active is None, (name, checks)
            controls = checks['by_model'][kind]['start_controls'][-1]
            if expected_attack is not None:
                assert controls['attack'] == expected_attack, (name, controls)
            cases.append(dict(name=name, model=kind, controls=controls, pcm_peak_int16=peak, pcm_frames=len(pcm)//4))
            with wave.open(str(folder/f'native-{name}.wav'), 'wb') as f:
                f.setparams((2, 2, session.audio_cfg['rate'], 0, 'NONE', 'not compressed'))
                f.writeframes(pcm)
        if device == "dt":
            report["render_machine_bytes"] = bytes(
                uc.mem_read(names["fw_render_machine"], 8)
            ).hex()
        assert (
            checks["starts"]
            and checks["nonzero_blocks"]
            and peak > 0
            and active is None
        ), checks
        if session.frames:
            panel.write_png(
                session.frames[-1][1], str(folder / "selected.png"), scale=4
            )
        report.update(
            status="passed",
            machine_id=20,
            checks=checks,
            pcm_peak_int16=peak,
            pcm_frames=len(pcm) // 4,
            sample_rate=session.audio_cfg["rate"],
            failures=failures,
        )
    finally:
        if session is not None:
            if session.frames:
                panel.write_png(
                    session.frames[-1][1], str(folder / "last-screen.png"), scale=4
                )
            session.close()
        (folder / "smoke.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("device", choices=("dt", "dn"))
    print(json.dumps(smoke(p.parse_args().device)))
