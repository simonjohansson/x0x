"""Frozen 909 capture scheduling and partitions, without the private recordings."""
from collections import Counter
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from x0x import fit909


class Fit909ProtocolTests(unittest.TestCase):
    def test_capture_schedule_and_grouped_partitions(self):
        events = fit909.load_events()
        self.assertEqual(len(events), 4480)
        groups = {}
        for index, event in enumerate(events):
            key = tuple(event[name+'_cc'] for name in ('tune', 'attack', 'decay'))
            self.assertEqual(groups.setdefault(key, event['partition']), event['partition'])
            self.assertEqual(event['index'], index)
            self.assertEqual(event['onset_sample'], 48000+96000*index)
            self.assertEqual(event['parameter_change_sample'], event['onset_sample']-12000)
            self.assertEqual(event['slot_frames'], 96000)
            self.assertEqual(event['start']*48000, event['onset_sample'])
            for name, value in zip(('tune', 'attack', 'decay'), key):
                self.assertTrue(0 <= value <= 127)
                self.assertEqual(event[name+'_source'], int(value*255/127+.5))
        self.assertEqual(len(groups), 4432)
        self.assertEqual(Counter(groups.values()), dict(train=1884, validation=1827, test=721))
        test = [e for e in events if e['partition']=='test']
        self.assertEqual(len(test), 724)
        self.assertEqual(sum(e['split']=='interaction' for e in events), 16**3)
        self.assertEqual(events[-1]['onset_sample']+96000, 430128000)

    def test_manifest_mutation_is_rejected_without_loading_audio(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(fit909, 'FIXTURES', Path(tmp)):
            (Path(tmp)/'events.csv').write_bytes(b'changed capture schedule')
            with self.assertRaisesRegex(ValueError, 'manifest changed'):
                fit909.load_events()
