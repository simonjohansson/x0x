"""Verify the latest-only stock inputs and build their pinned SDK dependencies."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from .fixtures import ROOT, load_json, write_json

DEVICES = {"dt": ("digitakt-mk1", ("core", "machine-pages")),
           "dn": ("digitone-mk1", ("core-dn1", "machines-dn1")),
           "dn2": ("digitone-mk2", ("core-dn2",))}


def verify_entry(entry, firmware_dir, sdk_revision):
    from elekloader import formats
    image = firmware_dir / entry["image"]["path"]
    raw = image.read_bytes()
    if len(raw) != entry["image"]["bytes"] or hashlib.sha256(raw).hexdigest() != entry["image"]["sha256"]:
        raise ValueError("stock image does not match the latest-only manifest: " + str(image))
    stock, device, release = formats.load(image)
    if device.key != entry["device"] or release.version != entry["version"]:
        raise ValueError("stock image device/version differs from the supported baseline")
    main = formats.main_image(stock, device)
    if len(main) != release.main_len or hashlib.sha256(main).hexdigest() != release.main_sha256:
        raise ValueError("decompressed stock identity differs from the pinned SDK profile")
    formats.verify({"syx": stock.raw}, stock, main, device)
    return dict(device=device.key, version=release.version, image_sha256=entry["image"]["sha256"],
                sdk_revision=sdk_revision, status="verified", image=str(image))


def baseline():
    manifest = load_json(ROOT / "firmware/manifest.json")
    actual = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT / "vendor/elekloader",
                            text=True, capture_output=True, check=True).stdout.strip()
    if actual != manifest["elekloader_revision"]:
        raise ValueError("Elekloader pin differs from the SDK used to verify the firmware baseline")
    entries = {entry["device"]: entry for entry in manifest["entries"]}
    if set(entries) != {value[0] for value in DEVICES.values()} or len(manifest["entries"]) != 3:
        raise ValueError("expected exactly one latest firmware for each active device")
    return entries, actual


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("device", choices=tuple(DEVICES), nargs="?")
    build = commands.add_parser("build-deps")
    build.add_argument("device", choices=tuple(DEVICES))
    package = commands.add_parser("baseline")
    package.add_argument("device", choices=tuple(DEVICES))
    args = parser.parse_args(argv)
    try:
        entries, revision = baseline()
        targets = [args.device] if args.device else list(DEVICES)
        reports = []
        for target in targets:
            key, mods = DEVICES[target]
            report = verify_entry(entries[key], ROOT / "firmware", revision)
            if args.command in {"build-deps", "baseline"}:
                output = ROOT / "out" / target / "deps"
                for mod in mods:
                    subprocess.run([sys.executable, "-m", "elekloader.sdk.build",
                                    str(ROOT / "vendor/elekloader/mods" / mod),
                                    "--stock", report["image"], "--out", str(output)], check=True)
                report["built_dependencies"] = list(mods)
                report["output"] = str(output)
                write_json(output / "stock-baseline.json", report)
                if args.command == "baseline":
                    artifacts = sorted(output.glob("*.elemod"))
                    if len(artifacts) != len(mods):
                        raise ValueError("unexpected/stale dependency artifacts; inspect " + str(output))
                    image = output.parent / "x0z-baseline.syx"
                    command = [sys.executable, "-m", "elekloader.patch", "--stock", report["image"]]
                    for artifact in artifacts:
                        command += ["--mod", str(artifact)]
                    command += ["--out", str(image), "--version", "X0Z0"]
                    subprocess.run(command, check=True)
                    report["baseline_image"] = str(image)
                    report["baseline_sha256"] = hashlib.sha256(image.read_bytes()).hexdigest()
                    report["scope"] = "Core/companion baseline only; no x0z kick machine"
                    write_json(output.parent / "baseline-build.json", report)
            reports.append(report)
        print(json.dumps(dict(status="passed", reports=reports)))
        return 0
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(json.dumps(dict(status="failed", reason=str(error))))
        return 1


if __name__ == "__main__":
    sys.exit(main())
