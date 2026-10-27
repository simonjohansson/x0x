import csv
import itertools
from pathlib import Path
import tempfile
import unittest

from x0x.reference909_grid import FRAMES, POSITIONS, WINDOWS, grid_records


class Full909GridTests(unittest.TestCase):
    def metadata(self,folder,mutate=None):
        rows=[dict(name=f'grid-u{t:03}-a{a:03}-d{d:03}-r{r}',split='grid',tune_displayed=t,attack_displayed=a,decay_displayed=d)
              for t,a,d in itertools.product(POSITIONS,repeat=3) for r in (1,2,3)]
        rows.append(dict(name='validation-do-not-open',split='validation',tune_displayed=17,attack_displayed=23,decay_displayed=31))
        rows.append(dict(name='history-do-not-infer',split='history',tune_displayed=128,attack_displayed=128,decay_displayed=128))
        if mutate:mutate(rows)
        path=Path(folder)
        with (path/'recordings.csv').open('w') as stream:
            writer=csv.DictWriter(stream,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
        return path

    def test_all_729_training_settings_keep_three_takes_and_exclude_reserved_audio(self):
        with tempfile.TemporaryDirectory() as folder:
            rows=grid_records(self.metadata(folder))
        self.assertEqual(len(rows),2187)
        self.assertEqual(len({(r['tune_displayed'],r['attack_displayed'],r['decay_displayed']) for r in rows}),729)
        self.assertTrue(all(r['name'].startswith('grid-') for r in rows))

    def test_duplicate_missing_mislabelled_or_wrong_repeat_is_not_complete_grid(self):
        mutations=(lambda r:r.__setitem__(0,r[1].copy()),lambda r:r.pop(0),
                   lambda r:r[0].__setitem__('name','grid-u000-a000-d000-r4'),
                   lambda r:r[0].__setitem__('attack_displayed',32),lambda r:r.append(r[0].copy()))
        for mutate in mutations:
            with self.subTest(mutate=mutate),tempfile.TemporaryDirectory() as folder:
                with self.assertRaises(AssertionError):grid_records(self.metadata(folder,mutate))

    def test_primary_windows_retain_all_sixteen_seconds_including_late_dc(self):
        self.assertEqual(FRAMES,768000)
        self.assertEqual(WINDOWS['full16s'],(0,768000))
        self.assertEqual(WINDOWS['tail2to16s'],(96000,768000))
        self.assertEqual(WINDOWS['first150ms'],(0,7200))


if __name__=='__main__':unittest.main()
