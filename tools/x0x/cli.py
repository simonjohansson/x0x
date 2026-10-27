"""Commands for synthetic host renders and explicit measurement comparisons."""
import argparse
import json
from pathlib import Path
import sys
import wave

from .analysis import analyze
from .audio import read_wav, write_wav
from .comparison import compare_backends
from .fixtures import load_json, validate_fixture, validate_result, write_json
from .oracle import render_diagnostic


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    render = commands.add_parser("render")
    render.add_argument("fixture")
    render.add_argument("--out", required=True)
    render.add_argument("--wav")
    render.add_argument("--voice", default=None)
    measure = commands.add_parser("analyze")
    measure.add_argument("input")
    measure.add_argument("--fixture")
    measure.add_argument("--out")
    compare = commands.add_parser("compare")
    compare.add_argument("fixture")
    compare.add_argument("oracle")
    compare.add_argument("--coldfire")
    compare.add_argument("--sharc")
    compare.add_argument("--tolerances", required=True)
    compare.add_argument("--out")
    unavailable = commands.add_parser("unavailable")
    unavailable.add_argument("device", choices=("dt", "dn", "dn2"))
    args = parser.parse_args(argv)
    try:
        if args.command == "unavailable":
            print(json.dumps(dict(status="unavailable", device=args.device,
                  reason="This explicit placeholder does not run native tests; use mise run test:" + args.device)))
            return 77
        if args.command == "render":
            fixture = validate_fixture(load_json(args.fixture))
            result = render_diagnostic(fixture)
            if args.wav:
                voice = args.voice or fixture["voices"][0]
                if voice not in result["samples"]:
                    raise ValueError("unknown output voice")
                write_wav(args.wav, result["samples"][voice], result["sample_rate"])
            write_json(args.out, result)
            print(json.dumps(dict(status="rendered", output=args.out, backend=result["backend"])))
            return 0
        if args.command == "analyze":
            if Path(args.input).suffix.lower() == ".wav":
                samples, rate = read_wav(args.input)
                if args.fixture:
                    raise ValueError("a standalone WAV has no fixture/build provenance; use a render result for fixture matching")
                report = analyze(samples, rate)
            else:
                if not args.fixture:
                    raise ValueError("a render result needs --fixture for identity and extent validation")
                fixture = validate_fixture(load_json(args.fixture))
                result = validate_result(load_json(args.input), fixture)
                report = {voice: analyze(values, result["sample_rate"]) for voice, values in result["samples"].items()}
            if args.out:
                write_json(args.out, report)
            else:
                print(json.dumps(report, allow_nan=False))
            return 0
        fixture = validate_fixture(load_json(args.fixture))
        oracle = validate_result(load_json(args.oracle), fixture)
        if "oracle" not in oracle["backend"]:
            raise ValueError("the independent oracle result must be identified as an oracle")
        backends = {}
        for name in ("coldfire", "sharc"):
            path = getattr(args, name)
            if path:
                result = validate_result(load_json(path), fixture)
                if result["backend"] != name:
                    raise ValueError("result backend identity does not match its requested CPU")
                backends[name] = result
        limits = load_json(args.tolerances)
        voices = {}
        for voice in fixture["voices"]:
            inputs = {name: result["samples"][voice] for name, result in backends.items()}
            voices[voice] = compare_backends(oracle["samples"][voice], fixture["sample_rate"], limits, **inputs)
        status = ("unavailable" if not backends else
                  "passed" if all(r["status"] == "passed" for r in voices.values()) else "failed")
        report = dict(status=status, fixture_sha256=oracle["fixture_sha256"], voices=voices)
        if args.out:
            write_json(args.out, report)
        else:
            print(json.dumps(report, allow_nan=False))
        return {"passed": 0, "failed": 1, "unavailable": 77}[status]
    except (ValueError, OSError, wave.Error) as error:
        print(json.dumps(dict(status="failed", reason=str(error))))
        return 1


if __name__ == "__main__":
    sys.exit(main())
