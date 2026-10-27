"""Independent 55 Hz body oracle with provisional Decay feedback control.

This is an uncalibrated 808 starting point, before excitation, pitch sigh,
stock Decay/Tone networks and residual-state retrigger behavior are modeled.
"""
import math

SAMPLE_RATE = 48000
FREQUENCY = 55.0
TAU = 0.25
GAIN = 0.25


RAW_MAX = 32512
DEFAULT_DECAY = 16384
RETENTION_MAX = math.exp(-1 / SAMPLE_RATE)  # One-second maximum amplitude time constant.
RETENTION_DEFAULT = math.exp(-1 / (SAMPLE_RATE * TAU))
RETENTION_MIN = ((RETENTION_DEFAULT - (DEFAULT_DECAY / RAW_MAX) * RETENTION_MAX)
                 / (1 - DEFAULT_DECAY / RAW_MAX))


def retention(decay_raw):
    """Provisional linear feedback retention, not a stock VR6 circuit/pot curve."""
    if type(decay_raw) is not int or not 0 <= decay_raw <= RAW_MAX:
        raise ValueError("Decay must be an exact native word in 0..32512")
    return RETENTION_MIN + (RETENTION_MAX - RETENTION_MIN) * decay_raw / RAW_MAX


def decay_tau(decay_raw):
    return -1 / (SAMPLE_RATE * math.log(retention(decay_raw)))


def reference(frames, decay_raw=DEFAULT_DECAY, changes=None):
    """Analytical phase and integrated log attenuation; changes apply before sample n."""
    changes = changes or {}
    loss = math.log(retention(decay_raw))
    attenuation = 0.0
    samples = []
    for n in range(frames):
        if n in changes:
            loss = math.log(retention(changes[n]))
        attenuation += loss
        samples.append(GAIN * math.exp(attenuation)
                       * math.sin(2 * math.pi * FREQUENCY * (n + 1) / SAMPLE_RATE))
    return samples


def compare():
    """Compare the current production body plus Tone stage on both CPUs."""
    from .tone808 import compare as compare_tone
    return compare_tone()


if __name__ == "__main__":
    import json
    print(json.dumps(compare()))
