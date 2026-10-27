"""Standalone approved DN2 page/selector tests with a fake DSP receiver."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import tempfile

from . import cpu


def diagnose() -> dict:
    root = cpu.ROOT
    with tempfile.TemporaryDirectory(prefix="x0x-dn2-controls-") as tmp:
        executable = Path(tmp) / "controls"
        cpu.command([*shlex.split(os.environ.get("CC", "clang")), "-std=c99", "-O2",
                     "-Wall", "-Wextra", "-Werror", "-I", root / "include",
                     "-I", root / "machines/digitone2",
                     "-I", root / "vendor/elekloader/elekloader/sdk/include",
                     root / "src/controls.c", root / "machines/digitone2/adapter.c",
                     root / "machines/digitone2/controls.c", root / "machines/digitone2/page.c",
                     root / "tests/ui/test_digitone2_controls.c", "-o", executable])
        cpu.command([executable])
    return dict(status="passed", kind="isolated-C-DN2-controls-and-selector",
                models=["808", "909"], input_origin="synthetic-callback-frames",
                checked=["approved descriptor/page", "exact fractional controls",
                         "START-only selector latch", "per-slot tail-clear metadata",
                         "ignored and invalid destinations", "no audio writes"],
                unqualified=["native UI/save/load", "native voice ownership",
                             "DSP reset/excitation", "audio and downstream processing"])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", action="store_true", help="standalone host test (the default)")
    parser.parse_args(argv)
    print(json.dumps(diagnose()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
