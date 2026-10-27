"""Independent 808 body oracle with provisional Decay feedback control.

This is an uncalibrated 808 starting point, with finite rectangular excitation, before pulse-edge shaping, pitch sigh,
stock Decay/Tone networks and residual-state retrigger behavior are modeled.
"""
import math

SAMPLE_RATE = 48000
# Rounded settled-body pitch from #2's five-setting training diagnostic, not circuit alignment.
FREQUENCY = 47.65
TAU = 0.143
GAIN = 0.25
PULSE_SAMPLES = 48  # Nominal 1 ms trigger in S01/S03, at 48 kHz.
PULSE_GAIN = GAIN / PULSE_SAMPLES
ATTACK_SAMPLES = 288  # S03 section8.1: 6 ms, distinct from the 1 ms drive.
# S03 equation7: R161 || (R165+R166) switches to R161 || R166.
ATTACK_FREQUENCY = FREQUENCY * math.sqrt(
    (1 / (1/1e6 + 1/53800)) / (1 / (1/1e6 + 1/6800)))


RAW_MAX = 32512
DEFAULT_DECAY = 16384
RETENTION_MIN = math.exp(-1 / (SAMPLE_RATE * .0333))
RETENTION_MAX = math.exp(-1 / (SAMPLE_RATE * .366))
RETENTION_DEFAULT = math.exp(-1 / (SAMPLE_RATE * TAU))


def retention(decay_raw):
    """Three training anchors; piecewise retention, not the stock VR6 circuit."""
    if type(decay_raw) is not int or not 0 <= decay_raw <= RAW_MAX:
        raise ValueError("Decay must be an exact native word in 0..32512")
    if decay_raw < DEFAULT_DECAY:
        return RETENTION_MIN + (RETENTION_DEFAULT - RETENTION_MIN) * decay_raw / DEFAULT_DECAY
    return RETENTION_DEFAULT + (RETENTION_MAX - RETENTION_DEFAULT) * (decay_raw - DEFAULT_DECAY) / (RAW_MAX - DEFAULT_DECAY)


def decay_tau(decay_raw):
    return -1 / (SAMPLE_RATE * math.log(retention(decay_raw)))


def _phase(sample):
    return 2*math.pi/SAMPLE_RATE * (ATTACK_FREQUENCY*min(sample, ATTACK_SAMPLES)
                                   + FREQUENCY*max(0, sample-ATTACK_SAMPLES))


def reference(frames, decay_raw=DEFAULT_DECAY, changes=None):
    """Finite-drive convolution with an integrated, two-frequency phase."""
    changes = changes or {}
    loss = math.log(retention(decay_raw))
    attenuation = 0.0
    samples = []
    cosine_sum = sine_sum = 0.0
    for n in range(frames):
        if n in changes:
            loss = math.log(retention(changes[n]))
        if n < PULSE_SAMPLES:
            weight = PULSE_GAIN * math.exp(-attenuation)
            cosine_sum += weight * math.cos(_phase(n))
            sine_sum += weight * math.sin(_phase(n))
        attenuation += loss
        samples.append(math.exp(attenuation) * (cosine_sum * math.sin(_phase(n+1))
                                               - sine_sum * math.cos(_phase(n+1))))
    return samples


def compare():
    """Compare the current production body, Tone and coupling on both CPUs."""
    from .tone808 import compare as compare_tone
    return compare_tone()


if __name__ == "__main__":
    import json
    print(json.dumps(compare()))
