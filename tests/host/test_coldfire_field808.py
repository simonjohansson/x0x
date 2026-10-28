"""Independent integer and actual assembled ColdFire field checks."""
import ctypes
from pathlib import Path
import struct
import tempfile
import unittest
from x0x import cpu,coldfire_field808 as dsp,field808,sharc_field808 as shared

class ColdFireFieldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global np
        try:
            import numpy as np
            import scipy
            cpu.require_module('emu.harness','digiemu')
        except (ImportError,cpu.Unavailable) as e:raise unittest.SkipTest(str(e))
        cls.work=tempfile.TemporaryDirectory(prefix='x0x-coldfire-field-')
        cls.receipt,cls.image=dsp.build(Path(cls.work.name))
        cls.model=shared.load_model()
    @classmethod
    def tearDownClass(cls):cls.work.cleanup()

    def test_full_hit_integer_realization_matches_frozen_model(self):
        reference=dsp.Reference(Path(self.work.name))
        for tone,decay in ((0,0),(0,32512),(32512,0),(32512,32512),(16384,16384),(1,17001),(12345,17001)):
            with self.subTest(tone=tone,decay=decay):
                actual=reference.render(tone,decay)/2**31
                expected=4*field808.render(self.model,tone,decay)
                self.assertLess(float(np.abs(actual-expected).max()),1e-5)
                self.assertLess(float(np.linalg.norm(actual-expected)/np.linalg.norm(expected)),.001)

    def test_actual_asm_matches_integer_output_and_entire_state(self):
        reference=dsp.Reference(Path(self.work.name))
        for tone,decay in ((0,0),(0,32512),(32512,0),(32512,32512),(1,17001),(128,8193),(255,24320),(12345,17001)):
            actual=dsp.Runner(self.image);reference.state=(ctypes.c_int32*dsp.WORDS)()
            for block in range(96):
                self.assertEqual(actual.call(tone,decay,block==0),reference.call(tone,decay,block==0))
                self.assertEqual(bytes(actual.uc.mem_read(actual.STATES,dsp.WORDS*4)),struct.pack('>352i',*reference.state))
            actual.check_tables()

    def test_latched_controls_restarts_slots_and_silence(self):
        a=dsp.Runner(self.image);b=dsp.Runner(self.image)
        self.assertEqual(a.call(0,0),[0]*32)
        for tone,decay in ((12345,17001),(0,32512),(32512,0)):
            fresh=dsp.Runner(self.image)
            for frame in range(80):
                expected=fresh.call(tone,decay,frame==0)
                current=(tone,decay) if frame==0 else (32512,0)
                self.assertEqual(a.call(*current,start=frame==0,model=0 if frame==0 else 32512),expected)
                self.assertEqual(a.call(128,8193,start=frame==0,slot=7),b.call(128,8193,start=frame==0,slot=7))
        self.assertEqual(a.call(0,0,True,model=32512),[0]*32)
        self.assertEqual(a.call(32512,32512),[0]*32)
        a.call(0,0,True)
        a.uc.mem_write(a.STATES,struct.pack('>I',264000))
        state=bytes(a.uc.mem_read(a.STATES,dsp.WORDS*4))
        for _ in range(3):self.assertEqual(a.call(0,0),[0]*32)
        self.assertEqual(state,bytes(a.uc.mem_read(a.STATES,dsp.WORDS*4)))
        a.check_tables();b.check_tables()

    def test_continuous_envelope_bounds_refuse_insufficient_headroom(self):
        arrays,groups=dsp.export();bounds=dsp.range_bounds(arrays,groups)
        self.assertLess(bounds['horner_prefix'],24)
        arrays['cf_body']=arrays['cf_body']*2
        with self.assertRaises(ValueError):dsp.range_bounds(arrays,groups)

    def test_invalid_controls_leave_state_untouched(self):
        a=dsp.Runner(self.image);a.call(16384,16384,True)
        state=bytes(a.uc.mem_read(a.STATES,dsp.WORDS*4))
        for tone,decay,start,model in ((32513,0,True,0),(0,32513,False,0),(0,0,2,0),(0,0,True,0xffffffff)):
            self.assertEqual(a.call(tone,decay,start,model=model),[0]*32)
            self.assertEqual(state,bytes(a.uc.mem_read(a.STATES,dsp.WORDS*4)))
        a.check_tables()
