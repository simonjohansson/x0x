"""Validated private host fixtures and raw render results; no firmware ABI."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
PARAMETERS = {"level", "tone", "decay", "tune", "attack"}


def finite(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def text(value):
    return isinstance(value, str) and bool(value.strip())


def validate_fixture(data):
    required = {"version", "id", "model", "sample_rate", "frames", "voices",
                "initial_state", "settings", "events", "expected_audible", "provenance"}
    if not isinstance(data, dict) or set(data) != required:
        raise ValueError("fixture fields do not match the private version-1 contract")
    if type(data["version"]) is not int or data["version"] != 1:
        raise ValueError("unsupported fixture version")
    if not all(text(data[k]) for k in ("id", "model")):
        raise ValueError("fixture identity and model revision are required")
    if type(data["sample_rate"]) is not int or not 8000 <= data["sample_rate"] <= 192000:
        raise ValueError("sample_rate must be an integer in 8000..192000 Hz")
    if type(data["frames"]) is not int or not 0 < data["frames"] <= 10_000_000:
        raise ValueError("frames must be an integer in 1..10000000")
    voices = data["voices"]
    if (not isinstance(voices, list) or not voices or len(voices) > 16
            or not all(text(v) for v in voices) or len(set(voices)) != len(voices)):
        raise ValueError("voices must contain 1..16 unique logical identities")
    if data["initial_state"] != "reset":
        raise ValueError("the initial state must be explicitly reset")
    settings = data["settings"]
    if (not isinstance(settings, dict) or not settings or not set(settings) <= PARAMETERS
            or not all(finite(v) and 0 <= v <= 1 for v in settings.values())):
        raise ValueError("settings must name finite normalized control values")
    audible = data["expected_audible"]
    if (not isinstance(audible, dict) or set(audible) != set(voices)
            or not all(type(v) is bool for v in audible.values())):
        raise ValueError("each voice needs an explicit expected_audible boolean")
    provenance = data["provenance"]
    if (not isinstance(provenance, dict)
            or not all(text(provenance.get(k)) for k in ("kind", "description"))):
        raise ValueError("fixture provenance kind and description are required")
    if not isinstance(data["events"], list):
        raise ValueError("events must be a list")
    last = -1
    for event in data["events"]:
        if not isinstance(event, dict):
            raise ValueError("each event must be an object")
        sample = event.get("sample")
        if type(sample) is not int or not last <= sample < data["frames"] or sample < 0:
            raise ValueError("event times must be in range and nondecreasing")
        last = sample
        if event.get("voice") not in voices:
            raise ValueError("event has an unknown logical voice")
        kind = event.get("kind")
        if not text(kind):
            raise ValueError("event kind must be named")
        fields = {"sample", "voice", "kind"}
        if kind == "parameter":
            fields |= {"parameter", "value"}
            if (not text(event.get("parameter")) or event["parameter"] not in PARAMETERS or not finite(event.get("value"))
                    or not 0 <= event["value"] <= 1):
                raise ValueError("parameter event needs a named normalized value")
        elif kind in {"trigger", "retrigger"}:
            fields |= {"strength"}
            if not finite(event.get("strength")) or not 0 <= event["strength"] <= 1:
                raise ValueError("trigger strength must be in 0..1")
        elif kind == "reassign":
            fields |= {"identity"}
            if not text(event.get("identity")):
                raise ValueError("reassignment needs a new ownership identity")
        elif kind != "reset":
            raise ValueError("unsupported semantic event")
        if set(event) != fields:
            raise ValueError("event fields do not match its kind")
    return data


def fixture_hash(fixture):
    validate_fixture(fixture)
    raw = json.dumps(fixture, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def project_revision():
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                          text=True, capture_output=True).stdout.strip()


def make_result(fixture, backend, samples, build):
    result = dict(version=1, fixture_id=fixture["id"], fixture_sha256=fixture_hash(fixture),
                  model=fixture["model"], sample_rate=fixture["sample_rate"],
                  frames=fixture["frames"], backend=backend, output_scale="1.0 = digital full scale",
                  build=build, samples=samples)
    return validate_result(result, fixture)


def validate_result(data, fixture):
    validate_fixture(fixture)
    required = {"version", "fixture_id", "fixture_sha256", "model", "sample_rate",
                "frames", "backend", "output_scale", "build", "samples"}
    if not isinstance(data, dict) or set(data) != required or type(data["version"]) is not int or data["version"] != 1:
        raise ValueError("invalid private render result")
    for key, expected in (("fixture_id", fixture["id"]), ("fixture_sha256", fixture_hash(fixture)),
                          ("model", fixture["model"]), ("sample_rate", fixture["sample_rate"]),
                          ("frames", fixture["frames"])):
        if type(data[key]) is not type(expected) or data[key] != expected:
            raise ValueError(f"result {key} does not match the fixture")
    if data["output_scale"] != "1.0 = digital full scale" or not text(data["backend"]):
        raise ValueError("result backend and raw output scale are required")
    if not isinstance(data["build"], dict) or not all(text(data["build"].get(k)) for k in ("source_revision", "toolchain")):
        raise ValueError("result build provenance is required")
    samples = data["samples"]
    if not isinstance(samples, dict) or set(samples) != set(fixture["voices"]):
        raise ValueError("result channel routing does not match the logical voices")
    for voice, values in samples.items():
        if not isinstance(values, list) or len(values) != fixture["frames"] or not all(finite(v) for v in values):
            raise ValueError("truncated or non-finite render output")
        if fixture["expected_audible"][voice] and not any(v != 0 for v in values):
            raise ValueError(f"unexpected silence for audible voice {voice}")
        if not fixture["expected_audible"][voice] and any(v != 0 for v in values):
            raise ValueError(f"unexpected output for silent voice {voice}")
    return data


def load_json(path):
    def reject_constant(value):
        raise ValueError(f"non-finite JSON constant: {value}")
    return json.loads(Path(path).read_text(), parse_constant=reject_constant)


def write_json(path, data):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
