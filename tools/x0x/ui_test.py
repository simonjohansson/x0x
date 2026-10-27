"""Compile the actual C control boundary independently of audio rendering."""
import argparse
import os
from pathlib import Path
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coldfire", action="store_true")
    args = parser.parse_args()
    output = ROOT / "out/host/test_controls"
    output.parent.mkdir(parents=True, exist_ok=True)
    if args.coldfire:
        prefix = os.environ.get("ELEKLOADER_CROSS", "m68k-elf-")
        obj = output.with_suffix(".coldfire.o")
        subprocess.run([prefix + "gcc", "-mcpu=54455", "-msoft-float", "-std=c99",
                        "-O2", "-ffreestanding", "-fno-builtin", "-Wall", "-Wextra", "-Werror",
                        "-Iinclude", "-c", "src/controls.c", "-o", str(obj)], cwd=ROOT, check=True)
        imports = subprocess.run([prefix + "nm", "-u", str(obj)], check=True,
                                 capture_output=True, text=True).stdout.strip()
        if imports:
            raise RuntimeError("control plumbing needs unexpected target runtime symbols: " + imports)
        print("ColdFire C control object has no undefined runtime imports")
        return
    compiler = shlex.split(os.environ.get("CC", "clang"))
    subprocess.run(compiler + ["-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
                   "-Iinclude", "src/controls.c", "tests/ui/test_controls.c", "-o", str(output)],
                   cwd=ROOT, check=True)
    subprocess.run([output], check=True)
    print("C control boundary passed (fake receiver; no native pages or DSP)")


if __name__ == "__main__":
    main()
