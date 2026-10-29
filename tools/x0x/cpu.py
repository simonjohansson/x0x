"""Pinned build tools and emulator imports for the current mod tests."""
from __future__ import annotations

import importlib
import hashlib
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SELACHE_PIN = "2b26d3b75c53063575bc5c820fa0d38879335187"
FRAMES = 32
EMAC_SEED = (0x12345678,0x89ABCDEF,0x13579BDF,0x2468ACE0,
             0x11223344,0x55667788,0xFFFFABCE,0x0CB1)


class Unavailable(RuntimeError):
    """A required tool or emulator is absent; not a passing test."""


def command(args: list[str | Path], cwd: Path | None = None) -> str:
    result = subprocess.run(list(map(str, args)), cwd=cwd, capture_output=True,
                            text=True, check=False)
    if result.returncode:
        raise RuntimeError(f"{args[0]} failed: {result.stdout}{result.stderr}")
    return result.stdout


def revision(path: Path) -> str:
    return command(["git", "rev-parse", "HEAD"], cwd=path).strip()


def clean_revision(path: Path) -> str:
    if command(['git', 'status', '--porcelain'], cwd=path).strip():
        raise ValueError('Modified dependency checkout: ' + str(path))
    return revision(path)


def source_hashes() -> dict[str, str]:
    paths = [ROOT/'mise.toml', ROOT/'firmware/manifest.json']
    for folder in ('tools/x0x', 'targets', 'machines', 'src', 'include', 'models', 'tests/asm', 'tests/fixtures'):
        paths.extend(p for p in (ROOT/folder).rglob('*') if p.is_file()
                     and p.suffix in ('.py', '.c', '.s', '.h', '.json', '.npz', '.patch', '.csv', '.html'))
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def tool_identity(name: str | Path) -> dict:
    path = Path(require_program(str(name))).resolve()
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def selache() -> Path:
    path = Path(os.environ.get('SELACHE', ROOT/'vendor/digikit/out/tools/selache')).resolve()
    if clean_revision(path) != SELACHE_PIN:
        raise ValueError('Selache revision mismatch')
    return path


def require_program(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise Unavailable(f"{name} is unavailable; run the documented mise bootstrap")
    return path


def require_module(name: str, dependency: str):
    try:
        module = importlib.import_module(name)
    except ImportError as error:
        raise Unavailable(f"{dependency} runtime is unavailable: {error}") from error
    expected = (ROOT / "vendor" / dependency).resolve()
    actual = Path(module.__file__).resolve()
    if not actual.is_relative_to(expected):
        raise Unavailable(f"{name} must come from pinned vendor/{dependency}, got {actual}")
    return module


def build_coldfire(folder: Path, source: Path, objects=()) -> tuple[bytes, Path]:
    prefix = os.environ.get("ELEKLOADER_CROSS", "m68k-elf-")
    assembler = require_program(prefix + "as")
    linker = require_program(prefix + "ld")
    objcopy = require_program(prefix + "objcopy")
    obj, executable, binary = [folder / name for name in ("diagnostic.o", "diagnostic.elf", "diagnostic.bin")]
    command([assembler, "-mcpu=54455", source, "-o", obj])
    command([linker, "-Ttext=0x40000400", "-e", "x0x_diagnostic", obj, *objects, "-o", executable])
    command([objcopy, "-O", "binary", executable, binary])
    return binary.read_bytes(), source
