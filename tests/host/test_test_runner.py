"""An unavailable required emulator is a failed gate, not a green suite."""
from types import SimpleNamespace
import unittest
from unittest import mock

from x0x import test


class RequiredChecksTests(unittest.TestCase):
    def test_skipped_or_failed_checks_fail_the_gate(self):
        for successful, skipped, exit_code in [(True, [], 0), (False, [], 1),
                                               (True, [('component', 'missing emulator')], 1)]:
            result = SimpleNamespace(wasSuccessful=lambda: successful, skipped=skipped)
            with mock.patch.object(test.unittest.defaultTestLoader, 'discover'), \
                 mock.patch.object(test.unittest, 'TextTestRunner') as runner, \
                 mock.patch('builtins.print'):
                runner.return_value.run.return_value = result
                self.assertEqual(test.main(), exit_code)
