"""Per-track retirement, bounded fade cost and the actual native frame hook."""
import os
from pathlib import Path
import struct
import tempfile
import unittest

from x0x import cpu, sharc_field808 as dsp


class ChokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory(prefix='x0x-choke-')
        cls.receipt, cls.artifact = dsp.build(Path(cls.folder.name))

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def runner(self):
        return dsp.Runner(self.receipt, self.artifact)

    def test_both_models_retire_only_the_owning_track_with_a_bounded_ramp(self):
        for model in (0, 32512):
            with self.subTest(model=model):
                mixed, other = self.runner(), self.runner()
                for b in range(200):
                    previous, _ = mixed.call(12345, 17001, b == 0, model=model, track=3)
                    self.assertEqual(mixed.call(32512, 32512, b == 0, slot=15,
                                                model=model, track=7)[0],
                                     other.call(32512, 32512, b == 0, slot=15,
                                                model=model, track=7)[0])
                mixed.call(16384, 16384, True, slot=1, model=model, track=3)
                tail = []
                for _ in range(4):
                    y, count = mixed.call(12345, 17001, model=model, track=3)
                    tail.extend(y)
                    self.assertLess(count, 600)
                    self.assertEqual(mixed.call(32512, 32512, slot=15, model=model, track=7)[0],
                                     other.call(32512, 32512, slot=15, model=model, track=7)[0])
                for i, y in enumerate(tail):
                    expected = struct.unpack('<f', struct.pack('<f', previous[-1]*(127-i)/128))[0]
                    self.assertEqual(y, expected)
                for _ in range(8):
                    y, count = mixed.call(12345, 17001, model=model, track=3)
                    self.assertEqual(y, (0.,)*32)
                    self.assertLess(count, 400)
                mixed.check_tables()

    def test_sixteen_allocated_slots_leave_one_renderer_per_track(self):
        for models in ((0, 0), (32512, 32512), (0, 32512)):
            with self.subTest(models=models):
                runner = self.runner()
                for slot in range(16):
                    track = slot % 2
                    runner.call(16384, 16384, True, slot=slot, model=models[track], track=track)
                    for old in range(slot):
                        runner.call(16384, 16384, slot=old, model=models[old % 2], track=old % 2)
                for _ in range(4):
                    for slot in range(16):
                        runner.call(16384, 16384, slot=slot, model=models[slot % 2], track=slot % 2)
                alive = [v for v in range(16)
                         if runner.core.peek(self.receipt['state_base'] + v*dsp.STATE_BYTES + 500) == 0]
                self.assertEqual(alive, [14, 15])
                for slot in range(14):
                    self.assertEqual(runner.call(16384, 16384, slot=slot, model=models[slot % 2],
                                                 track=slot % 2)[0], (0.,)*32)
                # Component instructions for two live engines plus fourteen retired slots.
                for block in range(200):
                    total = sum(runner.call(16384, 16384, slot=slot,
                                           model=models[slot % 2], track=slot % 2)[1]
                                for slot in range(16))
                    self.assertLess(total, 90000, (models, block, total))

    def test_invalid_attack_or_missing_owner_cannot_choke_another_voice(self):
        runner = self.runner()
        runner.call(16384, 16384, True, track=3)
        base = self.receipt['state_base']
        before = [runner.core.peek(base + i) for i in range(0, dsp.STATE_BYTES, 4)]
        self.assertEqual(runner.call(16384, 16384, True, slot=1, model=32512,
                                     attack=32513, track=3)[0], (0.,)*32)
        self.assertEqual(before, [runner.core.peek(base+i) for i in range(0, dsp.STATE_BYTES, 4)])
        for tag in (None, -1, 16):
            runner.call(16384, 16384, True, slot=1, track=tag)
            self.assertEqual(before, [runner.core.peek(base+i) for i in range(0, dsp.STATE_BYTES, 4)])

    def test_actual_coldfire_hook_preserves_registers_and_tags_only_x0x(self):
        folder = Path(self.folder.name)
        prefix = os.environ.get('ELEKLOADER_CROSS', 'm68k-elf-')
        source = cpu.ROOT/'machines/digitone2'
        cpu.command([prefix+'gcc', '-mcpu=54455', '-msoft-float', '-O2', '-ffreestanding',
                     '-fno-builtin', '-Wall', '-Wextra', '-Werror', '-c', source/'choke.c',
                     '-o', folder/'frame-c.o'])
        cpu.command([prefix+'as', '-mcpu=54455', source/'choke.s', '-o', folder/'frame.o'])
        cpu.command([prefix+'ld', '-Ttext=0x40000400', '-e', 'x0x_frame_owner',
                     folder/'frame.o', folder/'frame-c.o', '-o', folder/'frame.elf'])
        cpu.command([prefix+'objcopy', '-O', 'binary', folder/'frame.elf', folder/'frame.bin'])
        machine = cpu.require_module('emu.harness', 'digiemu').Machine()
        from unicorn import m68k_const as regs
        for address in (0x40000000, 0x40200000, 0x80000000):
            machine.ensure(address)
        uc = machine.uc
        uc.mem_write(0x40000400, (folder/'frame.bin').read_bytes())
        frame = [0x1357]*1344
        owners = bytearray(320)
        for slot in range(16):
            frame[74+slot] = 20 if slot < 12 else 0
            owners[20*slot] = slot if slot != 11 else 255
        uc.mem_write(0x80005e60, struct.pack('>1344H', *frame))
        uc.mem_write(0x40288305, bytes(owners))
        saved = {getattr(regs, 'UC_M68K_REG_'+n): 0x10203040+i
                 for i, n in enumerate([*(f'D{i}' for i in range(8)), *(f'A{i}' for i in range(7))])}
        for reg, value in saved.items():
            uc.reg_write(reg, value)
        uc.reg_write(regs.UC_M68K_REG_SR, 0x2715)
        uc.reg_write(regs.UC_M68K_REG_A7, 0x40050000)
        uc.emu_start(0x40000400, 0x40025e9a, count=10000)
        self.assertEqual(uc.reg_read(regs.UC_M68K_REG_PC), 0x40025e9a)
        self.assertEqual(uc.reg_read(regs.UC_M68K_REG_A7), 0x4004fffc)
        self.assertEqual(bytes(uc.mem_read(0x4004fffc, 4)), struct.pack('>I', 0x80005e60))
        self.assertEqual(uc.reg_read(regs.UC_M68K_REG_SR), 0x2715)
        self.assertTrue(all(uc.reg_read(reg) == value for reg, value in saved.items()))
        for slot in range(12):
            frame[109+73*slot+39] = 0xa500 | slot if slot != 11 else 0
        self.assertEqual(bytes(uc.mem_read(0x80005e60, 2688)), struct.pack('>1344H', *frame))
        self.assertEqual(bytes(uc.mem_read(0x40288305, 320)), bytes(owners))
