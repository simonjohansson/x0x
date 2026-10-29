"""Production dispatch: both assembled sample loops and the real C adapters."""

import ctypes
from pathlib import Path
import struct
import tempfile
import unittest
from x0x import cpu, field909, coldfire_field909 as cf9, coldfire_field808 as cf, sharc_field808 as sh


class ModTests(unittest.TestCase):
    def test_compiled_native_adapters(self):
        root = cpu.ROOT
        with tempfile.TemporaryDirectory() as tmp:
            for name, extra in (
                ("digitakt", []),
                (
                    "digitone",
                    [root / "machines/digitone/adapter.c", root / "src/controls.c"],
                ),
            ):
                output = Path(tmp) / name
                cpu.command(
                    [
                        "clang",
                        "-std=c99",
                        "-O2",
                        "-Wall",
                        "-Wextra",
                        "-Werror",
                        "-I" + str(root / "include"),
                        "-I" + str(root / "vendor/elekloader/elekloader/sdk/include"),
                        root / "machines" / name / "machine.c",
                        root / "targets/coldfire/engine.c",
                        *extra,
                        root / "tests/ui" / ("test_" + name + "_mod.c"),
                        "-o",
                        output,
                    ]
                )
                cpu.command([output])

    def test_actual_combined_coldfire(self):
        cpu.require_module("emu.harness", "digiemu")
        with tempfile.TemporaryDirectory() as tmp:
            _, image = cf.build(Path(tmp), combined=True)
            mixed = cf.Runner(image, words=353, stack_bytes=320)
            reference = cf.Reference(Path(tmp))
            reference909 = cf9.Reference(Path(tmp)/"909-reference")
            for block in range(100):
                actual = mixed.call(
                    12345, 17001, start=block == 0, model=32512 if block else 0
                )
                self.assertEqual(actual, reference.call(12345, 17001, start=block == 0))
                payload = bytes(mixed.uc.mem_read(mixed.STATES + 4, cf.WORDS * 4))
                self.assertEqual(payload, struct.pack(">352i", *reference.state))
                self.assertEqual(
                    int.from_bytes(mixed.uc.mem_read(mixed.STATES, 4), "big"), 1
                )
                expected = reference909.call(7890,23001,23456,start=block==0)
                actual = mixed.call(
                    7890,
                    23456,
                    start=block == 0,
                    slot=7,
                    model=32512 if block == 0 else 0,
                    attack=23001 if block==0 else 0,
                )
                self.assertEqual(actual,expected)
                self.assertEqual(bytes(mixed.uc.mem_read(mixed.STATES+7*353*4+4,1408)),struct.pack(">352i",*reference909.state))
            old = bytes(mixed.uc.mem_read(mixed.STATES, 353 * 4))
            self.assertEqual(mixed.call(32513, 0, True, model=32512), [0] * 32)
            self.assertEqual(old, bytes(mixed.uc.mem_read(mixed.STATES, 353 * 4)))
            reference.state = (ctypes.c_int32 * cf.WORDS)()
            self.assertEqual(
                mixed.call(0, 0, True, slot=7, model=0), reference.call(0, 0, True)
            )
            reference.state = (ctypes.c_int32 * cf.WORDS)()
            self.assertEqual(
                mixed.call(12345, 17001, True), reference.call(12345, 17001, True)
            )
            reference909.state=(ctypes.c_int32*352)()
            expected=reference909.call(0,16384,0,True)
            actual = mixed.call(0, 0, True, model=32512)
            self.assertEqual(actual,expected)
            mixed.check_tables()

    def test_actual_combined_sharc(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt, artifact = sh.build(Path(tmp))
            mixed = sh.Runner(receipt, artifact)
            isolated = sh.Runner(receipt, artifact)
            expected909 = 4 * field909.render(field909.load(), 7890, 16384, 23456, frames=3200)
            for block in range(100):
                self.assertEqual(
                    mixed.call(
                        12345, 17001, start=block == 0, model=32512 if block else 0
                    )[0],
                    isolated.call(12345, 17001, start=block == 0)[0],
                )
                expected = expected909[block*32:(block+1)*32]
                actual, _ = mixed.call(
                    7890,
                    23456,
                    start=block == 0,
                    slot=15,
                    model=32512 if block == 0 else 0,
                )
                self.assertLess(max(abs(a - b) for a, b in zip(actual, expected)), 1e-5)
            self.assertEqual(
                mixed.call(12345, 17001, True, slot=15)[0],
                isolated.call(12345, 17001, True)[0],
            )
            mixed.check_tables()
            isolated.check_tables()
