"""Compile the actual C control boundary with a fake receiver, without DSP."""
import os
from pathlib import Path
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def main():
    output = ROOT / "out/host/test_controls"
    output.parent.mkdir(parents=True, exist_ok=True)
    compiler = shlex.split(os.environ.get("CC", "clang"))
    subprocess.run(compiler + ["-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
                   "-Iinclude", "src/controls.c", "tests/ui/test_controls.c", "-o", str(output)],
                   cwd=ROOT, check=True)
    subprocess.run([output], check=True)
    print("C control boundary passed (fake receiver; no native pages or DSP)")


if __name__ == "__main__":
    main()
