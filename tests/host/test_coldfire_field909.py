"""Actual ColdFire 909 against independent integer and waveform references."""
import ctypes
import itertools
import struct
import tempfile
import unittest
from pathlib import Path
import numpy as np
from x0x import coldfire_field909 as dsp,field909


class ColdFire909Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder=tempfile.TemporaryDirectory(prefix='x0x-cf909-')
        cls.receipt,cls.image=dsp.build(Path(cls.folder.name))
        cls.reference=dsp.Reference(Path(cls.folder.name));cls.model=field909.load()

    @classmethod
    def tearDownClass(cls):cls.folder.cleanup()

    def test_complete_corner_and_fractional_hits_match_integer_reference(self):
        cases=list(itertools.product((0,32512),repeat=3))+[(1,255,32511),(12345,23001,17001)]
        for controls in cases:
            with self.subTest(controls=controls):
                runner=dsp.Runner(self.image,guarded=False);self.reference.state=(ctypes.c_int32*352)();values=[]
                for b in range(3000):
                    actual=runner.call(*controls,start=b==0)
                    self.assertEqual(actual,self.reference.call(*controls,start=b==0))
                    self.assertEqual(bytes(runner.uc.mem_read(runner.STATES,1408)),struct.pack('>352i',*self.reference.state))
                    values.extend(actual)
                y=np.asarray(values)/2**31;target=4*field909.render(self.model,*controls)
                self.assertLess(float(abs(y-target).max()),1e-5)
                self.assertEqual(runner.call(*controls),[0]*32)
                runner.check_tables()

    def test_guarded_callbacks_latch_controls_and_keep_independent_slots(self):
        runner=dsp.Runner(self.image);other=dsp.Runner(self.image)
        for b in range(40):
            expected=other.call(12345,23001,17001,start=b==0)
            actual=runner.call(12345 if b==0 else 0,23001 if b==0 else 0,17001 if b==0 else 0,start=b==0)
            self.assertEqual(actual,expected)
            runner.call(32512,0,0,start=b==0,slot=7)
        before=bytes(runner.uc.mem_read(runner.STATES,1408))
        for controls in ((32513,0,0),(0,0xffffffff,0),(0,0,32513)):
            self.assertEqual(runner.call(*controls,start=True),[0]*32)
            self.assertEqual(before,bytes(runner.uc.mem_read(runner.STATES,1408)))
        self.assertEqual(runner.call(12345,23001,17001,start=True),other.call(12345,23001,17001,start=True))
        self.assertLess(runner.maximum_instructions,40000)
        runner.check_tables()

    def test_continuous_fixed_point_horner_ranges_and_data_size(self):
        bounds=self.receipt['range_bounds']
        self.assertLess(bounds['control_horner'],4-bounds['rounding_margin'])
        self.assertLess(bounds['body_horner'],8-bounds['rounding_margin'])
        self.assertLess(self.receipt['image_bytes']+8*1412,256*1024)
        with self.assertRaises(ValueError):dsp.quantize([float('nan')],29)
        with self.assertRaises(ValueError):dsp.quantize([4],29)
