"""Independent field encoding, actual parcels and isolated voice lifecycle."""
import struct
import itertools
import statistics
import tempfile
from pathlib import Path
import unittest
from unittest import mock

from x0x import cpu, field808, sharc_field808 as dsp, sharc_layout


class SharcFieldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global np
        try:
            import numpy as np
            import scipy
            cpu.require_module('tools.sharc_dev.sharc_transpile_run','digikit')
        except (ImportError,cpu.Unavailable) as error:
            raise unittest.SkipTest('Run mise run bootstrap, then mise run test: '+str(error))
        cls.model=dsp.load_model()
        cls.tables=dsp.export_tables(cls.model)
        cls.folder=tempfile.TemporaryDirectory(prefix='x0x-sharc-field-')
        cls.receipt,cls.artifact=dsp.build(Path(cls.folder.name))

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def test_native_core_matches_independent_python_traces_and_write_guards(self):
        self.assertEqual(len(dsp.python_witness(self.receipt,self.artifact)),2)

    def test_body_rendering_stays_within_the_reduced_work_budget(self):
        for model, budget in ((0, 10000), (32512, 12000)):
            with self.subTest(model=model):
                runner = dsp.Runner(self.receipt, self.artifact)
                counts = [runner.call(16384, 16384, b == 0, model=model)[1]
                          for b in range(200)]
                self.assertLess(statistics.median(counts[50:]), budget)

    def test_full_hit_peak_work_at_control_corners_and_defaults(self):
        for model, frames, budget in ((0, 264000, 18000), (32512, 96000, 42000)):
            cases = list(itertools.product((0, 32512), repeat=3)) if model else [
                (tone, 16384, decay) for tone, decay in itertools.product((0, 32512), repeat=2)]
            for tone, attack, decay in cases + [(16384, 16384, 16384)]:
                with self.subTest(model=model, controls=(tone, attack, decay)):
                    runner = dsp.Runner(self.receipt, self.artifact)
                    counts = [runner.call(tone, decay, b == 0, model=model, attack=attack, track=0)[1]
                              for b in range(frames//32)]
                    self.assertLess(max(counts), budget)
                    self.assertLess(runner.call(tone, decay, model=model, attack=attack, track=0)[1], 350)

    def test_expired_block_preserves_state_and_restart(self):
        for model, age, word in ((0, 264000, 58), (32512, 96000, 0)):
            with self.subTest(model=model):
                runner = dsp.Runner(self.receipt, self.artifact)
                fresh = dsp.Runner(self.receipt, self.artifact)
                runner.call(12345, 17001, True, model=model, attack=23001)
                base = self.receipt['state_base']
                runner.core.poke(base+4*word, struct.pack('<I', age), 4)
                before = [runner.core.peek(base+4*i) for i in range(128)]
                expected = before.copy()
                expected[127] = 0
                if model == 0:
                    phase = (before[59]<<32) | before[60]
                    step = round(self.tables['frequency']*32/48000*2**64)
                    phase = (phase+step) % 2**64
                    expected[59:61] = [phase>>32, phase & 0xffffffff]
                output, count = runner.call(12345, 17001, model=model, attack=23001)
                self.assertEqual(output, (0.,)*32)
                self.assertLess(count, 350)
                self.assertEqual([runner.core.peek(base+4*i) for i in range(128)], expected)
                self.assertEqual(runner.call(12345, 17001, True, model=model, attack=23001)[0],
                                 fresh.call(12345, 17001, True, model=model, attack=23001)[0])
                runner.check_tables()

    def test_report_links_the_generated_plot_and_includes_asm_scope(self):
        page=Path(self.folder.name)/'preview.html'
        page.write_text('<html><img src="corners.png"></html>')
        dsp.decorate_html(page,[dict(port_max_dsp_fs=1e-6)])
        text=page.read_text()
        self.assertNotIn('corners.png',text)
        self.assertIn('src="waveforms.png"',text)
        self.assertIn('Executed ASM qualification',text)
        self.assertIn('reference-driven 909',text)

    def test_exported_cubic_basis_matches_original_model(self):
        for tone,decay in ((0,0),(32512,32512),(12345,17001)):
            expected=field808.render(self.model,tone,decay,frames=4800)
            actual=dsp.render_tables(self.tables,tone,decay,frames=4800)
            self.assertLess(float(abs(expected-actual).max())*4,1e-5)
        for group in self.tables['groups']:
            self.assertTrue(np.isfinite(group['basis']).all())

    def test_real_layout_contains_both_models_and_observer_margin(self):
        r=self.receipt
        self.assertLessEqual(r['code_bytes']+64+768,dsp.CODE_BYTES)
        self.assertLessEqual(r['initialized_plus_states']+16*172,r['layout']['data_bytes'])
        self.assertEqual(self.artifact['voice_state']['voice_bytes'],512)
        for code_bytes,voice_bytes in ((True,0),(63,0),(65536,0),(12288,True),(12288,32768)):
            with self.assertRaises(ValueError):
                sharc_layout.voice_artifact(bytes(4),b'',0,20,0,code_bytes=code_bytes,voice_bytes=voice_bytes)

    def test_executable_reader_rejects_changed_extent_entry_and_sections(self):
        raw=(Path(self.folder.name)/'field808.dxe').read_bytes()
        for changed in (b'bad',raw[:40],raw[:24]+struct.pack('<I',0)+raw[28:]):
            with self.assertRaises(ValueError):
                dsp.read_executable(changed,self.receipt['layout'])

    def test_start_reset_model_latch_slots_and_terminal_silence(self):
        runner=dsp.Runner(self.receipt,self.artifact)
        self.assertEqual(runner.call(0,0)[0],(0.,)*32)
        first,_=runner.call(32512,32512,True)
        continued,_=runner.call(0,0,False,model=32512)
        self.assertNotEqual(first,continued)
        other,_=runner.call(32512,32512,True,slot=15)
        self.assertEqual(first,other)
        self.assertEqual(first,runner.call(32512,32512,True)[0])
        self.assertTrue(any(runner.call(32512,32512,True,model=32512)[0]))
        self.assertTrue(any(runner.call(0,0)[0]))
        self.assertEqual(first,runner.call(32512,32512,True)[0])
        runner.core.poke(self.receipt['state_base']+232,struct.pack('<I',264000),4)
        for _ in range(3):
            self.assertEqual(runner.call(32512,32512)[0],(0.,)*32)
        state=runner.core.peek(self.receipt['state_base']+232)
        self.assertEqual(state,264000)
        runner.check_tables()

    def test_mid_hit_edits_leave_latched_output_and_state_exact(self):
        fixed=dsp.Runner(self.receipt,self.artifact)
        edited=dsp.Runner(self.receipt,self.artifact)
        tone,decay=12345,17001
        self.assertEqual(fixed.call(tone,decay,True)[0],edited.call(tone,decay,True)[0])
        for block in range(64):
            with self.subTest(block=block):
                controls=(0,32512,32512) if block%2 else (32512,0,0)
                actual,_=edited.call(controls[0],controls[1],model=controls[2])
                self.assertEqual(actual,fixed.call(tone,decay)[0])
        base=self.receipt['state_base']
        self.assertEqual([fixed.core.peek(base+i) for i in range(0,dsp.STATE_BYTES,4)],
                         [edited.core.peek(base+i) for i in range(0,dsp.STATE_BYTES,4)])
        fixed.check_tables();edited.check_tables()

    def test_interleaved_slots_and_developed_hit_restarts_match_fresh_voices(self):
        mixed=dsp.Runner(self.receipt,self.artifact)
        other=dsp.Runner(self.receipt,self.artifact)
        other.call(32512,0,True,slot=15)
        mixed.call(32512,0,True,slot=15)
        for tone,decay in ((0,32512),(1,0),(32512,32512)):
            fresh=dsp.Runner(self.receipt,self.artifact)
            for block in range(80):
                with self.subTest(tone=tone,decay=decay,block=block):
                    expected,_=fresh.call(tone,decay,start=block==0)
                    actual,_=mixed.call(tone,decay,start=block==0)
                    self.assertEqual(actual,expected)
                    self.assertEqual(mixed.call(32512,0,slot=15)[0],
                                     other.call(32512,0,slot=15)[0])
        base=self.receipt['state_base']+15*dsp.STATE_BYTES
        self.assertEqual([mixed.core.peek(base+i) for i in range(0,dsp.STATE_BYTES,4)],
                         [other.core.peek(base+i) for i in range(0,dsp.STATE_BYTES,4)])
        mixed.check_tables();other.check_tables()

    def test_bad_slot_flags_and_state_pointer_leave_voice_untouched(self):
        runner=dsp.Runner(self.receipt,self.artifact)
        runner.call(32512,32512,True)
        base=self.receipt['state_base']
        before=[runner.core.peek(base+i) for i in range(0,dsp.STATE_BYTES,4)]
        for index,value in ((1,16),(3,2),(4,0),(5,base+4)):
            original=runner.core.poke
            def corrupt(address,data,width=1):
                if address==runner.INPUT:
                    words=list(struct.unpack('<6I',data));words[index]=value
                    data=struct.pack('<6I',*words)
                return original(address,data,width)
            with mock.patch.object(runner.core,'poke',side_effect=corrupt):
                self.assertEqual(runner.call(32512,32512,True)[0],(0.,)*32)
            self.assertEqual(before,[runner.core.peek(base+i) for i in range(0,dsp.STATE_BYTES,4)])
        runner.check_tables()

    def test_fractional_assembled_waveform_and_invalid_controls(self):
        for tone in (1,128,255,12345):
            runner=dsp.Runner(self.receipt,self.artifact)
            actual=np.concatenate([runner.call(tone,17001,start=b==0)[0] for b in range(80)])
            expected=4*field808.render(self.model,tone,17001,frames=len(actual))
            self.assertLess(float(abs(actual-expected).max()),1e-5)
        runner=dsp.Runner(self.receipt,self.artifact)
        for tone,decay,model in ((32513,0,0),(0,32513,0),(0,0,0xffffffff)):
            self.assertEqual(runner.call(tone,decay,True,model=model)[0],(0.,)*32)
        self.assertEqual(runner.core.peek(self.receipt['state_base']+244),0)


if __name__=='__main__':
    unittest.main()
