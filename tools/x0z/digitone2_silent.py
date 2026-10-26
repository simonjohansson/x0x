"""Build the approved DN2 silent voice and check its actual SHARC callback."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

from . import cpu, firmware, sharc_callback as callback, sharc_selector as selector

ROOT = cpu.ROOT
SOURCE = ROOT / "targets/sharc/silence.s"
FOLDER = ROOT / "out/dn2/silent"


def component() -> tuple[dict, bytes]:
    FOLDER.mkdir(parents=True, exist_ok=True)
    code, entry, _ = callback.build(FOLDER, SOURCE)
    from elekloader.sdk.sharc import machine_layout
    callback.validate_layout(machine_layout("voice"), code, entry)
    callback.decoded_instructions(code, entry)
    inputs = selector.cases()
    reference, provenance = selector.c_reference(FOLDER, inputs)
    runner = selector.SelectorRunner(code, entry)
    for row, expected in zip(inputs, reference, strict=True):
        samples, state = runner.call_raw(row, state_writable=expected["notices"] == 1)
        if state != expected["state"]:
            raise AssertionError(row["label"] + ": silent selector state differs from C policy")
        if row["input_present"] and samples != [0.0] * 32:
            raise AssertionError(row["label"] + ": silent callback did not overwrite all output")
    report = dict(status="passed", scope="actual assembled SHARC callback with synthetic SDK frames",
                  project_revision=cpu.revision(ROOT),
                  elekloader_revision=cpu.revision(ROOT / "vendor/elekloader"),
                  emulator_revision=cpu.revision(ROOT / "vendor/digikit"),
                  calls=runner.calls, code_bytes=len(code), state_bytes=callback.STATE_BYTES,
                  worst_instructions=runner.worst_instructions,
                  source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                  image_sha256=hashlib.sha256(code).hexdigest(), c_reference=provenance,
                  checked=["all 16 independent slots", "START-only MODEL latch", "mixed models",
                           "all owned output samples zero", "state/output guards", "SDK context preservation"],
                  unqualified=["coupled OS boot", "native UI/locks/LFO delivery", "save/reload",
                               "native allocator ownership", "kick audio and real-device timing"])
    (FOLDER / "component-report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report, code


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
    artifact = voice_artifact(code, bytes(callback.STATE_BYTES), 0, 20, 0)
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
        raise AssertionError("silent DN2 mod does not link: " + "; ".join(errors))
    linked = link.link(mods, image, sharc_stream=stock.section(7))
    binding = next(record for record in sharc.parse(linked.sharc_stream, release.sharc)
                   if record.target == 0x20093e00)
    if binding.raw[16:] != struct.pack("<II", 0xbc8400, 20):
        raise AssertionError("installed SHARC binding does not select the approved ID20 callback")
    output = FOLDER / "x0z.syx"
    command = [sys.executable, "-m", "elekloader.patch", "--stock", stock_report["image"]]
    for artifact_path in artifacts:
        command += ["--mod", artifact_path]
    cpu.command([*command, "--out", output, "--version", "X0Z0"])
    report = dict(status="passed", scope="SDK-verified silent DN2 firmware packaging; not an emulator boot",
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
    from tools.patchkit import pk_harness as H
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
            emu.midi_in(bytes([0x90, 60, 100]))
            target = emu.status()["dsp_frames"] + 100
            emu.run_until(frames=target, timeout_wall_s=120)
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
            assert all(
                bytes.fromhex(v["hex"]) == bytes(128)
                for v in report["voice_outputs"].values()
            ), report["voice_outputs"]
            controls = struct.unpack(
                "<40I", bytes.fromhex(report["callback_params"]["hex"])
            )
            assert [controls[i] for i in (0, 1, 2, 5)] == [16384, 16384, 16384, 0], (
                controls
            )
            names = {
                k: int(v, 0)
                for k, v in json.loads((out / "x0z.syx.map.json").read_text()).items()
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
            assert all(bytes.fromhex(v["hex"]) == bytes(128)
                       for v in report["switched_voice_outputs"].values()), report["switched_voice_outputs"]
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

            chord("TRK", "TRIG 2")
            chord("FUNC", "SYN")
            for _ in range(4):
                tap("DOWN")
            tap("YES")
            tap("NO")
            (out / "native-track2-x0z.png").write_bytes(emu.frame_png())
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
            assert all(bytes.fromhex(v["hex"]) == bytes(128)
                       for v in report["mixed_voice_outputs"].values()), report["mixed_voice_outputs"]
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
        "native sequencer p-lock/LFO",
        "persistent save/reload",
        "kick sound and real-device timing",
    ]
    (out / "native-boot-report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--build", action="store_true", help="also package latest-OS silent firmware"
    )
    mode.add_argument(
        "--full-os",
        action="store_true",
        help="run the installed silent mod in coupled Digikit",
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
