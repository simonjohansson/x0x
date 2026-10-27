import copy
import unittest
from types import SimpleNamespace

from x0x.digitone2_adapter import CASES, check_bridge_writes, validate_trace


def trace():
    records = []
    for index, (slot, flags, value) in enumerate(CASES):
        params = [0] * 40
        params[0], params[8] = value, 257 + index
        records.append(dict(slot=slot, pitch=60 * 256 + 127, flags=flags, params=params))
    return records


class Digitone2AdapterTraceTests(unittest.TestCase):
    def test_unbacked_exclusive_end_cannot_expand_bridge_write_ownership(self):
        # The loaded L2 window ends just before 0x20094000. Its exclusive
        # end aliases, while its last byte and the bridge region stay direct.
        canonicalize = lambda address: address if address < 0x20094000 else address + 0x28000000
        region = [(0x20093c00, 0x20094000)]
        check_bridge_writes([SimpleNamespace(address=0x20093ffc, width=4)], region, canonicalize)
        for address, width in [(0x28200000, 4), (0x20094000, 4), (0x20093fff, 2)]:
            with self.subTest(address=address), self.assertRaisesRegex(AssertionError, "unowned memory"):
                check_bridge_writes([SimpleNamespace(address=address, width=width)], region, canonicalize)

    def test_fractional_snapshot_and_voice_slot_survive_the_boundary(self):
        records = validate_trace(trace())
        self.assertEqual(records[0]["slot"], 15)
        self.assertEqual(records[0]["params"][0], 1)
        self.assertEqual(records[3]["params"][0], 12345)
        self.assertEqual(records[4]["flags"], 1)

    def test_corrupt_or_undeclared_delivery_is_rejected(self):
        for field, value in [("slot", 0), ("slot", True), ("pitch", 60), ("flags", 0),
                             ("flags", True), ("params", None), ("params", [0] * 39)]:
            records = trace()
            records[0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                validate_trace(records)
        for position, value in [(0, 0), (8, 256), (39, 1), (0, True), (0, 32513)]:
            records = trace()
            records[0]["params"][position] = value
            with self.subTest(position=position, value=value), self.assertRaises(ValueError):
                validate_trace(records)

    def test_missing_callback_or_extra_metadata_cannot_pass(self):
        with self.assertRaises(ValueError):
            validate_trace(trace()[:-1])
        records = copy.deepcopy(trace())
        records[0]["claimed_native_lock"] = True
        with self.assertRaises(ValueError):
            validate_trace(records)


if __name__ == "__main__":
    unittest.main()
