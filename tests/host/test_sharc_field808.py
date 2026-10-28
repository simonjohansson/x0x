"""Independent field encoding, actual parcels and isolated voice lifecycle."""
import struct
import tempfile
from pathlib import Path
import unittest

import numpy as np

from x0x import field808, sharc_field808 as dsp, sharc_layout


class SharcFieldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model=dsp.load_model()
        cls.tables=dsp.export_tables(cls.model)
        cls.folder=tempfile.TemporaryDirectory(prefix='x0x-sharc-field-')
        cls.receipt,cls.artifact=dsp.build(Path(cls.folder.name))

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def test_native_core_matches_independent_python_traces_and_write_guards(self):
        self.assertEqual(len(dsp.python_witness(self.receipt,self.artifact)),2)

    def test_exported_cubic_basis_matches_original_model(self):
        for tone,decay in ((0,0),(32512,32512),(12345,17001)):
            expected=field808.render(self.model,tone,decay,frames=4800)
            actual=dsp.render_tables(self.tables,tone,decay,frames=4800)
            self.assertLess(float(abs(expected-actual).max())*4,1e-5)
        for group in self.tables['groups']:
            self.assertTrue(np.isfinite(group['basis']).all())

    def test_real_layout_retains_explicit_909_reservations(self):
        r=self.receipt
        self.assertLessEqual(r['code_bytes']+64+3584+768+704,dsp.CODE_BYTES)
        self.assertLessEqual(r['initialized_plus_states']+1280+256+512,r['layout']['data_bytes'])
        self.assertEqual(self.artifact['voice_state']['voice_bytes'],1060)
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
        self.assertEqual(runner.call(32512,32512,True,model=32512)[0],(0.,)*32)
        self.assertEqual(runner.call(0,0)[0],(0.,)*32)
        self.assertEqual(first,runner.call(32512,32512,True)[0])
        runner.core.poke(self.receipt['state_base']+232,struct.pack('<I',264000),4)
        for _ in range(3):
            self.assertEqual(runner.call(32512,32512)[0],(0.,)*32)
        state=runner.core.peek(self.receipt['state_base']+232)
        self.assertEqual(state,264000)
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
