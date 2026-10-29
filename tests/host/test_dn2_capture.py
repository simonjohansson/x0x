"""Execute the diagnostic ASM: exact source blocks, publication, and live registers."""
import json
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from x0x import cpu, dn2_capture as capture, sharc_field808 as engine


class ClientSelectionTests(unittest.TestCase):
    def test_explicit_checkout_and_cached_module_mismatch(self):
        checkout = Path('/private/tmp/selected-digihealth')
        modules = [SimpleNamespace(__file__=str(checkout/'tools'/f'{name}.py'))
                   for name in ('keymap', 'digiusb', 'midimido')]
        modules[2].Port = mock.Mock()
        with mock.patch.object(cpu, 'command', return_value='') as command:
            with mock.patch.object(capture.importlib, 'import_module', side_effect=modules):
                self.assertEqual(capture.client_modules(checkout), modules[1:])
            self.assertTrue(all(call.kwargs['cwd'] == checkout for call in command.call_args_list))
            modules[1].__file__ = '/private/tmp/wrong-client/digiusb.py'
            with mock.patch.object(capture.importlib, 'import_module', side_effect=modules):
                with self.assertRaisesRegex(ValueError, 'different checkout'):
                    capture.read('/private/tmp/unused-capture', checkout)
            modules[2].Port.assert_not_called()

    def test_dirty_or_unqualified_checkout_is_rejected_before_import(self):
        with mock.patch.object(capture.importlib, 'import_module') as imported:
            with mock.patch.object(cpu, 'command', return_value=' M tools/digiusb.py'):
                with self.assertRaisesRegex(ValueError, 'clean DigiHealth'):
                    capture.client_modules('/private/tmp/dirty')
            with mock.patch.object(cpu, 'command', side_effect=['', RuntimeError('unqualified revision')]):
                with self.assertRaisesRegex(RuntimeError, 'unqualified revision'):
                    capture.client_modules('/private/tmp/old')
            imported.assert_not_called()


class CaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cpu.require_module('tools.sharc_dev.sharc_transpile_run', 'digikit')
        except (ImportError, cpu.Unavailable) as error:
            raise unittest.SkipTest(str(error))
        cls.folder = tempfile.TemporaryDirectory(prefix='x0x-dn2-capture-')
        cls.normal, cls.normal_artifact = engine.build(Path(cls.folder.name)/'normal')
        cls.receipt, cls.artifact = capture.instrument(Path(cls.folder.name)/'diagnostic')

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def runner(self):
        result = engine.Runner(self.receipt, self.artifact)
        result.immutable = [(a, b) for a, b in result.immutable if a != capture.CAPTURE]
        return result

    def record(self, runner):
        return struct.pack('<176I', *(runner.core.peek(capture.CAPTURE+4*i) for i in range(176)))

    def frame(self, runner, samples, frame, bank=0):
        from tools.sharc_dev import sharc_trace as trace
        core = runner.core
        master = tuple(samples) + tuple(-0.5*x for x in samples)
        pcm = tuple((frame*1000+i)*(1 if i%2 else -1) for i in range(64))
        core.poke(0x268438, struct.pack('<64f', *master), 4)
        core.poke(0x2c0478+256*bank, struct.pack('<64i', *pcm), 4)
        core.poke(0x268a38, struct.pack('<I', bank), 4)
        live = dict(R0=0x12345678, R1=bank^1, R2=0x89abcdef, I4=0x2c1000,
                    I6=0x2dff00, I12=0x1c9e75, L2=128, L3=256, MODE1=0x10000)
        for name, value in live.items():
            core.set_reg(trace.UREG_CODES[name], trace.Const(value))
        before = {name:core.get_reg(trace.UREG_CODES[name]) for name in live}
        core.set_option(runner.native.OPT_STOP_PC, 0x170000)
        core.fresh_call(self.receipt['capture_hook_pc'])
        count = core.run(10000)
        self.assertEqual(core.pc(), 0x170000, (hex(core.pc()), core.halt_reason))
        self.assertEqual(before, {name:core.get_reg(trace.UREG_CODES[name]) for name in live})
        core.set_option(runner.native.OPT_STOP_PC, runner.STOP)
        self.assertLess(count, 1500)
        return master, pcm, count

    def test_both_engines_match_normal_and_capture_exact_150th_block(self):
        for model, slot in [(0, 0), (32512, 15)]:
            with self.subTest(model=model, slot=slot):
                expected = engine.Runner(self.normal, self.normal_artifact)
                actual = self.runner()
                counts = []
                frozen = None
                for block in range(160):
                    raw, _ = actual.call(16384, 16384, start=block==0, slot=slot, model=model)
                    self.assertEqual(raw, expected.call(16384, 16384, start=block==0, slot=slot, model=model)[0])
                    master, pcm, count = self.frame(actual, raw, block+1, bank=slot%2)
                    counts.append(count)
                    if block == 149:
                        frozen = self.record(actual)
                        decoded = capture.decode(frozen)
                        self.assertEqual(decoded['frame'], 150)
                        self.assertEqual(decoded['slot'], slot)
                        self.assertEqual(decoded['model'], 1 if model==0 else 2)
                        self.assertEqual(decoded['raw'], list(raw))
                        self.assertEqual(decoded['master_left']+decoded['master_right'], list(master))
                        self.assertEqual(decoded['pcm'], list(pcm))
                    elif block > 149:
                        self.assertEqual(self.record(actual), frozen)
                actual.check_tables()
                self.assertEqual(sum(n>100 for n in counts), 1)
                # A later START invalidates, then captures a new immutable generation.
                raw, _ = actual.call(0, 0, start=True, slot=slot, model=model)
                self.frame(actual, raw, 161, bank=slot%2)
                self.assertEqual(actual.core.peek(capture.CAPTURE+4), 1)
                self.assertEqual(actual.core.peek(capture.CAPTURE+8), 2)
                with self.assertRaises(ValueError):
                    capture.decode(self.record(actual))
                for block in range(149):
                    raw, _ = actual.call(0, 0, slot=slot, model=model)
                    self.frame(actual, raw, 162+block, bank=slot%2)
                second = capture.decode(self.record(actual))
                self.assertEqual(second['epoch'], 2)
                self.assertEqual(second['raw'], list(raw))
                self.assertEqual(second['frame'], 310)

    def test_stale_raw_frame_is_not_published(self):
        runner = self.runner()
        for block in range(150):
            raw, _ = runner.call(16384, 16384, start=block==0)
            if block < 149:
                self.frame(runner, raw, block+1)
        runner.core.poke(capture.CAPTURE+704, struct.pack('<I', 150), 4)
        self.frame(runner, raw, 151)
        self.assertEqual(runner.core.peek(capture.CAPTURE+4), 4)
        with self.assertRaises(ValueError):
            capture.decode(self.record(runner))

    def test_invalid_context_cannot_arm_and_bad_pcm_bank_cannot_publish(self):
        runner = self.runner()
        original = runner.core.poke
        def corrupt(address, data, width=1):
            if address == runner.INPUT:
                words = list(struct.unpack('<6I', data)); words[5] += 4
                data = struct.pack('<6I', *words)
            return original(address, data, width)
        with mock.patch.object(runner.core, 'poke', side_effect=corrupt):
            runner.call(16384, 16384, start=True)
        self.assertEqual(runner.core.peek(capture.CAPTURE+4), 0)
        for block in range(150):
            raw, _ = runner.call(16384, 16384, start=block==0)
            self.frame(runner, raw, block+1, bank=0 if block<149 else 2)
        self.assertEqual(runner.core.peek(capture.CAPTURE+4), 4)
        with self.assertRaises(ValueError):
            capture.decode(self.record(runner))

    def test_placement_adapter_tables_and_profile_stay_unchanged(self):
        from elekloader.devices.digitone_mk2 import DEVICE
        profile = DEVICE.releases['1.12'].sharc
        self.assertEqual(self.artifact['segments'][0], self.normal_artifact['segments'][0])
        self.assertEqual(self.artifact['segments'][2], self.normal_artifact['segments'][2])
        self.assertEqual(self.artifact['voice_state'], self.normal_artifact['voice_state'])
        self.assertLessEqual(self.receipt['code_bytes']+64, engine.CODE_BYTES)
        self.assertLessEqual(self.receipt['state_base']+16*512, capture.CAPTURE)
        self.assertEqual(capture.CAPTURE+capture.RESERVE, 0x2009fc00)
        self.assertEqual(profile['peek_hook'][2], '3e0617000000')
        self.assertEqual(json.loads((Path(self.folder.name)/'diagnostic/voice.sharc.json').read_text()), self.artifact)

    def test_reader_rejects_unpublished_mismatched_and_nonfinite_records(self):
        header = [capture.MAGIC,3,1,0,1,150,150,150,4800,150,0,0x25c000,0x268438,0x2c0478,0,1]
        def record(words):
            return struct.pack('<16I96f64i', *words, *([0.0]*96), *([0]*64))
        self.assertEqual(capture.decode(record(header))['frame'], 150)
        ddr = header.copy(); ddr[11] = 0x804acc90
        self.assertEqual(capture.decode(record(ddr))['raw_pointer'], 0x804acc90)
        for index, value in [(0,0),(1,0),(1,1),(1,2),(1,4),(2,0),(3,16),(4,0),
                             (5,151),(6,151),(7,151),(8,4799),(9,149),(10,1),
                             (11,0),(11,0x25c001),(11,0xa0000000),(12,0),(13,0),(14,2),(15,2)]:
            with self.subTest(index=index, value=value), self.assertRaises(ValueError):
                words = header.copy(); words[index] = value; capture.decode(record(words))
        for data in [b'', bytes(704), record(header)[:-4], record(header)+bytes(4),
                     record(header)[:64]+struct.pack('<f', float('nan'))+record(header)[68:]]:
            with self.assertRaises(ValueError):
                capture.decode(data)

    def test_readback_refuses_a_trigger_during_transfer_and_closes_port(self):
        header = [capture.MAGIC,3,1,0,1,150,150,150,4800,150,0,0x25c000,0x268438,0x2c0478,0,1]
        data = struct.pack('<16I96f64i', *header, *([0.0]*96), *([0]*64))
        for changed in (False, True):
            port = mock.Mock()
            final = data[:64] if not changed else bytes(64)
            health = SimpleNamespace(Diag=lambda p: p, RemoteKeys=lambda d: SimpleNamespace(product=3), dsp_peek=mock.Mock(side_effect=[data[:64], data, final]))
            with tempfile.TemporaryDirectory() as tmp, mock.patch.object(capture, 'client_modules', return_value=(health, SimpleNamespace(Port=lambda:port))):
                folder = Path(tmp)/'readback'
                if changed:
                    with self.assertRaises(ValueError):
                        capture.read(folder, Path(tmp))
                    self.assertFalse(folder.exists())
                else:
                    self.assertEqual(capture.read(folder, Path(tmp))['epoch'], 1)
                    self.assertEqual((folder/'capture-000001.bin').read_bytes(), data)
                    self.assertEqual(json.loads((folder/'capture-000001.json').read_text())['frame'], 150)
                port.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
