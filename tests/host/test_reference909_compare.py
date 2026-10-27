import unittest

from x0x.reference909_compare import CASES, measurements, names, project_gain


PROJECT='''  MASTERHWOUT
  MASTER_VOLUME 1 0 -1 -1 1
  <TRACK {one}
    VOLPAN 0.25 0 1 -1 1
    REC 0 -1 0 0 0 0 0 0
      BYPASS 0 0 0
      <VST "VST3i: TR-909 (Roland) (24 out)"
      FXID {one}
'''


class Reference909Tests(unittest.TestCase):
    def test_only_fifteen_selected_training_names_are_constructed(self):
        wanted=[n for tune,decay in CASES.values() for n in names(tune,decay)]
        self.assertEqual(len(set(wanted)),15)
        self.assertTrue(all(n.startswith('grid-') and '-a128-' in n for n in wanted))
        self.assertIn('grid-u255-a128-d000-r3',wanted)
        for tune,decay in [(16,80),(128,239),(True,0),(128.5,128)]:
            with self.assertRaises(ValueError):names(tune,decay)

    def test_gain_correction_requires_the_recorded_909_routing(self):
        self.assertEqual(project_gain(PROJECT),4)
        for bad in [PROJECT.replace('VOLPAN 0.25','VOLPAN 1'),
                    PROJECT.replace('MASTER_VOLUME 1 0','MASTER_VOLUME 1 .5'),
                    PROJECT+'    HWOUT 0\n',PROJECT.replace('MASTERHWOUT\n','MASTERHWOUT 0\n'),
                    PROJECT+'      FXID {two}\n',PROJECT.replace('BYPASS 0 0 0','BYPASS 1 0 0')]:
            with self.assertRaises(AssertionError):project_gain(bad)

    def test_halfsecond_diagnostic_does_not_invent_a_full_tail_measurement(self):
        report=measurements([0.0]*24000)
        self.assertEqual(report['analysis']['duration_s'],.5)
        self.assertNotIn('energy_after_1s_fraction',report)
        self.assertTrue(all(v['median_hz'] is None and not v['reliable'] for v in report['pitch_windows'].values()))
        self.assertEqual(report['envelope_rms_10ms'],[0.0]*50)
