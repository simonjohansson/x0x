from pathlib import Path
import tempfile
import unittest
from unittest import mock

from x0x import reference_grid_common as common


class ReferenceGridBootstrapTests(unittest.TestCase):
    def test_changed_frozen_source_is_rejected_before_vendor_or_cpu_use(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'tools/x0x').mkdir(parents=True)
            (root/'tools/x0x/body808.py').write_text('changed')
            with mock.patch.object(common,'_git',side_effect=[b'accepted\n',b'tools/x0x/body808.py\n',b'original']):
                with self.assertRaisesRegex(ValueError,'frozen source differs'):
                    common.prepare_frozen(root)

    def test_child_resolves_frozen_modules_before_current_vendor_modules(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with mock.patch.object(common.subprocess,'call',return_value=7) as call:
                self.assertEqual(common.frozen_invocation('driver.py',['--backend','coldfire'],root),7)
            args,kwargs=call.call_args
            self.assertEqual(args[0][-2:],['--backend','coldfire'])
            self.assertEqual(kwargs['env']['PYTHONPATH'].split(common.os.pathsep)[0],str(root.resolve()/'tools'))
            self.assertEqual(kwargs['cwd'],common.ROOT)
