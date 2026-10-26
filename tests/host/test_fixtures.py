import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
import wave

from x0z.audio import read_wav, write_wav
from x0z.cli import main
from x0z.fixtures import fixture_hash, load_json, validate_fixture, validate_result, write_json
from x0z.oracle import render_diagnostic

ROOT = Path(__file__).resolve().parents[2]


def fixture():
    return load_json(ROOT / "tests/fixtures/diagnostic.json")


class FixtureTests(unittest.TestCase):
    def test_analytic_impulses_retrigger_and_tied_events(self):
        result = render_diagnostic(fixture())
        a, b = result["samples"]["A"], result["samples"]["B"]
        self.assertEqual(a[:31], [0] * 31)
        self.assertEqual(a[31:34], [.375, .1875, .21875])
        self.assertEqual(a[64:67], [.125, .0625, .03125])
        self.assertEqual(b[32], .25)
        self.assertEqual(b[64], .25 * 2 ** -32)

    def test_unrelated_voice_events_do_not_change_output(self):
        original = fixture()
        other = copy.deepcopy(original)
        other["events"].insert(4, dict(sample=64, voice="B", kind="reset"))
        self.assertEqual(render_diagnostic(original)["samples"]["A"],
                         render_diagnostic(other)["samples"]["A"])

    def test_equal_time_order_is_not_silently_sorted(self):
        data = fixture()
        data["voices"] = ["A"]
        data["expected_audible"] = {"A": False}
        data["events"] = [dict(sample=0, voice="A", kind="trigger", strength=1),
                          dict(sample=0, voice="A", kind="reset")]
        self.assertEqual(render_diagnostic(data)["samples"]["A"], [0] * 128)
        data["events"].reverse()
        data["expected_audible"]["A"] = True
        self.assertEqual(render_diagnostic(data)["samples"]["A"][0], .5)

    def test_reset_retains_settings_and_reassignment_clears_history(self):
        data = fixture()
        data["voices"] = ["A"]
        data["expected_audible"] = {"A": True}
        data["events"] = [dict(sample=0, voice="A", kind="parameter", parameter="level", value=.25),
                          dict(sample=0, voice="A", kind="trigger", strength=1),
                          dict(sample=1, voice="A", kind="reassign", identity="new-owner"),
                          dict(sample=1, voice="A", kind="trigger", strength=.5)]
        self.assertEqual(render_diagnostic(data)["samples"]["A"][:3], [.25, .125, .0625])

    def test_a_fresh_trigger_cannot_discard_a_live_tail(self):
        data = fixture()
        data["events"][2]["kind"] = "trigger"
        with self.assertRaisesRegex(ValueError, "quiescent"):
            render_diagnostic(data)

    def test_malformed_fixtures_fail(self):
        changes = [dict(version=True), dict(frames=0), dict(sample_rate=48000.0),
                   dict(voices=["A", "A"]), dict(initial_state="unknown"),
                   dict(settings={"level": float("nan")}), dict(settings={"level": True}),
                   dict(settings={"level": 10 ** 400}),
                   dict(expected_audible={"A": True}), dict(provenance={})]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_fixture(fixture() | change)
        for change in [dict(sample=-1), dict(sample=128), dict(sample=True),
                       dict(voice="unknown"), dict(kind=[]), dict(strength=float("inf")),
                       dict(unexpected="field")]:
            data = fixture()
            data["events"][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_fixture(data)
        data = fixture()
        data["events"].reverse()
        with self.assertRaisesRegex(ValueError, "nondecreasing"):
            validate_fixture(data)

    def test_render_identity_provenance_extent_and_routing_are_checked(self):
        data = fixture()
        result = render_diagnostic(data)
        for key, value in [("fixture_sha256", "wrong"), ("sample_rate", 44100),
                           ("model", "808"), ("frames", 1), ("build", {}),
                           ("output_scale", "normalized")]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_result(result | {key: value}, data)
        for samples in [{"A": [0] * 128}, {"A": [0] * 128, "B": [0] * 128},
                        {"A": result["samples"]["A"][:-1], "B": result["samples"]["B"]},
                        {"A": [float("nan")] * 128, "B": result["samples"]["B"]}]:
            with self.subTest(samples=list(samples)), self.assertRaises(ValueError):
                validate_result(result | {"samples": samples}, data)

    def test_hash_covers_settings_and_events_not_object_key_order(self):
        data = fixture()
        self.assertEqual(fixture_hash(data), fixture_hash(dict(reversed(list(data.items())))))
        altered = copy.deepcopy(data)
        altered["events"][0]["strength"] = .5
        self.assertNotEqual(fixture_hash(data), fixture_hash(altered))

    def test_intentional_silence_is_valid(self):
        data = fixture()
        data["events"] = []
        data["expected_audible"] = {"A": False, "B": False}
        result = render_diagnostic(data)
        self.assertEqual(result["samples"]["A"], [0] * data["frames"])
        result["samples"]["A"][17] = .0001
        with self.assertRaisesRegex(ValueError, "silent voice"):
            validate_result(result, data)


class AudioTests(unittest.TestCase):
    def test_pcm_round_trip_has_explicit_quantization(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.wav"
            expected = [-1.0, -.25, 0, .25, 1]
            write_wav(path, expected, 48000)
            actual, rate = read_wav(path)
            self.assertEqual(rate, 48000)
            for a, b in zip(actual, expected):
                self.assertLessEqual(abs(a - b), 1 / 32768)
            with self.assertRaisesRegex(ValueError, "clipping"):
                write_wav(path, [1.1], 48000)

    def test_wrong_channel_routing_and_truncated_pcm_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.wav"
            with wave.open(str(path), "wb") as wav:
                wav.setparams((2, 2, 48000, 0, "NONE", "not compressed"))
                wav.writeframes(b"\0" * 8)
            with self.assertRaisesRegex(ValueError, "mono"):
                read_wav(path)
            with wave.open(str(path), "wb") as wav:
                wav.setparams((1, 2, 48000, 0, "NONE", "not compressed"))
                wav.writeframes(b"\0\1\2")
            with self.assertRaisesRegex(ValueError, "truncated"):
                read_wav(path)
            write_wav(path, [.25] * 8, 48000)
            path.write_bytes(path.read_bytes()[:-2])
            with self.assertRaisesRegex(ValueError, "truncated"):
                read_wav(path)


class CommandTests(unittest.TestCase):
    def call(self, *args):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            code = main(list(args))
        return code, json.loads(output.getvalue())

    def test_render_analyze_and_missing_peer_status(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "result.json"
            fixture_path = str(ROOT / "tests/fixtures/diagnostic.json")
            self.assertEqual(self.call("render", fixture_path, "--out", str(target))[0], 0)
            self.assertEqual(self.call("analyze", str(target), "--fixture", fixture_path)[0], 0)
            limits = str(ROOT / "tests/fixtures/diagnostic-tolerances.json")
            code, report = self.call("compare", fixture_path, str(target), "--tolerances", limits)
            self.assertEqual((code, report["status"]), (77, "unavailable"))
            backend = load_json(target)
            backend["backend"] = "coldfire"
            peer = Path(directory) / "coldfire.json"
            write_json(peer, backend)
            code, report = self.call("compare", fixture_path, str(target), "--coldfire", str(peer), "--tolerances", limits)
            self.assertEqual((code, report["status"]), (0, "passed"))
            backend["samples"]["A"][31] *= .5
            write_json(peer, backend)
            self.assertEqual(self.call("compare", fixture_path, str(target), "--coldfire", str(peer), "--tolerances", limits)[0], 1)

    def test_device_suites_are_unavailable_not_successful_placeholders(self):
        for device in ("dt", "dn", "dn2"):
            code, report = self.call("unavailable", device)
            self.assertEqual((code, report["status"]), (77, "unavailable"))


if __name__ == "__main__":
    unittest.main()
