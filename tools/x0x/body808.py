"""Independent first-body oracle: a fixed 55 Hz, 250 ms damped sine.

This is an uncalibrated 808 starting point, before excitation, pitch sigh,
stock Decay/Tone networks and residual-state retrigger behavior are modeled.
"""
import math

SAMPLE_RATE = 48000
FREQUENCY = 55.0
TAU = 0.25
GAIN = 0.25


def reference(frames):
    """Samples after a START at time zero; no recurrence or target quantization."""
    return [GAIN * math.exp(-(n + 1) / (SAMPLE_RATE * TAU))
            * math.sin(2 * math.pi * FREQUENCY * (n + 1) / SAMPLE_RATE)
            for n in range(frames)]
