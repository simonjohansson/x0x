"""The physical-only observer must not alter the assembled 808's samples."""
from pathlib import Path
import struct
import tempfile
import unittest

from x0x import cpu,physical808 as probe,sharc_field808 as dsp


class PhysicalObserverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy
            cpu.require_module('tools.sharc_dev.sharc_transpile_run','digikit')
        except (ImportError,cpu.Unavailable) as error:
            raise unittest.SkipTest(str(error))
        cls.work=tempfile.TemporaryDirectory(prefix='x0x-physical-observer-')
        cls.base,cls.artifact,_,_,_=probe.instrument(Path(cls.work.name))
        import json
        cls.original=json.loads((Path(cls.work.name)/'baseline/voice.sharc.json').read_text())

    @classmethod
    def tearDownClass(cls):cls.work.cleanup()

    def test_wrapper_preserves_samples_and_records_only_its_slot(self):
        for tone,decay,slot in ((0,0,0),(32512,32512,15),(16384,16384,4)):
            raw=dsp.Runner(self.base,self.original)
            observed=dsp.Runner(self.base,self.artifact,state_bytes=probe.STATE_BYTES)
            observed.core.set_option(observed.native.OPT_INSTRUCTION_CLOCK,1)
            witness=None
            for block in range(40):
                expected,_=raw.call(tone,decay,block==0,slot)
                actual,_=observed.call(tone,decay,block==0,slot)
                self.assertEqual(actual,expected)
                if block==32:witness=actual
            address=self.base['state_base']+slot*probe.STATE_BYTES
            self.assertEqual(observed.core.peek(address+1060),40)
            self.assertEqual(observed.core.peek(address+1080),1)
            self.assertEqual(observed.core.peek(address+1084),1024)
            self.assertEqual(observed.core.peek(address+1088),tone)
            self.assertEqual(observed.core.peek(address+1092),decay)
            words=[observed.core.peek(address+1096+4*i) for i in range(32)]
            self.assertEqual(struct.unpack('<32f',struct.pack('<32I',*words)),witness)
            for other in range(16):
                if other!=slot:
                    self.assertEqual(observed.core.peek(self.base['state_base']+other*probe.STATE_BYTES+1060),0)
            observed.check_tables()
            observed.call(tone,decay,True,slot)
            self.assertEqual(observed.core.peek(address+1080),0)

    def test_909_cannot_publish_a_stale_808_age_as_a_waveform_witness(self):
        observed=dsp.Runner(self.base,self.artifact)
        for block in range(32):observed.call(16384,16384,block==0)
        address=self.base['state_base']
        self.assertEqual(observed.core.peek(address+232),1024)
        observed.call(16384,16384,True,model=32512)
        observed.call(16384,16384,model=32512)
        self.assertEqual(observed.core.peek(address+244),2)
        self.assertEqual(observed.core.peek(address+1080),0)
        observed.check_tables()

    def test_observer_regions_fit_the_expanded_owner(self):
        aligned=(self.base['data_bytes']+7)//8*8
        self.assertLessEqual(aligned+16*probe.STATE_BYTES,self.base['layout']['data_bytes'])
        self.assertEqual(self.artifact['stack_bytes'],64)
        self.assertEqual(self.artifact['voice_state']['voice_bytes'],probe.STATE_BYTES)

    def test_physical_witness_rejects_unready_corrupt_and_nonfinite_data(self):
        model=dsp.load_model()
        from x0x import field808
        expected=4*field808.render(model,16384,16384,frames=1056)[1024:]
        blob=struct.pack('<4I32f2I',1,1024,16384,16384,*expected,33077,666860)
        row=probe.compare_witness(blob,model)
        self.assertEqual((row['age'],row['tone'],row['decay']),(1024,16384,16384))
        self.assertLess(row['max_error_dsp_fs'],1e-5)
        for offset,value in ((0,0),(4,1023),(8,32768)):
            bad=bytearray(blob);struct.pack_into('<I',bad,offset,value)
            with self.assertRaises(ValueError):probe.compare_witness(bad,model)
        bad=bytearray(blob);struct.pack_into('<f',bad,16,float('nan'))
        with self.assertRaises(ValueError):probe.compare_witness(bad,model)
        with self.assertRaises(ValueError):probe.compare_witness(blob[:-1],model)
