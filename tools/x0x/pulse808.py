"""S01/S03 main pulse shaper and calibrated bridged-T input oracle.

shortcut: ideal negative D53 clamp and fixed 14 V trigger; transistor/accent,
full frequency-dependent feedback and loaded output remain separate work.
"""
import cmath
import math

from . import body808, retrigger808

R162, R163, C40 = 4700., 100000., 15e-9
DC_GAIN = R162/(R162+R163)
TAU = R162*R163/(R162+R163)*C40
TRIGGER_V = 14.0  # Upper end of S03 section3's published 4..14 V range; not a VST fit.
VOLT_SCALE = retrigger808.VOLT_SCALE
ON_EQUILIBRIUM = TRIGGER_V*VOLT_SCALE*DC_GAIN


def shaped_voltage(sample):
    """Fresh ideal-diode charge-state solution, sampled in encoded volts."""
    if sample < body808.PULSE_SAMPLES:
        return ON_EQUILIBRIUM + (TRIGGER_V*VOLT_SCALE-ON_EQUILIBRIUM)*math.exp(-sample/(48000*TAU))
    return -retrigger808.DIODE_DROP_V*VOLT_SCALE*math.exp(-(sample-body808.PULSE_SAMPLES)/(48000*TAU))


def main_reference(frames, decay_raw=body808.DEFAULT_DECAY, changes=None):
    """Closed-form constant/exponential forcing on each pole/input segment."""
    changes = changes or {}
    state = 0j
    result = []
    a = 1/(retrigger808.R167*retrigger808.C41)
    for n in range(frames):
        if n == body808.ATTACK_SAMPLES:
            alpha,beta = body808.switch_coordinates(decay_raw)
            state = complex(state.real,alpha*state.imag+beta*state.real)
        if n in (0,body808.PULSE_SAMPLES,body808.ATTACK_SAMPLES) or n in changes:
            decay_raw = changes.get(n,decay_raw)
            sigma = -48000*math.log(body808.retention(decay_raw))
            omega = 2*math.pi*(body808.ATTACK_FREQUENCY if n < body808.ATTACK_SAMPLES else body808.FREQUENCY)
            pole = complex(-sigma,-omega)
            gain = (sigma*sigma+omega*omega)/a+2*a-2*sigma
            forcing = gain*complex(1,-sigma/omega)
            equilibrium = ON_EQUILIBRIUM if n < body808.PULSE_SAMPLES else 0.
            amplitude = shaped_voltage(n)-equilibrium
            constant = forcing*equilibrium/pole
            exponential_drive = forcing*amplitude/(pole+1/TAU)
            initial,begin = state,n
        elapsed = (n+1-begin)/48000
        exponential = cmath.exp(pole*elapsed)
        state = exponential*initial + constant*(exponential-1) + exponential_drive*(exponential-math.exp(-elapsed/TAU))
        result.append(state.real+equilibrium+amplitude*math.exp(-elapsed/TAU))
    return result


def step_coefficients(decay_raw, attack):
    """Integrated exponential-source gain and extra constant-source term while ON."""
    sigma = -48000*math.log(body808.retention(decay_raw))
    omega = 2*math.pi*(body808.ATTACK_FREQUENCY if attack else body808.FREQUENCY)
    a = 1/(retrigger808.R167*retrigger808.C41)
    gain = (sigma*sigma+omega*omega)/a+2*a-2*sigma
    pole = complex(-sigma,-omega)
    forcing = gain*complex(1,-sigma/omega)
    q = cmath.exp(pole/48000)
    exponential = forcing*(q-math.exp(-1/(48000*TAU)))/(pole+1/TAU)
    bias = ON_EQUILIBRIUM*(forcing*(q-1)/pole-exponential)
    return exponential.real,exponential.imag,bias.real,bias.imag
