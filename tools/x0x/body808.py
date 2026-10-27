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


def switch_coordinates(decay_raw):
    """Keep output and C41/C42 voltage when the calibrated pole pair changes.

    shortcut: effective constant damping, not the complete feedback shelf;
    this state conversion addresses only the initial frequency transition.
    """
    sigma = -SAMPLE_RATE * math.log(retention(decay_raw))
    low, high = 2*math.pi*FREQUENCY, 2*math.pi*ATTACK_FREQUENCY
    ratio = (sigma*sigma + low*low)/(sigma*sigma + high*high)
    return ratio*high/low, (ratio-1)*sigma/low


def _main_reference(frames, decay_raw=DEFAULT_DECAY, changes=None):
    """Finite-drive convolution, then free decay from conserved capacitor state."""
    changes = changes or {}
    loss = math.log(retention(decay_raw))
    attenuation = 0.0
    samples = []
    cosine_sum = sine_sum = 0.0
    for n in range(frames):
        if n in changes:
            decay_raw = changes[n]
            loss = math.log(retention(decay_raw))
        if n < PULSE_SAMPLES:
            weight = PULSE_GAIN * math.exp(-attenuation)
            cosine_sum += weight * math.cos(_phase(n))
            sine_sum += weight * math.sin(_phase(n))
        attenuation += loss
        if n < ATTACK_SAMPLES:
            angle = _phase(n+1)
            sample = math.exp(attenuation) * (cosine_sum*math.sin(angle)-sine_sum*math.cos(angle))
            if n+1 == ATTACK_SAMPLES:
                quadrature = math.exp(attenuation) * (cosine_sum*math.cos(angle)+sine_sum*math.sin(angle))
                alpha, beta = switch_coordinates(decay_raw)
                switch_x, switch_y = sample, alpha*quadrature+beta*sample
                switch_attenuation = attenuation
        else:
            angle = 2*math.pi*FREQUENCY*(n+1-ATTACK_SAMPLES)/SAMPLE_RATE
            sample = math.exp(attenuation-switch_attenuation) * (switch_x*math.cos(angle)+switch_y*math.sin(angle))
        samples.append(sample)
    return samples


def reference(frames, decay_raw=DEFAULT_DECAY, changes=None):
    from .retrigger808 import companion_body_reference
    return [main+companion for main,companion in zip(
        _main_reference(frames, decay_raw, changes),
        companion_body_reference(frames, decay_raw, changes))]


def compare():
    """Compare the current production body, Tone and coupling on both CPUs."""
    from .tone808 import compare as compare_tone
    return compare_tone()


if __name__ == "__main__":
    import json
    print(json.dumps(compare()))
