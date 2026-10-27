"""Host-only C39/R161/D52 reference; not connected to production DSP.

S01 p9 / S03 section8.1 Figure8: C39 feeds the node, R161 returns to
Vcomm approximated as ground, and D52 clamps the positive edge.
shortcut: fixed 0.71 V ideal diode; finite conduction/source impedance,
Vcomm loading and transistor leakage require the coupled circuit model.
"""
import math

from . import body808

R161 = 1e6
C39 = 33e-9
TAU = R161 * C39
DIODE_DROP_V = .71
ENVELOPE_V = 15.0
SAMPLE_RATE = body808.SAMPLE_RATE


def filter_reference(envelope, sample_rate=SAMPLE_RATE):
    """Exact ZOH RC intervals with capacitor charging at ideal-diode events.

    Values are volts, sampled immediately after each input edge. The capacitor
    voltage is the state: clipping updates its charge, not just the output.
    """
    if type(sample_rate) is not int or sample_rate <= 0:
        raise ValueError("sample rate must be a positive integer")
    retention = math.exp(-1 / (sample_rate * TAU))
    capacitor = 0.0
    result = []
    for drive in envelope:
        if not math.isfinite(drive):
            raise ValueError("envelope voltage must be finite")
        node = drive - capacitor
        if not math.isfinite(node):
            raise ValueError("envelope step exceeds the reference range")
        node = min(node, DIODE_DROP_V)
        result.append(node)
        capacitor = drive - node * retention
    return result


def reference(frames):
    if type(frames) is not int or frames < 0:
        raise ValueError("frame count must be a nonnegative integer")
    return filter_reference([ENVELOPE_V if n < body808.ATTACK_SAMPLES else 0.0
                             for n in range(frames)])
