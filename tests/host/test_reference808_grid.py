import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from x0x import reference808_grid as grid
from x0x import reference_grid_common as common
from x0x.reference808_grid import FRAMES, WINDOWS, grid_records, pitch_windows, unchanged_readbacks


class Full808GridTests(unittest.TestCase):
    def metadata(self, folder, mutate=None):
        values = [0, 32, 64, 96, 128, 159, 191, 223, 255]
        rows = [dict(name=f'grid-t{t:03}-d{d:03}-r{r}', split='grid',
                     tone_displayed=t, decay_displayed=d)
                for t in values for d in values for r in (1, 2, 3)]
        rows += [dict(name='validation-do-not-open', split='validation',
                      tone_displayed=16, decay_displayed=16)]
        if mutate:
            mutate(rows)
        path = Path(folder)
        with (path/'recordings.csv').open('w') as stream:
            writer = csv.DictWriter(stream, fieldnames=rows[0])
            writer.writeheader(); writer.writerows(rows)
        return path

    def test_training_selection_excludes_validation_without_opening_audio(self):
        with tempfile.TemporaryDirectory() as folder:
            rows = grid_records(self.metadata(folder))
        self.assertEqual(len(rows), 243)
        self.assertNotIn('validation-do-not-open', {r['name'] for r in rows})

    def test_duplicate_or_wrong_repeat_cannot_masquerade_as_full_grid(self):
        for mutate in [lambda r: r.__setitem__(0, r[1].copy()),
                       lambda r: r[0].__setitem__('name', 'grid-t000-d000-r4'),
                       lambda r: r.pop(0)]:
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as folder:
                with self.assertRaises(AssertionError):
                    grid_records(self.metadata(folder, mutate))

    def test_sparse_pitch_windows_are_not_reported_as_reliable(self):
        cycle = dict(frequency_hz=48.0, valid=True, start_sample=3000, end_sample=4000)
        for count in (0, 1, 2, 3):
            result = pitch_windows({'frequency': {'cycles': [cycle] * count}})['body']
            self.assertEqual(result['reliable'], count >= 3)
            self.assertEqual(result['median_hz'], 48.0 if count >= 3 else None)

    def test_readback_changes_beyond_plugin_controls_are_rejected(self):
        before = {i: {'normalized': '0.5'} for i in range(193)}
        after = {i: dict(row) for i, row in before.items()}
        unchanged_readbacks(before, after)
        after[100]['normalized'] = '0.6'
        with self.assertRaises(AssertionError):
            unchanged_readbacks(before, after)

    def test_full_tail_windows_cover_twelve_seconds(self):
        self.assertEqual(FRAMES, 576000)
        self.assertEqual(WINDOWS[-1], ('whole12s', 0, 12))
        self.assertEqual([(a,b) for name,a,b in WINDOWS if name.startswith('tail')],
                         [(2,4), (4,8), (8,12)])

    def test_explicit_revision_reaches_both_comparisons(self):
        revision='b'*40
        with mock.patch.object(sys,'argv',['reference808_grid','--revision','HEAD']), \
             mock.patch.object(common,'_git',return_value=(revision+'\n').encode()), \
             mock.patch.object(grid,'compare') as compare, \
             mock.patch.object(grid,'compare_histories') as histories:
            grid.main()
        compare.assert_called_once_with(Path('research/reference/808/captures'),Path('out/reference/808-grid'),revision)
        histories.assert_called_once_with(Path('research/reference/808/captures'),Path('out/reference/808-grid'),revision)

    def test_wrong_revision_or_failed_numeric_receipt_rejected_before_audio(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)
            for receipt,message in [({'commit':'old'},'render revision differs'),
                                    ({'commit':'selected','status':'failed'},'numeric render is not qualified')]:
                (p/'report.json').write_text(json.dumps(receipt))
                with self.subTest(receipt=receipt),self.assertRaisesRegex(AssertionError,message):
                    grid.load_backend(p,'selected')

    def test_package_entry_can_render_without_direct_file_reentry(self):
        from x0x import cpu
        revision='b'*40
        metadata={'commit':revision,'frozen_source_root':str(cpu.ROOT)}
        with tempfile.TemporaryDirectory() as folder:
            argv=['reference808_grid','--backend','coldfire','--revision','HEAD',
                  '--frozen-source',str(cpu.ROOT),'--output',folder]
            with mock.patch.object(sys,'argv',argv), \
                 mock.patch.object(common,'_git',return_value=(revision+'\n').encode()), \
                 mock.patch.object(common,'prepare_frozen',return_value=metadata), \
                 mock.patch('x0x.reference808_grid_render.render') as render:
                grid.main()
            render.assert_called_once_with('coldfire',Path(folder).resolve(),
                                           Path('research/reference/808/captures').resolve(),metadata)
