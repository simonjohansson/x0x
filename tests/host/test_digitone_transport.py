import copy
import importlib
import sys
import unittest
from unittest.mock import patch

from x0z import digitone_transport as transport


class DigitoneTransportTraceTests(unittest.TestCase):
    def traces(self):
        return [dict(block=index + 1, order=list(transport.ORDER), pointer=pointer,
                     late_pointer=pointer, pre=370 + index, final=2402 + index, late=2402 + index)
                for index, pointer in enumerate(transport.POINTERS)]

    def test_fractional_final_words_and_missing_capture(self):
        traces = self.traces()
        transport.validate_trace(traces)
        traces[1].update(late_pointer=0, late=None)
        transport.validate_trace(traces)

    def test_early_target_wrong_bank_or_stale_block_is_rejected(self):
        for change in (dict(late=12345), dict(late=370), dict(final=None),
                       dict(late_pointer=0),
                       dict(late_pointer=transport.POINTERS[0]), dict(block=1),
                       dict(order=transport.ORDER[:-1]), dict(pointer=transport.POINTERS[0])):
            traces = copy.deepcopy(self.traces())
            traces[1].update(change)
            with self.subTest(change=change), self.assertRaises(AssertionError):
                transport.validate_trace(traces)
        with self.assertRaises(AssertionError):
            transport.validate_trace([])

    def test_host_import_does_not_load_firmware_or_emulator(self):
        with patch.dict(sys.modules, {"elekloader": None, "emu": None, "unicorn": None}):
            importlib.reload(transport)

    def test_boolean_values_cannot_stand_in_for_native_words(self):
        for change in (dict(block=True), dict(pre=False), dict(final=False, late=False)):
            traces = self.traces()
            traces[0].update(change)
            with self.subTest(change=change), self.assertRaises(AssertionError):
                transport.validate_trace(traces)


if __name__ == "__main__":
    unittest.main()
