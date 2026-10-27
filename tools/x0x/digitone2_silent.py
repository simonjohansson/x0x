"""Build the approved DN2 voice with provisional 808/909 bodies and check its callback."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import time

from . import cpu, firmware, sharc_body808 as body, body808, body909, tone808, leakage808, tune909, vca909

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
            counters=struct.unpack("<16I",bytes.fromhex(emu.dsp_peek(0x200921c0,64)["hex"]))
            assert counters == (0,)*16, counters
            report["excitation_808"] = dict(pulse_samples=body808.PULSE_SAMPLES,initial_frequency_samples=body808.ATTACK_SAMPLES,counters_after_settled_note=list(counters),
                scope="native initial counter consumed; separate 1 ms drive / 6 ms frequency timing is actual-ASM component proof")
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
            def check_outputs(outputs, selections, required_models=()):
                audible = set()
                verified_909 = {}
                for key, value in outputs.items():
                    slot = int(key)
                    model = selections[2 * slot + 1]
                    samples = struct.unpack("<32f", bytes.fromhex(value["hex"]))
                    assert all(math.isfinite(x) and abs(x) < .5 for x in samples), (key, samples)
                    assert model in (1, 2), (key, model)
                    if model == 2:
                        phase, c8 = struct.unpack("<If", bytes.fromhex(
                            emu.dsp_peek(0x20092080 + 8*slot, 8)["hex"]))
                        c9 = struct.unpack("<f", bytes.fromhex(
                            emu.dsp_peek(0x20092200 + 4*slot, 4)["hex"]))[0]
                        remaining = struct.unpack("<I", bytes.fromhex(
                            emu.dsp_peek(0x200921C0 + 4*slot, 4)["hex"]))[0]
                        assert math.isfinite(c8) and 0 <= c8 <= vca909.SOURCE_V*vca909.STATE_SCALE, (slot,c8)
                        assert math.isfinite(c9) and 0 <= c9 <= tune909.CHARGE_V/tune909.SUPPLY_V, (slot,c9)
                        assert remaining <= tune909.TRIGGER_SAMPLES, (slot,remaining)
                        verified_909[key] = dict(phase=phase, c8_encoded=c8,
                                                c8_voltage_v=c8/vca909.STATE_SCALE,
                                                audio_gain_fs=max(c8-vca909.BASE_V*vca909.STATE_SCALE,0),
                                                c9_normalized=c9,trigger_remaining=remaining)
                    if any(samples):
                        audible.add(model)
                assert set(required_models) <= audible, (required_models, audible)
                return dict(nonzero_models=sorted(audible), body909_state=verified_909,
                            buffer_stage="downstream voice buffer after stock envelope/filter processing")
            report["voice_output_checks"] = check_outputs(report["voice_outputs"], state, (1,))
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
            report["switched_output_checks"] = check_outputs(report["switched_voice_outputs"], changed, (2,))
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
            # A finite C8 tail ends during the UI setup; excite both models together.
            emu.midi_in(bytes([0x90,63,100,0x91,62,100]))
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
            report["mixed_output_checks"] = check_outputs(report["mixed_voice_outputs"], mixed, (1, 2))
            new_lanes = [i for i in range(16) if mixed[2*i] and mixed[2*i+1] == 1 and not changed[2*i]]
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
                def tone_snapshot():
                    metadata=struct.unpack("<2I",bytes.fromhex(
                        emu.dsp_peek(0x20092000+8*lane,8)["hex"]))
                    native=struct.unpack("<40H",bytes.fromhex(
                        emu.dsp_peek(0x25C48C+2*(0x6D+0x49*lane),80)["hex"]))
                    x,y=struct.unpack("<2f",bytes.fromhex(
                        emu.dsp_peek(0x20092080+8*lane,8)["hex"]))
                    def node(base):
                        return struct.unpack("<f",bytes.fromhex(
                            emu.dsp_peek(base+4*lane,4)["hex"]))[0]
                    remaining=struct.unpack("<I",bytes.fromhex(
                        emu.dsp_peek(0x200921C0+4*lane,4)["hex"]))[0]
                    assert metadata[1]==1 and remaining==0, (metadata,remaining)
                    return dict(callbacks=metadata[0],native=native,x=x,y=y,
                                companion=node(0x20092200),main=node(0x20092240),
                                capacitor=node(0x20092100))
                before=tone_snapshot()
                native=before["native"]
                assert abs(native[0]-(position<<8))<=1 and native[1]==16384 and native[5]==0, native
                g=tone808.coefficient(native[0])
                emu.run_until(frames=emu.status()["dsp_frames"]+16,timeout_wall_s=120)
                after=tone_snapshot()
                assert after["native"]==native, (label,before,after)
                callbacks=after["callbacks"]-before["callbacks"]
                assert 0<callbacks<=64, (label,before,after)
                samples,_=leakage808.continue_reference(complex(before["x"],before["y"]),
                    before["main"],before["companion"],native[1],32*callbacks)
                # Continue capacitor voltage/current, independently of the ASM's TPT state.
                r=tone808.resistance(native[0])
                history=1/(2*tone808.SAMPLE_RATE*tone808.C45)
                last_input=before["x"]+before["main"]
                voltage=((1-g)*before["capacitor"]-g*last_input)/(1-2*g)
                current=(last_input-voltage)/r
                for sample in samples:
                    voltage=(voltage+history*current+history*sample/r)/(1+history/r)
                    current=(sample-voltage)/r
                expected=voltage+history*current
                capacitor=after["capacitor"]
                previous_input, previous_output = struct.unpack("<2f",bytes.fromhex(
                    emu.dsp_peek(0x20092140+8*lane,8)["hex"]))
                tone_last = ((1-g)*capacitor-g*(after["x"]+after["main"]))/(1-2*g)
                coupling_input_error = abs(previous_input-tone_last)
                assert coupling_input_error <= 1e-5, (label,previous_input,tone_last)
                assert math.isfinite(previous_output) and abs(previous_output) < .5
                error=abs(capacitor-expected)
                assert math.isfinite(capacitor) and error<=1e-5, (label,capacitor,expected,error)
                emu.run_until(frames=emu.status()["dsp_frames"]+150,timeout_wall_s=120)
                emu.call("pcm.tap",action="capture_stop")
                pcm=hook_ab.read_wav(path)
                peak=float(max(abs(pcm)))
                assert all(math.isfinite(v) for v in pcm) and 0<peak<1, label
                report["tone_audio"][label]=dict(target=position,slot=lane,tone_raw=native[0],
                    decay_raw=native[1],coefficient=g,capacitor=capacitor,
                    prediction_scope="independent nonlinear continuation from native state; no START",
                    before=before,after=after,prediction_samples=32*callbacks,
                    predicted_capacitor=expected,state_error_fs=error,
                    native_peak_fs=peak,native_wav=str(path),
                    coupling_previous_input=previous_input,coupling_previous_output=previous_output,
                    coupling_input_error_fs=coupling_input_error)

                emu.midi_in(bytes([0x81,note,0]))
            assert report["tone_audio"]["bright"]["coefficient"] > 10*report["tone_audio"]["dark"]["coefficient"]
            assert any(abs(v["coupling_previous_input"]-v["coupling_previous_output"]) > 1e-5
                       for v in report["tone_audio"].values()), "native coupling did not filter the Tone output"
            emu.midi_in(bytes([0xB1,cc["0"],64]))
            tap("STOP"); tap("STOP")
            emu.run_until(frames=emu.status()["dsp_frames"] + 3000, timeout_wall_s=120)
            report["decay_909"] = {}
            report["tune_909"] = {}
            # Saved T1 is already 909; this does not exercise or work around #80's late MODEL edit.
            for label, position, tune_position, note in (
                    ("default",64,64,76),("short",0,64,77),("long",127,64,78),
                    ("tune-low",64,0,79),("tune-high",64,127,80)):
                emu.midi_in(bytes([0xB0,cc["0"],tune_position]))
                emu.midi_in(bytes([0xB0,cc["1"],position]))
                emu.run_until(frames=emu.status()["dsp_frames"] + 600, timeout_wall_s=120)
                path = out / ("native-909.wav" if label == "default" else
                              f"909-{label if label.startswith('tune-') else 'decay-'+label}-native.wav")
                emu.call("pcm.tap", action="capture", path=str(path))
                emu.midi_in(bytes([0x90,note,100]))
                capture_start = emu.status()["dsp_frames"]
                if label == "default":
                    observed=[]
                    first_trigger=None
                    # Frame jobs may overshoot a whole controller chunk. Existing exact
                    # instruction-step jobs expose the prefix within the same24-frame window.
                    previous_frame=capture_start
                    observation_deadline=time.monotonic()+120
                    while emu.status()["dsp_frames"] < capture_start+24:
                        remaining_wall=observation_deadline-time.monotonic()
                        if remaining_wall<=0:
                            raise TimeoutError("first909trigger observation exceeded120s wall deadline")
                        emu.step(10000,timeout_wall_s=remaining_wall)
                        current_frame=emu.status()["dsp_frames"]
                        if current_frame==previous_frame:
                            continue
                        previous_frame=current_frame
                        ids=struct.unpack("<16H",bytes.fromhex(emu.dsp_peek(0x25C48C+2*74,32)["hex"]))
                        pitches=struct.unpack("<16H",bytes.fromhex(emu.dsp_peek(0x25C48C+2,32)["hex"]))
                        lanes=[i for i in range(16) if ids[i]==20 and pitches[i]==note<<8]
                        row=dict(offset_dsp_frames=current_frame-capture_start,dsp_frames=current_frame,matching_slots=lanes)
                        if len(lanes)==1:
                            slot=lanes[0]
                            metadata=struct.unpack("<32I",bytes.fromhex(emu.dsp_peek(0x20092000,128)["hex"]))
                            remaining=struct.unpack("<I",bytes.fromhex(emu.dsp_peek(0x200921C0+4*slot,4)["hex"]))[0]
                            row.update(slot=slot,model=metadata[2*slot+1],callbacks=metadata[2*slot],remaining=remaining)
                            if metadata[2*slot+1]==2 and remaining in (64,32) and row["dsp_frames"]<=capture_start+24:
                                native=struct.unpack("<40H",bytes.fromhex(emu.dsp_peek(0x25C48C+2*(0x6D+0x49*slot),80)["hex"]))
                                assert native[0]==tune_position*256 and native[1]==position*256,(label,native)
                                phase,c8=struct.unpack("<If",bytes.fromhex(emu.dsp_peek(0x20092080+8*slot,8)["hex"]))
                                c9=struct.unpack("<f",bytes.fromhex(emu.dsp_peek(0x20092200+4*slot,4)["hex"]))[0]
                                age=tune909.TRIGGER_SAMPLES-remaining
                                _,predicted=body909.continue_reference(body909.INITIAL_STATE,native[1],native[0],age)
                                phase_error=abs((phase/2**32-.25-predicted[0]+.5)%1-.5)
                                c9_error=abs(c9-predicted[1])
                                c8_error=abs(c8-predicted[3])
                                assert predicted[2]==remaining,(row,predicted)
                                assert phase_error<=1e-5 and c9_error<=1e-5 and c8_error<=1e-5,(row,phase_error,c9_error,c8_error)
                                first_trigger=dict(status="passed",slot=slot,age_samples=age,remaining=remaining,
                                    dsp_frames=row["dsp_frames"],native_tune_raw=native[0],native_decay_raw=native[1],
                                    native_control_words=dict(tune=native[0],decay=native[1],attack=native[2],model=native[5]),
                                    actual=dict(phase_word=phase,phase_cycles=phase/2**32-.25,c9_normalized=c9,c8_encoded=c8),
                                    predicted=dict(phase_cycles=predicted[0],c9_normalized=predicted[1],c8_encoded=predicted[3]),
                                    phase_error_cycles=phase_error,c9_error_normalized=c9_error,c8_state_error_fs=c8_error,
                                    scope="fresh-hit private DSPstate during electrical trigger; age from96-minus-remaining, not lifetime callbacks; downstream PCM separate")
                        observed.append(row)
                        if first_trigger is not None:break
                    report["first_trigger_909"] = first_trigger or dict(status="unqualified",
                        reason="No unique fresh909 snapshot with remaining64or32 was visible inside the existing24frame window")
                    report["first_trigger_909"]["observations"]=observed
                # Observe at16ms, before minimum Decay crosses the physical Q12 knee.
                emu.run_until(frames=capture_start + 24, timeout_wall_s=120)
                ids = struct.unpack("<16H", bytes.fromhex(emu.dsp_peek(0x25C48C + 2*74, 32)["hex"]))
                pitches = struct.unpack("<16H", bytes.fromhex(emu.dsp_peek(0x25C48C + 2, 32)["hex"]))
                lanes = [i for i in range(16) if ids[i] == 20 and pitches[i] == note << 8]
                assert len(lanes) == 1, (ids,pitches)
                lane = lanes[0]
                def oscillator_snapshot(require_audible):
                    state = struct.unpack("<32I", bytes.fromhex(emu.dsp_peek(0x20092000,128)["hex"]))
                    assert state[2*lane+1] == 2, state
                    native = struct.unpack("<40H", bytes.fromhex(
                        emu.dsp_peek(0x25C48C + 2*(0x6D+0x49*lane),80)["hex"]))
                    assert native[0] == tune_position*256 and native[1] == position*256, (label,native)
                    downstream = emu.dsp_peek(output_base+128*lane,128)
                    checked = check_outputs({str(lane):downstream},state,(2,) if require_audible else ())
                    return dict(callbacks=state[2*lane],tune_raw=native[0],decay_raw=native[1],downstream_voice_buffer=downstream,
                                downstream_nonzero=2 in checked["nonzero_models"],
                                **checked["body909_state"][str(lane)])
                early = oscillator_snapshot(True)
                # Retain the original750-frame total capture, with an earlier first sample.
                emu.run_until(frames=capture_start + 750, timeout_wall_s=120)
                late = oscillator_snapshot(False)
                emu.call("pcm.tap",action="capture_stop")
                pcm = hook_ab.read_wav(path)
                assert len(pcm) >= 48000 and all(math.isfinite(v) for v in pcm)
                peak = float(max(abs(pcm)))
                assert 0 < peak < 1, peak
                frames = 32*(late["callbacks"]-early["callbacks"])
                assert frames > 0 and late["tune_raw"] == early["tune_raw"], (label,early,late)
                # Lifetime callback counts remain valid deltas; variable pitch cannot reveal note age.
                phases, voltages, remaining = tune909.continue_reference(
                    early["phase"]/2**32-.25,early["c9_normalized"],early["trigger_remaining"],
                    early["tune_raw"],frames)
                phase_error=abs((late["phase"]/2**32-.25-phases[-1]+.5)%1-.5)
                c9_error=abs(late["c9_normalized"]-voltages[-1])
                expected_c8=early["c8_voltage_v"]
                charging=min(frames,early["trigger_remaining"])
                if charging:
                    expected_c8=vca909.step(expected_c8,early["decay_raw"],True,charging/body909.SAMPLE_RATE)
                if frames>charging:
                    expected_c8=vca909.step(expected_c8,early["decay_raw"],False,(frames-charging)/body909.SAMPLE_RATE)
                expected_encoded=expected_c8*vca909.STATE_SCALE
                expected_gain=max(expected_encoded-vca909.BASE_V*vca909.STATE_SCALE,0)
                c8_error=abs(late["c8_encoded"]-expected_encoded)
                gain_error=abs(late["audio_gain_fs"]-expected_gain)
                assert phase_error<=1e-5 and c9_error<=1e-5 and c8_error<=1e-5 and gain_error<=1e-5, (label,phase_error,c9_error,c8_error,gain_error)
                assert late["trigger_remaining"]==remaining, (label,late,remaining)
                if expected_gain>0:
                    assert late["downstream_nonzero"], (label,expected_gain,late)
                else:
                    assert expected_c8<=vca909.BASE_V and late["audio_gain_fs"]==0, (label,expected_c8,late)
                capture_report = dict(slot=lane,early=early,late=late,
                    native_peak_fs=peak,native_wav=str(path),frames=len(pcm)//2,
                    prediction_samples=frames,phase_error_cycles=phase_error,c9_error_normalized=c9_error,
                    expected_c8_voltage_v=expected_c8,c8_state_error_fs=c8_error,
                    expected_audio_gain_fs=expected_gain,audio_gain_error_fs=gain_error,
                    early_target_dsp_frames=24,total_capture_target_dsp_frames=750,
                    scope="fixed native Tune/Decay; independent event-split C8 flow and separate Q12 gain from observed state; nonzero early downstream buffer/PCM, later silence only below the predicted physical knee")
                report["tune_909" if label.startswith("tune-") else "decay_909"][label] = capture_report
                emu.midi_in(bytes([0x80,note,0]))
                emu.run_until(frames=emu.status()["dsp_frames"] + 1600, timeout_wall_s=120)
            assert report["tune_909"]["tune-high"]["early"]["c9_normalized"] > report["tune_909"]["tune-low"]["early"]["c9_normalized"]
            assert (report["decay_909"]["long"]["early"]["c8_voltage_v"] >
                    report["decay_909"]["default"]["early"]["c8_voltage_v"] >
                    report["decay_909"]["short"]["early"]["c8_voltage_v"])
            report["body909_audio"] = report["decay_909"]["default"]
            report["final_status"] = emu.status()
            final = report["final_status"]
            assert final["cf"]["ready"] and final["cf"]["error"] is None, final
            assert final["dsp"] == "sharc" and final["audio"]["halted"] is None, final
            assert final["audio"]["missing_blocks"] == 0, final
            report["regression_status"] = "passed"
            report["status"] = "passed" if report["first_trigger_909"]["status"] == "passed" else "unqualified"
    except Exception as error:
        report["error"] = str(error)
        report["traceback"] = traceback.format_exc()
    report["unqualified"] = [
        "persistence across emulator/device restart",
        "late post-STOP MODEL not rerun for this DSP increment; original-order adopted-runtime proof separately qualified in #80",
        "808 circuit fidelity and pot calibration",
        "909 physical diode/pot calibration, Q11 reset, Attack, full transistor VCA and real-device timing",
    ]
    if report.get("first_trigger_909",{}).get("status")=="unqualified":
        report["unqualified"].append("first909trigger private-state snapshot not observed within the existing capture window")
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
