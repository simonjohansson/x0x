import copy
import unittest

from x0x import cpu, sharc_layout as private


class SharcLayoutTests(unittest.TestCase):
    def setUp(self):
        self.sdk = cpu.require_module("elekloader.sdk.sharc", "elekloader")
        self.sharc = cpu.require_module("elekloader.sharc", "elekloader")
        device = cpu.require_module("elekloader.devices.digitone_mk2", "elekloader")
        self.profile = device.DEVICE.releases["1.12"].sharc

    def test_private_partition_preserves_the_public_default(self):
        original = dict(self.sdk.machine_layout("voice"))
        self.assertEqual(private.voice_layout(), dict(code_pc16=0xBC8400,
                         code_bytes=8192, data_address=0x20092800, data_bytes=5120))
        self.assertEqual(self.sdk.machine_layout("voice"), original)
        self.assertEqual(original, dict(code_pc16=0xBC8400, code_bytes=6144,
                                       data_address=0x20092000, data_bytes=7168))

    def test_measured_pulse_size_fits_existing_owner_and_pinned_reservations(self):
        code, data = b"\x01\x00" * 3750, bytes(4736)
        doc = private.voice_artifact(code, data, 0, 20, 0)
        result = self.sharc.module_payload(doc, self.profile)
        self.assertEqual(result["owner"], self.profile["voice_range"])
        canonical = self.sdk.voice_artifact(b"\x01\x00" * 2, b"", 0, 20, 0)
        self.assertEqual(doc["segments"][0], canonical["segments"][0])
        self.assertEqual(doc["segments"][1]["offset_bytes"], 2048)
        self.assertEqual(len(bytes.fromhex(doc["segments"][1]["hex"])), 8192)
        self.assertEqual(doc["segments"][2]["offset_bytes"], 10240)
        self.assertEqual(doc["zero"], [dict(offset_bytes=14976, size_bytes=384),
                                       dict(offset_bytes=15360, size_bytes=1024)])
        self.assertEqual(doc["entries"], dict(render_offset_bytes=2048))
        self.assertEqual(code, b"\x01\x00" * 3750)
        self.assertEqual(data, bytes(4736))

    def test_exact_bounds_and_empty_data_cover_the_owner(self):
        for data in (b"", bytes(5120)):
            doc = private.voice_artifact(b"\x01\x00" * 4064, data, 8126, 20, 128)
            self.sharc.module_payload(doc, self.profile)
            self.assertEqual(doc["zero"][-1], dict(offset_bytes=15360, size_bytes=1024))

    def test_rejects_bad_code_data_and_entry(self):
        for code in (b"", b"\x00", bytes(8130), bytearray(4)):
            with self.assertRaises(ValueError):
                private.voice_artifact(code, b"", 0, 20, 0)
        for data in (bytes(2), bytes(5124), bytearray(4)):
            with self.assertRaises(ValueError):
                private.voice_artifact(bytes(4), data, 0, 20, 0)
        for entry in (-2, 1, 4, True):
            with self.assertRaises(ValueError):
                private.voice_artifact(bytes(4), b"", entry, 20, 0)

    def test_bridge_fixture_covers_the_entire_private_code_region_and_guard(self):
        from x0x.digitone2_adapter import _bridge_window
        code = b"\x03\x00" * 3750
        window = _bridge_window(code, 0xBC8400)
        layout = private.voice_layout()
        self.assertEqual(len(window), 16384)
        self.assertEqual(window[2048:2048 + len(code)], code)
        self.assertEqual(window[2048 + len(code):2048 + layout["code_bytes"]],
                         b"\x01\x00" * ((layout["code_bytes"] - len(code)) // 2))
        self.assertEqual(window[2048 + layout["code_bytes"]:15360], bytes(5120))
        canonical = self.sdk.voice_artifact(bytes(4), b"", 0, 20, 0)
        self.assertEqual(window[:2048], bytes.fromhex(canonical["segments"][0]["hex"]))
        for bad in (bytes(8130), b"\x00"):
            with self.assertRaises(ValueError):
                _bridge_window(bad, 0xBC8400)

    def test_existing_scalar_and_payload_guards_remain_enforced(self):
        for machine, stack in ((4, 0), (32, 0), (True, 0), (20, 129)):
            with self.assertRaises(self.sharc.ModError):
                private.voice_artifact(bytes(4), b"", 0, machine, stack)
        original = private.voice_artifact(bytes(4), bytes(4), 0, 20, 0)
        bad_guard = copy.deepcopy(original)
        bad_guard["segments"][1]["hex"] = bad_guard["segments"][1]["hex"][:-128] + "00" * 64
        overlap = copy.deepcopy(original)
        overlap["segments"][2]["offset_bytes"] -= 4
        bad_adapter = copy.deepcopy(original)
        adapter = bytearray.fromhex(bad_adapter["segments"][0]["hex"])
        adapter[0] ^= 1
        bad_adapter["segments"][0]["hex"] = adapter.hex()
        guard_entry = copy.deepcopy(original)
        guard_entry["entries"]["render_offset_bytes"] = 2048 + 8192 - 2
        for doc in (bad_guard, overlap, bad_adapter, guard_entry):
            with self.assertRaises(self.sharc.ModError):
                self.sharc.module_payload(doc, self.profile)
