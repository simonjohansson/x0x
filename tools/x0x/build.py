"""Normal x0x mod builds: shared frozen 808, provisional 909, pinned stock SDK."""

from pathlib import Path
import argparse
import hashlib
import json
import shutil

from . import cpu, firmware, sharc_field808, coldfire_field808

DEVICES = {
    "dt": ("digitakt", "digitakt-mk1", ("core", "machine-pages")),
    "dn": ("digitone", "digitone-mk1", ("core-dn1", "machines-dn1")),
    "dn2": ("digitone2", "digitone-mk2", ("core-dn2", "machines-dn2")),
}


def stage(device, folder):
    name, _, _ = DEVICES[device]
    source = cpu.ROOT / "machines" / name
    folder = Path(folder).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((source / "mod.json").read_text())
    manifest["sources"] = [str(source / p) for p in manifest["sources"]]
    if device == "dn2":
        model, _ = sharc_field808.build(folder)
    else:
        model = coldfire_field808.write_tables(folder / "model")
        manifest["sources"].append(str(folder / "model/tables.s"))
    (folder / "mod.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return model


def build(device, folder=None):
    from elekloader.sdk import build as sdk
    from elekloader import patch

    _, key, dependencies = DEVICES[device]
    folder = Path(folder or cpu.ROOT / "out" / device).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    model = stage(device, folder / "mod")
    entries, revision = firmware.baseline()
    stock = firmware.verify_entry(entries[key], cpu.ROOT / "firmware", revision)
    artifacts = []
    correction = None
    for dependency in dependencies:
        source = cpu.ROOT / "vendor/elekloader/mods" / dependency
        if device == "dt" and dependency == "machine-pages":
            destination = folder / "machine-pages"
            shutil.copytree(source, destination, dirs_exist_ok=True)
            correction = cpu.ROOT / "machines/digitakt/legacy-defaults.patch"
            cpu.command(
                ["patch", "-p1", "--batch", "--forward", "--fuzz=0", "-i", correction],
                cwd=destination,
            )
            source = destination
        artifacts.append(
            sdk.build(str(source), stock["image"], str(folder / "deps"))[0]
        )
    artifacts.append(
        sdk.build(str(folder / "mod"), stock["image"], str(folder / "deps"))[0]
    )
    outputs, manifest = patch.build(
        stock["image"], artifacts, "X0X2", log=lambda *_: None
    )
    image = folder / "x0x.syx"
    image.write_bytes(outputs["syx"])
    (folder / "link-map.json").write_text(json.dumps(manifest["_map"], indent=2) + "\n")
    report = dict(
        status="passed",
        scope="Normal combined x0x mod packaging; no emulator/device evidence implied",
        device=key,
        version="X0X2",
        stock=stock,
        elekloader_revision=revision,
        model=model,
        firmware=str(image),
        firmware_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
        linked_layout=manifest["link"]["layout"],
        sources=json.loads((folder / "mod/mod.json").read_text())["sources"],
        defaults_correction_sha256=hashlib.sha256(correction.read_bytes()).hexdigest()
        if correction
        else None,
        note="New frozen-model 808 plus retained provisional 909; final new-909 source qualification remains separate.",
    )
    (folder / "build.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("device", choices=DEVICES)
    print(json.dumps(build(p.parse_args().device)))


if __name__ == "__main__":
    main()
