import unittest
from x0x.reference808_compare import raw_position, residual


class ReferenceComparisonTests(unittest.TestCase):
    def test_capture_control_mapping_preserves_approved_default_and_corners(self):
        self.assertEqual([raw_position(x) for x in (0,128,255)],[0,16384,32512])
        for value in (-1,256,True,128.5):
            with self.assertRaises(ValueError):raw_position(value)

    def test_supplemental_shift_is_explicit_and_raw_error_stays_visible(self):
        late=[0,0,1,2,3]
        target=[1,2,3,0,0]
        self.assertGreater(residual(late,target)['rms_fs'],0)
        self.assertEqual(residual(late,target,2)['rms_fs'],0)
        self.assertEqual(residual(target,late,-2)['peak_fs'],0)
        self.assertGreater(residual(late,target)['rms_fs'],0)
