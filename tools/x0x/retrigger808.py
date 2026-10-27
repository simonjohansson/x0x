"""Independent C39/R161/D52 and bridge-input reference models.

S01 p9 / S03 section8.1 Figure8: C39 feeds the node, R161 returns to
Vcomm approximated as ground, and D52 clamps the positive edge.
shortcut: fixed 0.71 V ideal diode; finite conduction/source impedance,
Vcomm loading and transistor leakage require the coupled circuit model.
"""
import math
import cmath

from . import body808

R161 = 1e6
C39 = 33e-9
TAU = R161 * C39
DIODE_DROP_V = .71
ENVELOPE_V = 15.0
SAMPLE_RATE = body808.SAMPLE_RATE
R167, R170, C41, C42 = 1e6, 470e3, 15e-9, 15e-9
# Encoding/headroom convention, not a measured hardware or VST voltage scale.
VOLT_SCALE = body808.GAIN / ENVELOPE_V


def companion_body_reference(frames, decay_raw=body808.DEFAULT_DECAY, changes=None):
    """Continuous RC forcing integrated analytically over constant-pole segments.

    shortcut: source-separated C39 and calibrated constant damping; loaded
    feedback, main pulse shaping and intrinsic accent remain unmodeled.
    """
    changes = changes or {}
    state = 0j
    result = []
    fall = (DIODE_DROP_V*math.exp(-body808.ATTACK_SAMPLES/(SAMPLE_RATE*TAU))
            - ENVELOPE_V)*VOLT_SCALE
    for n in range(frames):
        if n == body808.ATTACK_SAMPLES:
            alpha, beta = body808.switch_coordinates(decay_raw)
            state = complex(state.real, alpha*state.imag+beta*state.real)
        if n == 0 or n == body808.ATTACK_SAMPLES or n in changes:
            decay_raw = changes.get(n, decay_raw)
            sigma = -SAMPLE_RATE*math.log(body808.retention(decay_raw))
            omega = 2*math.pi*(body808.ATTACK_FREQUENCY if n < body808.ATTACK_SAMPLES else body808.FREQUENCY)
            pole = complex(-sigma, -omega)
            source = (DIODE_DROP_V*VOLT_SCALE*math.exp(-n/(SAMPLE_RATE*TAU))
                      if n < body808.ATTACK_SAMPLES else
                      fall*math.exp(-(n-body808.ATTACK_SAMPLES)/(SAMPLE_RATE*TAU)))
            forcing = complex(-1/(R161*C42), sigma/(omega*R161*C42))
            driven = forcing*source/(pole+1/TAU)
            initial, begin = state, n
        elapsed = (n+1-begin)/SAMPLE_RATE
        exponential = cmath.exp(pole*elapsed)
        state = exponential*initial + driven*(exponential-math.exp(-elapsed/TAU))
        result.append(state.real)
    return result


def companion_step(decay_raw, attack):
    """Exact one-sample coefficients for a continuously decaying C39 input."""
    sigma = -SAMPLE_RATE*math.log(body808.retention(decay_raw))
    omega = 2*math.pi*(body808.ATTACK_FREQUENCY if attack else body808.FREQUENCY)
    pole = complex(-sigma, -omega)
    forcing = complex(-1/(R161*C42), sigma/(omega*R161*C42))
    step = forcing*(cmath.exp(pole/SAMPLE_RATE)-math.exp(-1/(SAMPLE_RATE*TAU)))/(pole+1/TAU)
    return step.real, step.imag


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
