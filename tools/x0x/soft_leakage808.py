"""Isolated S03 equation8 Q43 soft knee on the accepted calibrated 808 core.

The published fit is used as written, not refitted or zero-current shifted.
This is a model experiment, not production DSP or complete circuit alignment.
The existing pole/control/source/START conventions are retained; a small-signal
pole shift caused by the published nonlinearity is a prediction, not retuning.
"""
import cmath
import math

from . import body808, pulse808, retrigger808

ALPHA = 14.3150
KNEE_V = -.5560
SLOPE = 1.4765e-5
RATIO = 47000.0 / 53800.0
C42 = 15e-9
SCALE = retrigger808.VOLT_SCALE
RATE = body808.SAMPLE_RATE


def collector_current(common_v):
    """Published signed collector current in A, with voltage in physical volts."""
    if not math.isfinite(common_v):
        raise ValueError('common-node voltage must be finite')
    delta = common_v - KNEE_V
    if delta < 0:
        return SLOPE*delta - SLOPE/ALPHA*math.log1p(math.exp(ALPHA*delta))
    return -SLOPE/ALPHA*math.log1p(math.exp(-ALPHA*delta))


def collector_slope(common_v):
    """Analytic dI/dV in siemens; finite even far outside the operating range."""
    if not math.isfinite(common_v):
        raise ValueError('common-node voltage must be finite')
    x = ALPHA*(common_v-KNEE_V)
    if x >= 0:
        e = math.exp(-x)
        return SLOPE*e/(1+e)
    return SLOPE/(1+math.exp(x))


def _parameters(raw):
    sigma = -RATE*math.log(body808.retention(raw))
    omega = 2*math.pi*body808.FREQUENCY
    a = 1/(retrigger808.R167*retrigger808.C41)
    square = sigma*sigma+omega*omega
    return sigma, omega, a, a*sigma/square, a*omega/square


def quiet_state(raw=body808.DEFAULT_DECAY):
    """Zero-output rest with physical Q43 bias; zero stored state is not rest."""
    sigma,omega,a,cw,cy = _parameters(raw)
    transresistance = a/(sigma*sigma+omega*omega)*RATIO/C42
    lo,hi = 0.,1.
    for _ in range(80):
        voltage = (lo+hi)/2
        if voltage+transresistance*collector_current(voltage) > 0:
            hi = voltage
        else:
            lo = voltage
    voltage = (lo+hi)/2
    leak = RATIO/C42*SCALE*collector_current(voltage)
    return complex(0.,-leak/omega)


def quiet_pole(raw=body808.DEFAULT_DECAY):
    """Small-signal pole about biased rest, without subtracting current/slope."""
    sigma,omega,a,cw,cy = _parameters(raw)
    state = quiet_state(raw)
    volts = (cw*state.real+cy*state.imag)/SCALE
    conductance_rate = RATIO/C42*collector_slope(volts)
    return complex(-sigma,math.sqrt(omega*omega+a*conductance_rate))


def _stepper(raw, subdivisions):
    sigma,omega,a,cw,cy = _parameters(raw)
    n = sigma/omega
    pole = complex(-sigma,-omega)
    main_gain = ((sigma*sigma+omega*omega)/a+2*a-2*sigma)*complex(1,-n)
    companion_gain = complex(-1/(retrigger808.R161*C42),n/(retrigger808.R161*C42))
    dt = 1/(RATE*subdivisions)
    mu = math.exp(-dt/(2*pulse808.TAU))
    mr = math.exp(-dt/(2*retrigger808.TAU))
    main_retention = math.exp(-1/(RATE*pulse808.TAU))
    companion_retention = math.exp(-1/(RATE*retrigger808.TAU))
    def derivative(z,u,r):
        current = collector_current((u+cw*z.real+cy*z.imag)/SCALE)
        leak = RATIO/C42*SCALE*current
        return pole*z+main_gain*u+companion_gain*r+complex(leak,-n*leak)
    def advance(state,main,companion):
        u,r = main,companion
        for _ in range(subdivisions):
            uh,rh = u*mu,r*mr
            ue,re = uh*mu,rh*mr
            k1 = derivative(state,u,r)
            k2 = derivative(state+dt*k1/2,uh,rh)
            k3 = derivative(state+dt*k2/2,uh,rh)
            k4 = derivative(state+dt*k3,ue,re)
            state += dt*(k1+2*k2+2*k3+k4)/6
            u,r = ue,re
        return state,main*main_retention,companion*companion_retention
    return advance


def _validate(frames,raw,subdivisions):
    if type(frames) is not int or frames < 0:
        raise ValueError('frame count must be a nonnegative integer')
    if type(subdivisions) is not int or subdivisions <= 0:
        raise ValueError('subdivision count must be a positive integer')
    body808.retention(raw)


def continue_reference(state, main, companion, raw, frames, *, subdivisions=4):
    """Continue a post-attack snapshot; output and node states keep encoded units."""
    _validate(frames,raw,subdivisions)
    if not all(math.isfinite(v) for v in (state.real,state.imag,main,companion)):
        raise ValueError('continuation state must be finite')
    advance = _stepper(raw,subdivisions)
    result = []
    for _ in range(frames):
        state,main,companion = advance(state,main,companion)
        result.append(state.real+main)
    return result,(state,main,companion)


def reference(frames, raw=body808.DEFAULT_DECAY, changes=None, *, subdivisions=4):
    """Fresh accepted excitation/switch convention, then continuous soft-knee RK4."""
    _validate(frames,raw,subdivisions)
    changes = changes or {}
    for sample,value in changes.items():
        if type(sample) is not int or sample < 0:
            raise ValueError('change position must be a nonnegative integer')
        body808.retention(value)
    state = 0j
    main = pulse808.TRIGGER_V*SCALE
    companion = retrigger808.DIODE_DROP_V*SCALE
    main_retention = math.exp(-1/(RATE*pulse808.TAU))
    companion_retention = math.exp(-1/(RATE*retrigger808.TAU))
    result = []
    for sample in range(frames):
        if sample == body808.ATTACK_SAMPLES:
            alpha,beta = body808.switch_coordinates(raw)
            state = complex(state.real,alpha*state.imag+beta*state.real)
            companion -= retrigger808.ENVELOPE_V*SCALE
        if sample == body808.PULSE_SAMPLES:
            main = -retrigger808.DIODE_DROP_V*SCALE
        if sample in (0,body808.PULSE_SAMPLES,body808.ATTACK_SAMPLES) or sample in changes:
            raw = changes.get(sample,raw)
            if sample < body808.ATTACK_SAMPLES:
                sigma = -RATE*math.log(body808.retention(raw))
                omega = 2*math.pi*body808.ATTACK_FREQUENCY
                q = cmath.exp(complex(-sigma,-omega)/RATE)
                gx,gy,bx,by = pulse808.step_coefficients(raw,True)
                main_gain,bias = complex(gx,gy),complex(bx,by)
                companion_gain = complex(*retrigger808.companion_step(raw,True))
            else:
                advance = _stepper(raw,subdivisions)
        if sample < body808.ATTACK_SAMPLES:
            state = q*state+main_gain*main+companion_gain*companion+(bias if sample < body808.PULSE_SAMPLES else 0j)
            main = main*main_retention+(pulse808.ON_EQUILIBRIUM*(1-main_retention) if sample < body808.PULSE_SAMPLES else 0.)
            companion *= companion_retention
        else:
            state,main,companion = advance(state,main,companion)
        result.append(state.real+main)
    return result
