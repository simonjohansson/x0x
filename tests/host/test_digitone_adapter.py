import contextlib
import io
import json
import unittest
from unittest.mock import patch

from x0z import digitone_adapter as adapter
from x0z.cpu import Unavailable


class DigitoneAdapterCommandTests(unittest.TestCase):
    def test_missing_tools_are_unavailable_not_passed(self):
        output = io.StringIO()
        with patch.object(adapter, "verify_host", side_effect=Unavailable("compiler missing")):
            with contextlib.redirect_stdout(output):
                self.assertEqual(adapter.main(["--host"]), 77)
        self.assertEqual(json.loads(output.getvalue())["status"], "unavailable")

    def test_memory_or_control_corruption_is_a_failure(self):
        output = io.StringIO()
        with patch.object(adapter, "verify", side_effect=AssertionError("native fraction lost")):
            with contextlib.redirect_stdout(output):
                self.assertEqual(adapter.main([]), 1)
        self.assertEqual(json.loads(output.getvalue())["status"], "failed")

    def test_host_path_does_not_start_an_emulator(self):
        output = io.StringIO()
        with patch.object(adapter, "verify_host", return_value={"kind": "host"}), patch.object(adapter, "verify", side_effect=AssertionError("emulator started")):
            with contextlib.redirect_stdout(output):
                self.assertEqual(adapter.main(["--host"]), 0)
        self.assertEqual(json.loads(output.getvalue())["kind"], "host")


if __name__ == "__main__":
    unittest.main()
