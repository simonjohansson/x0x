"""Build the approved DN2 voice with the first 808 body and check its callback."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

from . import cpu, firmware, sharc_body808 as body, body808, tone808

ROOT = cpu.ROOT
FOLDER = ROOT / "out/dn2/silent"


def component() -> tuple[dict, bytes]:
    return body.component()


def build() -> dict:
    from elekloader import elemod, formats, link, sharc
    from elekloader.sdk import build as sdk
    from elekloader.sdk.sharc import voice_artifact

    component_report, code = component()
    entries, revision = firmware.baseline()
    stock_report = firmware.verify_entry(entries["digitone-mk2"], ROOT / "firmware", revision)
    stage = FOLDER / "mod"
    stage.mkdir(exist_ok=True)
    source_dir = ROOT / "machines/digitone2"
    manifest = json.loads((source_dir / "mod.json").read_text())
    manifest["sources"] = [str(source_dir / path) for path in manifest["sources"]]
    (stage / "mod.json").write_text(json.dumps(manifest, indent=2) + "\n")
    artifact = voice_artifact(code, bytes(body.STATE_BYTES), 0, 20, 0)
    (stage / "voice.sharc.json").write_text(json.dumps(artifact, indent=2) + "\n")
    artifacts = []
    for source in (ROOT / "vendor/elekloader/mods/core-dn2",
                   ROOT / "vendor/elekloader/mods/machines-dn2", stage):
        path, _ = sdk.build(str(source), stock_report["image"], str(FOLDER / "deps"))
        artifacts.append(path)
    mods = [elemod.load_any(path) for path in artifacts]
    stock, device, release = formats.load(stock_report["image"])
    image = formats.main_image(stock, device)
    errors = link.check(mods, image)
    if errors:
        raise AssertionError("DN2 mod does not link: " + "; ".join(errors))
    linked = link.link(mods, image, sharc_stream=stock.section(7))
    binding = next(record for record in sharc.parse(linked.sharc_stream, release.sharc)
                   if record.target == 0x20093e00)
    if binding.raw[16:] != struct.pack("<II", 0xbc8400, 20):
        raise AssertionError("installed SHARC binding does not select the approved ID20 callback")
    output = FOLDER / "x0x.syx"
    command = [sys.executable, "-m", "elekloader.patch", "--stock", stock_report["image"]]
    for artifact_path in artifacts:
        command += ["--mod", artifact_path]
    cpu.command([*command, "--out", output, "--version", "X0X0"])
    report = dict(status="passed", scope="SDK-verified first-body DN2 firmware packaging; not an emulator boot",
                  firmware=str(output), firmware_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                  stock=stock_report, component=component_report,
                  machine_id=20, sharc_entry_pc16=0xbc8400,
                  coupled_boot="not exercised by packaging",
                  unqualified=component_report["unqualified"])
    (FOLDER / "build-report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def full_os() -> dict:
    """Exercise native controls through ordinary public emulator startup APIs."""
    cpu.require_module("tools.control.digi_client", "digikit")
    from tools.control.digi_client import Emu
    from tools.emulator import digi_env, native_target
    from tools.patchkit import pk_harness as H, hook_ab
    import traceback

    package = build()
    out = FOLDER
    stock, firmware_path = Path(package["stock"]["image"]), Path(package["firmware"])
    ready = ROOT / "out/dn2/stock-ready"
    meta = ready / "SOURCE.json"
    if (
        not meta.is_file()
        or json.loads(meta.read_text())["syx_sha256"]
        != package["stock"]["image_sha256"]
    ):
        raise cpu.Unavailable(
            "prepare exact stock DN2 ready inputs with tools.emulator.ready first"
        )
    gen = digi_env.generated_dir()
    digi_env.check_generated(gen)
    binary = native_target.target_dir(gen) / "release/digi-emud"
    if not binary.is_file():
        raise cpu.Unavailable(
            "build the pinned Digikit daemon with native_emu --daemon --auto-coupled --build-only"
        )
    firmware = firmware_path
    report = dict(
        status="failed",
        scope="pinned Digikit coupled native firmware cold boot; no device",
        firmware_sha256=hashlib.sha256(firmware.read_bytes()).hexdigest(),
        elekloader_revision=package["stock"]["sdk_revision"],
        digikit_revision=cpu.revision(ROOT / "vendor/digikit"),
    )
    try:
        with Emu.spawn_coupled(
            stock, ready, binary=binary, timeout=120, run_dir=out / "native-run"
        ) as emu:
            report["stock_status"] = emu.status()
            report["load"] = emu.load(
                firmware, start="cold", base_sha256=package["stock"]["image_sha256"]
            )
            (out / "firmware-load.json").write_text(
                json.dumps(report["load"], indent=2) + "\n"
            )
            assert report["load"]["start_used"] == "cold", report["load"]
            initial = emu.status()
            assert initial["dsp"] == "sharc", initial
            start = initial["dsp_frames"]
            emu.run_until(frames=start + 100, timeout_wall_s=120)
            report["boot_status"] = emu.status()
            assert report["boot_status"]["audio"]["halted"] is None, report[
                "boot_status"
            ]
            assert report["boot_status"]["audio"]["missing_blocks"] == 0, report[
                "boot_status"
            ]
            report["binding"] = emu.dsp_peek(0x20093E00, 8)
            assert bytes.fromhex(report["binding"]["hex"]) == struct.pack(
                "<II", 0xBC8400, 20
            ), report["binding"]
            (out / "native-main.png").write_bytes(emu.frame_png())
            for name in ("FUNC", "SYN"):
                emu.button(H.button(name), True)
            emu.step(3_000_000)
            for name in ("SYN", "FUNC"):
                emu.button(H.button(name), False)
            emu.step(1_000_000)
            (out / "native-machine-menu.png").write_bytes(emu.frame_png())
            report["menu_status"] = emu.status()
            for _ in range(4):
                emu.tap(H.button("DOWN"), hold=3_000_000)
                emu.step(4_000_000)
            emu.tap(H.button("YES"), hold=3_000_000)
            emu.step(6_000_000)
            emu.tap(H.button("NO"), hold=3_000_000)
            emu.step(6_000_000)
            (out / "native-controls.png").write_bytes(emu.frame_png())
            report["selected_frame_hash"] = emu.frame_hash()
            report["before_note"] = emu.dsp_peek(0x20092000, 128)
            emu.call("pcm.tap", action="capture", path=str(out / "native-808.wav"))
            emu.midi_in(bytes([0x90, 60, 100]))
            target = emu.status()["dsp_frames"] + 750
            emu.run_until(frames=target, timeout_wall_s=120)
            report["pcm_capture"] = emu.call("pcm.tap", action="capture_stop")
            pcm = hook_ab.read_wav(out / "native-808.wav")
            assert len(pcm) > 0 and all(math.isfinite(x) for x in pcm), "invalid native PCM"
            pcm_peak = float(max(abs(pcm)))
            report["body_audio"] = dict(capture=str(out / "native-808.wav"),
                                      pcm_peak_fs=pcm_peak, sample_rate=48000,
                                      frames=len(pcm) // 2, scope="isolated native 808 note")
            assert 0 < pcm_peak < 1, "808 body did not reach bounded downstream PCM"
            report["after_note"] = emu.dsp_peek(0x20092000, 128)
            report["callback_frame"] = emu.dsp_peek(0x20093D00, 20)
            report["callback_params"] = emu.dsp_peek(0x20093D14, 160)
            state = struct.unpack("<32I", bytes.fromhex(report["after_note"]["hex"]))
            assert any(state[2 * i] > 0 and state[2 * i + 1] == 1 for i in range(16)), (
                state
            )
            frame = struct.unpack("<5I", bytes.fromhex(report["callback_frame"]["hex"]))
            output_base = frame[0] - 128 * frame[1]
            report["voice_outputs"] = {
                str(i): emu.dsp_peek(output_base + 128 * i, 128)
                for i in range(16)
                if state[2 * i] > 0
            }
            def check_outputs(outputs, selections, require_body=False):
                audible = False
                for key, value in outputs.items():
                    samples = struct.unpack("<32f", bytes.fromhex(value["hex"]))
                    assert all(math.isfinite(x) and abs(x) < .5 for x in samples), (key, samples)
                    if selections[2 * int(key) + 1] == 2:
                        assert samples == (0.0,) * 32, "909 branch must remain silent"
                    elif any(samples):
                        audible = True
                if require_body:
                    assert audible, "no nonzero actual 808 callback output"
            check_outputs(report["voice_outputs"], state, require_body=True)
            controls = struct.unpack(
                "<40I", bytes.fromhex(report["callback_params"]["hex"])
            )
            assert [controls[i] for i in (0, 1, 2, 5)] == [16384, 16384, 16384, 0], (
                controls
            )
            names = {
                k: int(v, 0)
                for k, v in json.loads((out / "x0x.syx.map.json").read_text()).items()
            }
            cc = {
                str(k): (emu.peek32(names["dn2_t1"] + 60 * (321 + k) + 24) >> 16)
                & 0xFFFF
                for k in (0, 1, 2, 5)
            }
            report["native_cc"] = cc
            assert all(v < 128 for v in cc.values()), cc
            edits = {0: 100, 1: 10, 2: 80}
            emu.midi_in(bytes(v for k, value in edits.items()
                              for v in (0xB0, cc[str(k)], value)))
            emu.run_until(frames=emu.status()["dsp_frames"] + 300, timeout_wall_s=120)
            edited = struct.unpack(
                "<40I", bytes.fromhex(emu.dsp_peek(0x20093D14, 160)["hex"])
            )
            report["ordinary_abc_edits"] = {
                "cc_targets": {str(k): v << 8 for k, v in edits.items()},
                "delivered": {str(k): edited[k] for k in edits},
            }
            packed = struct.unpack("<40H", bytes.fromhex(
                emu.dsp_peek(0x25C48C + 2*0x6D, 80)["hex"]))
            report["ordinary_abc_edits"]["native_frame"] = [packed[k] for k in edits]
            assert [packed[k] for k in edits] == [edited[k] for k in edits], packed
            # The native smoother retains fractions; test distinct routing, not instantaneous settling.
            assert edited[0] > edited[2] > 16384 > edited[1], report["ordinary_abc_edits"]
            assert edited[5] == 0, edited
            emu.midi_in(bytes([0xB0, cc["5"], 127]))
            emu.run_until(frames=emu.status()["dsp_frames"] + 100, timeout_wall_s=120)
            pending = struct.unpack(
                "<32I", bytes.fromhex(emu.dsp_peek(0x20092000, 128)["hex"])
            )
            report["pending_state"] = list(pending)
            assert not any(pending[2 * i + 1] == 2 for i in range(16)), pending
            emu.midi_in(bytes([0x80, 60, 0]))
            emu.run_until(frames=emu.status()["dsp_frames"] + 30, timeout_wall_s=120)
            emu.midi_in(bytes([0x90, 60, 100]))
            emu.run_until(frames=emu.status()["dsp_frames"] + 100, timeout_wall_s=120)
            changed = struct.unpack(
                "<32I", bytes.fromhex(emu.dsp_peek(0x20092000, 128)["hex"])
            )
            report["changed_state"] = list(changed)
            assert any(
                changed[2 * i] > 0 and changed[2 * i + 1] == 2 for i in range(16)
            ), changed
            for i in range(16):
                if pending[2 * i] and pending[2 * i + 1] == 1:
                    assert changed[2 * i] > pending[2 * i] and changed[2 * i + 1] == 1, changed
            report["switched_voice_outputs"] = {
                str(i): emu.dsp_peek(output_base + 128 * i, 128)
                for i in range(16) if changed[2 * i] > 0
            }
            check_outputs(report["switched_voice_outputs"], changed)
            (out / "native-model-909.png").write_bytes(emu.frame_png())

            def chord(*buttons):
                for name in buttons:
                    emu.button(H.button(name), True)
                emu.step(3_000_000)
                for name in reversed(buttons):
                    emu.button(H.button(name), False)
                emu.step(1_000_000)

            def tap(name):
                emu.tap(H.button(name), hold=3_000_000)
                emu.step(4_000_000)

            tap("MOD")
            emu.turn(H.encoder("ENC D"), 1)
            emu.step(4_000_000)
            tap("DOWN")
            tap("YES")
            for _ in range(30):
                emu.turn(H.encoder("ENC H"), 4)
                emu.step(264_000)
            emu.step(13_200_000)
            (out / "native-lfo-tntun.png").write_bytes(emu.frame_png())
            report["lfo_tntun"] = []
            for _ in range(4):
                emu.run_until(frames=emu.status()["dsp_frames"] + 100, timeout_wall_s=120)
                ids = struct.unpack("<16H", bytes.fromhex(
                    emu.dsp_peek(0x25C48C + 2*74, 32)["hex"]))
                last = max(i for i in range(16) if ids[i] == 20)
                native = struct.unpack("<40H", bytes.fromhex(
                    emu.dsp_peek(0x25C48C + 2*(0x6D + 0x49*last), 80)["hex"]))
                delivered = struct.unpack("<40I", bytes.fromhex(
                    emu.dsp_peek(0x20093D14, 160)["hex"]))
                report["lfo_tntun"].append({"slot": last, "native": list(native),
                                            "delivered": list(delivered)})
                assert native == delivered, (native, delivered)
                assert [delivered[k] for k in (1, 2, 5)] == [2560, 20480, 32512], delivered
            assert len({row["delivered"][0] for row in report["lfo_tntun"]}) > 1, report["lfo_tntun"]
            emu.midi_in(bytes([0xB0, 109, 64]))
            emu.run_until(frames=emu.status()["dsp_frames"] + 300, timeout_wall_s=120)
            tap("SYN")
            chord("TRK", "TRIG 2")
            chord("FUNC", "SYN")
            for _ in range(4):
                tap("DOWN")
            tap("YES")
            tap("NO")
            (out / "native-track2-x0x.png").write_bytes(emu.frame_png())
            emu.midi_in(bytes([0x91, 62, 100]))
            emu.run_until(frames=emu.status()["dsp_frames"] + 100, timeout_wall_s=120)
            mixed = struct.unpack(
                "<32I", bytes.fromhex(emu.dsp_peek(0x20092000, 128)["hex"])
            )
            report["mixed_track_state"] = list(mixed)
            assert any(mixed[2*i] > 0 and mixed[2*i+1] == 1 and changed[2*i] == 0
                       for i in range(16)), mixed
            assert all(mixed[2*i] > changed[2*i] and mixed[2*i+1] == 2
                       for i in range(16) if changed[2*i+1] == 2), mixed
            report["mixed_voice_outputs"] = {
                str(i): emu.dsp_peek(output_base + 128*i, 128)
                for i in range(16) if mixed[2*i] > 0
            }
            check_outputs(report["mixed_voice_outputs"], mixed, require_body=True)
            new_lanes = [i for i in range(16) if mixed[2*i] and not changed[2*i]]
            report["track2_voice_params"] = {
                str(i): list(struct.unpack("<40H", bytes.fromhex(
                    emu.dsp_peek(0x25C48C + 2*(0x6D + 0x49*i), 80)["hex"])))
                for i in new_lanes
            }
            assert all([p[k] for k in (0, 1, 2, 5)] == [16384, 16384, 16384, 0]
                       for p in report["track2_voice_params"].values()), report["track2_voice_params"]
            chord("TRK", "TRIG 3")
            (out / "native-track3-stock.png").write_bytes(emu.frame_png())
            emu.midi_in(bytes([0x92, 65, 100]))
            emu.run_until(frames=emu.status()["dsp_frames"] + 100, timeout_wall_s=120)
            ids = struct.unpack("<16H", bytes.fromhex(
                emu.dsp_peek(0x25C48C + 2*74, 32)["hex"]))
            pitches = struct.unpack("<16H", bytes.fromhex(
                emu.dsp_peek(0x25C48C + 2, 32)["hex"]))
            stock_lanes = [i for i in range(16) if ids[i] == 0 and pitches[i] == 65 << 8]
            assert stock_lanes, (ids, pitches)
            report["stock_track_voice_outputs"] = {
                str(i): emu.dsp_peek(output_base + 128*i, 128) for i in stock_lanes
            }
            stock_samples = [sample for v in report["stock_track_voice_outputs"].values()
                             for sample in struct.unpack("<32f", bytes.fromhex(v["hex"]))]
            assert all(math.isfinite(sample) for sample in stock_samples), report["stock_track_voice_outputs"]
            assert any(stock_samples), report["stock_track_voice_outputs"]
            stock_state = struct.unpack("<32I", bytes.fromhex(
                emu.dsp_peek(0x20092000, 128)["hex"]))
            assert all(stock_state[2*i:2*i+2] == (0, 0) for i in stock_lanes), stock_state
            chord("TRK", "TRIG 2")
            chord("FUNC", "YES")
            emu.run_until(frames=emu.status()["dsp_frames"] + 100, timeout_wall_s=120)
            emu.midi_in(bytes([0xB1, cc["0"], 10, 0xB1, cc["5"], 127]))
            emu.run_until(frames=emu.status()["dsp_frames"] + 100, timeout_wall_s=120)
            report["temporary_pattern_edited"] = {
                str(i): list(struct.unpack("<40H", bytes.fromhex(
                    emu.dsp_peek(0x25C48C + 2*(0x6D + 0x49*i), 80)["hex"])))
                for i in new_lanes
            }
            assert all(p[0] < 16384 and p[5] > 16384
                       for p in report["temporary_pattern_edited"].values()), report["temporary_pattern_edited"]
            (out / "native-temp-edited.png").write_bytes(emu.frame_png())
            chord("FUNC", "NO")
            emu.run_until(frames=emu.status()["dsp_frames"] + 100, timeout_wall_s=120)
            (out / "native-temp-reloaded.png").write_bytes(emu.frame_png())
            emu.midi_in(bytes([0x81, 62, 0, 0x91, 62, 100]))
            emu.run_until(frames=emu.status()["dsp_frames"] + 100, timeout_wall_s=120)
            restored = struct.unpack("<32I", bytes.fromhex(
                emu.dsp_peek(0x20092000, 128)["hex"]))
            restored_lanes = [i for i in range(16) if restored[2*i] and not stock_state[2*i]]
            report["temporary_pattern_reload"] = {
                "state": list(restored),
                "params": {
                    str(i): list(struct.unpack("<40H", bytes.fromhex(
                        emu.dsp_peek(0x25C48C + 2*(0x6D + 0x49*i), 80)["hex"])))
                    for i in restored_lanes
                },
            }
            assert restored_lanes and all(restored[2*i+1] == 1 for i in restored_lanes), restored
            assert all([p[k] for k in (0, 1, 2, 5)] == [16384, 16384, 16384, 0]
                       for p in report["temporary_pattern_reload"]["params"].values()), report["temporary_pattern_reload"]
            chord("FUNC", "SETTINGS")
            tap("YES")
            tap("YES")
            emu.run_until(frames=emu.status()["dsp_frames"] + 2000, timeout_wall_s=120)
            (out / "native-project-save.png").write_bytes(emu.frame_png())
            tap("NO")
            chord("TRK", "TRIG 1")
            tap("SYN")
            chord("FUNC", "SYN")
            for _ in range(4):
                tap("UP")
            tap("YES")
            tap("NO")
            emu.midi_in(bytes([0xB0, 40, 10, 0x80, 60, 0, 0x90, 69, 100]))
            emu.run_until(frames=emu.status()["dsp_frames"] + 100, timeout_wall_s=120)
            ids = struct.unpack("<16H", bytes.fromhex(
                emu.dsp_peek(0x25C48C + 2*74, 32)["hex"]))
            pitches = struct.unpack("<16H", bytes.fromhex(
                emu.dsp_peek(0x25C48C + 2, 32)["hex"]))
            report["before_persistent_reload"] = {"ids": list(ids), "pitches": list(pitches)}
            assert any(ids[i] == 0 and pitches[i] == 69 << 8 for i in range(16)), (ids, pitches)
            (out / "native-project-edited.png").write_bytes(emu.frame_png())
            tap("SETTINGS")
            emu.step(26_400_000)
            tap("YES")
            emu.step(26_400_000)
            tap("YES")
            emu.step(66_000_000)
            (out / "native-project-list.png").write_bytes(emu.frame_png())
            tap("YES")
            emu.step(132_000_000, timeout_wall_s=120)
            (out / "native-project-confirm.png").write_bytes(emu.frame_png())
            tap("YES")
            emu.step(396_000_000, timeout_wall_s=120)
            (out / "native-project-reloaded.png").write_bytes(emu.frame_png())
            emu.midi_in(bytes([0x80, 69, 0, 0x90, 67, 100]))
            emu.run_until(frames=emu.status()["dsp_frames"] + 100, timeout_wall_s=120)
            ids = struct.unpack("<16H", bytes.fromhex(
                emu.dsp_peek(0x25C48C + 2*74, 32)["hex"]))
            pitches = struct.unpack("<16H", bytes.fromhex(
                emu.dsp_peek(0x25C48C + 2, 32)["hex"]))
            state = struct.unpack("<32I", bytes.fromhex(
                emu.dsp_peek(0x20092000, 128)["hex"]))
            reloaded_lanes = [i for i in range(16) if ids[i] == 20 and pitches[i] == 67 << 8]
            report["persistent_project_reload"] = {
                "scope": "native project save/reload in this emulator session; no power cycle",
                "state": list(state),
                "params": {
                    str(i): list(struct.unpack("<40H", bytes.fromhex(
                        emu.dsp_peek(0x25C48C + 2*(0x6D + 0x49*i), 80)["hex"])))
                    for i in reloaded_lanes
                },
            }
            assert reloaded_lanes and all(state[2*i] and state[2*i+1] == 2
                                          for i in reloaded_lanes), (ids, pitches, state)
            assert all([p[k] for k in (0, 1, 2, 5)] == [25600, 2560, 20480, 32512]
                       for p in report["persistent_project_reload"]["params"].values()), report["persistent_project_reload"]
            tap("NO")
            tap("NO")
            chord("TRK", "TRIG 2")
            tap("SYN")
            emu.midi_in(bytes([0x80, 60, 0, 0x80, 67, 0, 0x81, 62, 0, 0x82, 65, 0]))
            emu.run_until(frames=emu.status()["dsp_frames"] + 300, timeout_wall_s=120)
            tap("RECORD")
            tap("TRIG 1")
            emu.button(H.button("TRIG 1"), True)
            emu.step(3_000_000)
            for _ in range(30):
                emu.turn(H.encoder("ENC A"), 4)
                emu.step(264_000)
            emu.step(13_200_000)
            (out / "native-plock-held.png").write_bytes(emu.frame_png())
            emu.button(H.button("TRIG 1"), False)
            emu.step(4_000_000)
            tap("RECORD")
            tap("PLAY")
            emu.run_until(frames=emu.status()["dsp_frames"] + 50, timeout_wall_s=120)
            ids = struct.unpack("<16H", bytes.fromhex(
                emu.dsp_peek(0x25C48C + 2*74, 32)["hex"]))
            pitches = struct.unpack("<16H", bytes.fromhex(
                emu.dsp_peek(0x25C48C + 2, 32)["hex"]))
            state = struct.unpack("<32I", bytes.fromhex(
                emu.dsp_peek(0x20092000, 128)["hex"]))
            locked = {
                str(i): list(struct.unpack("<40H", bytes.fromhex(
                    emu.dsp_peek(0x25C48C + 2*(0x6D + 0x49*i), 80)["hex"])))
                for i in range(16) if ids[i] == 20 and pitches[i] == 60 << 8
            }
            report["sequencer_plock"] = {"state": list(state), "params": locked}
            assert any(p[0] > 16384 and [p[k] for k in (1, 2, 5)] == [16384, 16384, 0]
                       and state[2*int(i)] and state[2*int(i)+1] == 1
                       for i, p in locked.items()), report["sequencer_plock"]
            tap("STOP")
            emu.midi_in(bytes([0x91, 70, 100]))
            emu.run_until(frames=emu.status()["dsp_frames"] + 100, timeout_wall_s=120)
            pitches = struct.unpack("<16H", bytes.fromhex(
                emu.dsp_peek(0x25C48C + 2, 32)["hex"]))
            base = {
                str(i): list(struct.unpack("<40H", bytes.fromhex(
                    emu.dsp_peek(0x25C48C + 2*(0x6D + 0x49*i), 80)["hex"])))
                for i in range(16) if pitches[i] == 70 << 8
            }
            report["unlocked_base_after_plock"] = base
            assert base and all([p[k] for k in (0, 1, 2, 5)] == [16384, 16384, 16384, 0]
                                for p in base.values()), base
            # Read actual per-voice quadrature energy across a held native note.
            report["decay_audio"] = {}
            for label, position, note in (("short", 0, 72), ("long", 127, 73)):
                emu.midi_in(bytes([0x81, 70, 0, 0xB1, cc["1"], position]))
                emu.run_until(frames=emu.status()["dsp_frames"] + 600, timeout_wall_s=120)
                path = out / f"decay-{label}-native.wav"
                emu.call("pcm.tap", action="capture", path=str(path))
                emu.midi_in(bytes([0x91, note, 100]))
                emu.run_until(frames=emu.status()["dsp_frames"] + 100, timeout_wall_s=120)
                ids = struct.unpack("<16H", bytes.fromhex(emu.dsp_peek(0x25C48C + 2*74, 32)["hex"]))
                pitches = struct.unpack("<16H", bytes.fromhex(emu.dsp_peek(0x25C48C + 2, 32)["hex"]))
                lanes = [i for i in range(16) if ids[i] == 20 and pitches[i] == note << 8]
                assert len(lanes) == 1, (label, lanes)
                lane = lanes[0]
                def body_snapshot():
                    metadata = struct.unpack("<2I", bytes.fromhex(emu.dsp_peek(0x20092000 + 8*lane, 8)["hex"]))
                    xy = struct.unpack("<2f", bytes.fromhex(emu.dsp_peek(0x20092080 + 8*lane, 8)["hex"]))
                    native = struct.unpack("<40H", bytes.fromhex(
                        emu.dsp_peek(0x25C48C + 2*(0x6D + 0x49*lane), 80)["hex"]))
                    assert metadata[1] == 1 and all(math.isfinite(x) for x in xy), (metadata, xy)
                    energy = sum(x*x for x in xy)
                    assert energy > 0
                    return dict(callbacks=metadata[0], energy=energy, decay_raw=native[1])
                early = body_snapshot()
                emu.run_until(frames=emu.status()["dsp_frames"] + 500, timeout_wall_s=120)
                late = body_snapshot()
                emu.call("pcm.tap", action="capture_stop")
                pcm = hook_ab.read_wav(path)
                assert len(pcm) >= 28800 and all(math.isfinite(x) for x in pcm), label
                peak = float(max(abs(pcm)))
                assert 0 < peak < 1, (label, peak)
                dt = (late["callbacks"] - early["callbacks"]) * 32 / 48000
                ratio = late["energy"] / early["energy"]
                assert dt > 0 and 0 < ratio < 1, (label, early, late)
                first = sum(float(x)*float(x) for x in pcm[:9600])
                tail = sum(float(x)*float(x) for x in pcm[19200:28800])
                report["decay_audio"][label] = dict(target=position, slot=lane, early=early, late=late,
                    raw_state_energy_ratio=ratio, measured_tau_s=-2*dt/math.log(ratio),
                    pcm_peak_fs=peak, native_late_early_energy_ratio=tail/first,
                    native_wav=str(path))
                emu.midi_in(bytes([0x81, note, 0]))
            assert (report["decay_audio"]["long"]["measured_tau_s"] >
                    4 * report["decay_audio"]["short"]["measured_tau_s"]), report["decay_audio"]
            assert (report["decay_audio"]["long"]["native_late_early_energy_ratio"] >
                    4 * report["decay_audio"]["short"]["native_late_early_energy_ratio"]), report["decay_audio"]
            emu.midi_in(bytes([0xB1, cc["1"], 64]))
            tap("STOP"); tap("STOP")
            report["tone_audio"] = {}
            for label, position, note in (("dark", 0, 74), ("bright", 127, 75)):
                emu.midi_in(bytes([0xB1, cc["0"], position, 0xB1, cc["1"], 64]))
                emu.run_until(frames=emu.status()["dsp_frames"] + 600, timeout_wall_s=120)
                path = out / f"tone-{label}-native.wav"
                emu.call("pcm.tap", action="capture", path=str(path))
                emu.midi_in(bytes([0x91, note, 100]))
                emu.run_until(frames=emu.status()["dsp_frames"] + 150, timeout_wall_s=120)
                ids = struct.unpack("<16H", bytes.fromhex(emu.dsp_peek(0x25C48C + 2*74,32)["hex"]))
                pitches = struct.unpack("<16H", bytes.fromhex(emu.dsp_peek(0x25C48C + 2,32)["hex"]))
                lanes=[i for i in range(16) if ids[i]==20 and pitches[i]==note<<8]
                assert len(lanes)==1, (label,lanes)
                lane=lanes[0]
                native=struct.unpack("<40H",bytes.fromhex(
                    emu.dsp_peek(0x25C48C+2*(0x6D+0x49*lane),80)["hex"]))
                assert abs(native[0]-(position<<8))<=1 and native[1]==16384 and native[5]==0, native
                x,y=struct.unpack("<2f",bytes.fromhex(emu.dsp_peek(0x20092080+8*lane,8)["hex"]))
                capacitor=struct.unpack("<f",bytes.fromhex(emu.dsp_peek(0x20092100+4*lane,4)["hex"]))[0]
                g=tone808.coefficient(native[0])
                pole=body808.retention(native[1])*complex(
                    math.cos(2*math.pi*55/48000),math.sin(2*math.pi*55/48000))
                expected=(2*g/(1-(1-2*g)/pole)*complex(y,x)).imag
                error=abs(capacitor-expected)
                assert math.isfinite(capacitor) and error<=1e-5, (label,capacitor,expected,error)
                emu.run_until(frames=emu.status()["dsp_frames"]+150,timeout_wall_s=120)
                emu.call("pcm.tap",action="capture_stop")
                pcm=hook_ab.read_wav(path)
                peak=float(max(abs(pcm)))
                assert all(math.isfinite(v) for v in pcm) and 0<peak<1, label
                report["tone_audio"][label]=dict(target=position,slot=lane,tone_raw=native[0],
                    decay_raw=native[1],coefficient=g,capacitor=capacitor,
                    predicted_settled_capacitor=expected,state_error_fs=error,
                    native_peak_fs=peak,native_wav=str(path))
                emu.midi_in(bytes([0x81,note,0]))
            assert report["tone_audio"]["bright"]["coefficient"] > 10*report["tone_audio"]["dark"]["coefficient"]
            emu.midi_in(bytes([0xB1,cc["0"],64]))
            report["final_status"] = emu.status()
            final = report["final_status"]
            assert final["cf"]["ready"] and final["cf"]["error"] is None, final
            assert final["dsp"] == "sharc" and final["audio"]["halted"] is None, final
            assert final["audio"]["missing_blocks"] == 0, final
            report["status"] = "passed"
    except Exception as error:
        report["error"] = str(error)
        report["traceback"] = traceback.format_exc()
    report["unqualified"] = [
        "persistence across emulator/device restart",
        "808 circuit fidelity and pot calibration",
        "909 audio and real-device timing",
    ]
    (out / "native-boot-report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--build", action="store_true", help="also package latest-OS first-body firmware"
    )
    mode.add_argument(
        "--full-os",
        action="store_true",
        help="run the installed first-body mod in coupled Digikit",
    )
    args = parser.parse_args()
    try:
        report = (
            full_os() if args.full_os else build() if args.build else component()[0]
        )
        print(json.dumps(report))
        return int(report["status"] != "passed")
    except cpu.Unavailable as error:
        print(json.dumps(dict(status="unavailable", reason=str(error))))
        return 77


if __name__ == "__main__":
    sys.exit(main())
