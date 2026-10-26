import importlib
import sys
import unittest
from unittest.mock import patch

from x0z import digitone_endpoints as endpoints


class DigitoneEndpointTests(unittest.TestCase):
    def words(self, level=32634, model=32767):
        return [level, 0, 32512, min(level, 32512), 32512, model, min(model, 32512), 1, 1, 0, 0, 0]

    def test_raw_overshoot_ui_endpoint_and_canonical_model_are_independent(self):
        for level in (0, 1, 32511, 32512, 32513, 32634, 32767):
            with self.subTest(level=level):
                endpoints.validate_delivery(self.words(level), level, 32767, 1, (1, 0, 0, 0))

    def test_clipped_observation_or_rescaled_denominator_is_rejected(self):
        for index, replacement in ((0, 32512), (2, 32767), (4, 32634), (4, 32767),
                                   (5, 32512), (6, 32767), (8, True)):
            words = self.words(); words[index] = replacement
            with self.subTest(index=index, replacement=replacement), self.assertRaises(AssertionError):
                endpoints.validate_delivery(words, 32634, 32767, 1, (1, 0, 0, 0))

    def test_first_continue_preserves_unwritten_asm_notice(self):
        words = [32634, 0, 32512, 32512, 32512, 32767, 32512, 4, *([0xa5a5a5a5] * 4)]
        endpoints.validate_delivery(words, 32634, 32767, 4, None)
        words[-1] = 0
        with self.assertRaises(AssertionError):
            endpoints.validate_delivery(words, 32634, 32767, 4, None)

    def test_host_import_requires_no_emulator_or_firmware(self):
        with patch.dict(sys.modules, {"elekloader": None, "emu": None, "unicorn": None}):
            importlib.reload(endpoints)


if __name__ == "__main__":
    unittest.main()
