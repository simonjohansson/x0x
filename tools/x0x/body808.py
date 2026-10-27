"""Independent 808 body oracle with provisional Decay feedback control.

Shaped main and companion inputs use calibrated pole frequencies/losses. The Q43 hard-knee leakage adds amplitude-dependent pitch sigh; full
feedback, soft-knee transistor behavior, loaded output and residual retrigger remain open.
"""
import math

SAMPLE_RATE = 48000
# Rounded settled-body pitch from #2's five-setting training diagnostic, not circuit alignment.
FREQUENCY = 47.65
TAU = 0.143
GAIN = 0.25
PULSE_SAMPLES = 48  # Nominal 1 ms trigger in S01/S03, at 48 kHz.
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


def switch_coordinates(decay_raw):
    """Keep output and C41/C42 voltage when the calibrated pole pair changes.

    shortcut: effective constant damping, not the complete feedback shelf;
    this state conversion addresses only the initial frequency transition.
    """
    sigma = -SAMPLE_RATE * math.log(retention(decay_raw))
    low, high = 2*math.pi*FREQUENCY, 2*math.pi*ATTACK_FREQUENCY
    ratio = (sigma*sigma + low*low)/(sigma*sigma + high*high)
    return ratio*high/low, (ratio-1)*sigma/low


def reference(frames, decay_raw=DEFAULT_DECAY, changes=None):
    from .leakage808 import reference as leakage_reference
    return leakage_reference(frames, decay_raw, changes)


def compare():
    """Compare the current production body, Tone and coupling on both CPUs."""
    from .tone808 import compare as compare_tone
    return compare_tone()


if __name__ == "__main__":
    import json
    print(json.dumps(compare()))
