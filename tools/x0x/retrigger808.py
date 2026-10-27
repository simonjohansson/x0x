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
R167, R170, C41, C42 = 1e6, 470e3, 15e-9, 15e-9


def bridge_reference(main, companion, sample_rate=SAMPLE_RATE):
    """Isolated S03 bridge in volts, with feedback source held at ground.

    State is the voltage across C41/C42, retained at the Q43 switch. Inputs
    are held over each sample; return output just after the input edge.
    shortcut: ideal op-amp and independent sources; loaded C39, the feedback
    shelf and rail/nonlinear paths remain separate circuit-alignment work.
    """
    if type(sample_rate) is not int or sample_rate <= 0:
        raise ValueError("sample rate must be a positive integer")
    if len(main) != len(companion):
        raise ValueError("bridge inputs must have equal lengths")
    a = 1 / (R167*C41)
    transitions = []
    for rg in (53800.0, 6800.0):
        g = 1/R161 + 1/R170 + 1/rg
        omega = math.sqrt(a*g/C42 - a*a)
        decay = math.exp(-a/sample_rate)
        sine = decay*math.sin(omega/sample_rate)/omega
        transitions.append((1/(R161*g), decay*math.cos(omega/sample_rate),
                            -a*sine, (g/C42-a)*sine))
    c41 = c42 = 0.0
    result = []
    for n, (pulse, retrigger) in enumerate(zip(main, companion)):
        if not math.isfinite(pulse) or not math.isfinite(retrigger):
            raise ValueError("bridge input voltages must be finite")
        attack = n*SAMPLE_RATE < body808.ATTACK_SAMPLES*sample_rate
        scale, diagonal, upper, lower = transitions[attack]
        equilibrium = pulse - scale*retrigger
        d41, d42 = c41-equilibrium, c42+equilibrium
        output = pulse-c41-c42
        c41 = equilibrium + diagonal*d41 + upper*d42
        c42 = -equilibrium + lower*d41 + diagonal*d42
        if not all(math.isfinite(v) for v in (output, c41, c42)):
            raise ValueError("bridge state exceeds the reference range")
        result.append(output)
    return result


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
