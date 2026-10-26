"""Synthetic test equipment, not an 808 or 909 model."""
import platform

from .fixtures import make_result, project_revision, validate_fixture


def render_diagnostic(fixture):
    """A one-pole impulse probe with closed-form amplitude strength * 2**-age."""
    validate_fixture(fixture)
    if fixture["model"] != "diagnostic-pole-v1" or set(fixture["settings"]) != {"level"}:
        raise ValueError("the diagnostic oracle only supports diagnostic-pole-v1 with Level")
    state = {voice: 0.0 for voice in fixture["voices"]}
    level = {voice: fixture["settings"]["level"] for voice in state}
    output = {voice: [] for voice in state}
    events = iter(fixture["events"])
    event = next(events, None)
    for sample in range(fixture["frames"]):
        while event is not None and event["sample"] == sample:
            voice, kind = event["voice"], event["kind"]
            if kind in {"reset", "reassign"}:
                state[voice] = 0.0
            elif kind == "parameter":
                if event["parameter"] != "level":
                    raise ValueError("the diagnostic probe only consumes Level")
                level[voice] = event["value"]
            elif kind == "trigger":
                if state[voice] != 0:
                    raise ValueError("fresh trigger requires explicitly quiescent state")
                state[voice] = event["strength"]
            else:
                state[voice] += event["strength"]
            event = next(events, None)
        for voice in state:
            output[voice].append(level[voice] * state[voice])
            state[voice] *= .5
    return make_result(fixture, "host-diagnostic-oracle", output,
                       dict(source_revision=project_revision(), toolchain="CPython " + platform.python_version()))
