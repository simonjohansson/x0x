"""Build the approved DN2 silent voice and check its actual SHARC callback."""
from __future__ import annotations

import argparse
import hashlib
import json
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
                  coupled_boot="blocked: complete ADSP-2156x HWR reset-table text is unavailable",
                  unqualified=component_report["unqualified"])
    (FOLDER / "build-report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="also package latest-OS silent firmware")
    args = parser.parse_args()
    try:
        report = build() if args.build else component()[0]
        print(json.dumps(report))
        return 0
    except cpu.Unavailable as error:
        print(json.dumps(dict(status="unavailable", reason=str(error))))
        return 77


if __name__ == "__main__":
    sys.exit(main())
