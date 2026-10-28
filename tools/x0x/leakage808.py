"""Reference-calibrated effective Q43 feedback on the 808 modal core.

shortcut: retain S03's hard-knee form with effective calibrated coefficients;
complete feedback, finite transistor behavior and residual retrigger remain open.
"""
import cmath
import math

from . import body808, pulse808, retrigger808

R165, R166 = 47000.,6800.
RATE = body808.SAMPLE_RATE
# Effective FS/rate calibration; S03's prior was -.556 V / 1.4765e-5 A/V.
KNEE = -.018011980654046803
LEAK_RATE = 2933.2119129807006
# Equivalent encoded KCL parameters, not measured reference transistor values.
KNEE_V = KNEE/retrigger808.VOLT_SCALE
SLOPE = LEAK_RATE*retrigger808.C42*(R165+R166)/R165


def coefficients(decay_raw):
    """(common-node w/y factors, half-interval gain, sigma/omega), all Q31-safe."""
    sigma = -RATE*math.log(body808.retention(decay_raw))
    omega = 2*math.pi*body808.FREQUENCY
    a = 1/(retrigger808.R167*retrigger808.C41)
    denominator = sigma*sigma+omega*omega
    return a*sigma/denominator,a*omega/denominator,LEAK_RATE/(2*RATE),sigma/omega


def half_kick(state, main, decay_raw):
    """Exact leakage-only flow: q41 and therefore Vcomm stay constant."""
    cw,cy,gain,n = coefficients(decay_raw)
    common = main+cw*state.real+cy*state.imag
    delta = gain*min(common-KNEE,0.)
    return state+complex(delta,-n*delta)


def _settled_stepper(decay_raw, subdivisions):
    cw,cy,_,n = coefficients(decay_raw)
    omega = 2*math.pi*body808.FREQUENCY
    sigma = n*omega
    a = 1/(retrigger808.R167*retrigger808.C41)
    pole = complex(-sigma,-omega)
    forcing = ((sigma*sigma+omega*omega)/a+2*a-2*sigma)*complex(1,-n)
    companion_forcing = complex(-1/(retrigger808.R161*retrigger808.C42),
                                n/(retrigger808.R161*retrigger808.C42))
    dt = 1/(RATE*subdivisions)
    mu = math.exp(-dt/(2*pulse808.TAU))
    mr = math.exp(-dt/(2*retrigger808.TAU))
    main_retention = math.exp(-1/(RATE*pulse808.TAU))
    companion_retention = math.exp(-1/(RATE*retrigger808.TAU))
    def derivative(z,u,r):
        leak = LEAK_RATE*min(u+cw*z.real+cy*z.imag-KNEE,0.)
        return pole*z+forcing*u+companion_forcing*r+complex(leak,-n*leak)
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


def continue_reference(state, main, companion, decay_raw, frames):
    """Continue a post-attack native snapshot with constant controls, without START.

    Return (body_samples, (final_complex_w_y, final_C40, final_C39)); sources and
    modal state use the same encoded volts as the render callback.
    """
    if type(frames) is not int or frames < 0:
        raise ValueError("frame count must be a nonnegative integer")
    if not all(math.isfinite(v) for v in (state.real,state.imag,main,companion)):
        raise ValueError("continuation state must be finite")
    advance = _settled_stepper(decay_raw,8)
    samples = []
    for _ in range(frames):
        state,main,companion = advance(state,main,companion)
        samples.append(state.real+main)
    return samples,(state,main,companion)


def reference(frames, decay_raw=body808.DEFAULT_DECAY, changes=None, *, split=False, subdivisions=8):
    """Independent fine-step RK4 ODE, or CPU candidate Strang split for comparison.

    Source nodes are advanced analytically. Before Q43 releases at 6 ms, the
    existing linear solution is exact and leakage is disabled. Both paths use
    after-interval output and preserve the current source/switch conventions.
    """
    if type(frames) is not int or frames < 0:
        raise ValueError("frame count must be a nonnegative integer")
    if type(subdivisions) is not int or subdivisions <= 0:
        raise ValueError("subdivision count must be a positive integer")
    changes = changes or {}
    state = 0j
    main = pulse808.TRIGGER_V*pulse808.VOLT_SCALE
    companion = retrigger808.DIODE_DROP_V*retrigger808.VOLT_SCALE
    main_retention = math.exp(-1/(RATE*pulse808.TAU))
    companion_retention = math.exp(-1/(RATE*retrigger808.TAU))
    result = []
    for sample in range(frames):
        if sample == body808.ATTACK_SAMPLES:
            alpha,beta = body808.switch_coordinates(decay_raw)
            state = complex(state.real,alpha*state.imag+beta*state.real)
            companion -= retrigger808.ENVELOPE_V*retrigger808.VOLT_SCALE
        if sample == body808.PULSE_SAMPLES:
            main = -retrigger808.DIODE_DROP_V*retrigger808.VOLT_SCALE
        if sample in (0,body808.PULSE_SAMPLES,body808.ATTACK_SAMPLES) or sample in changes:
            decay_raw = changes.get(sample,decay_raw)
            sigma = -RATE*math.log(body808.retention(decay_raw))
            omega = 2*math.pi*(body808.ATTACK_FREQUENCY if sample < body808.ATTACK_SAMPLES else body808.FREQUENCY)
            pole = complex(-sigma,-omega)
            q = cmath.exp(pole/RATE)
            gx,gy,bx,by = pulse808.step_coefficients(decay_raw,sample < body808.ATTACK_SAMPLES)
            main_gain,bias = complex(gx,gy),complex(bx,by)
            companion_gain = complex(*retrigger808.companion_step(decay_raw,sample < body808.ATTACK_SAMPLES))
            cw,cy,half,n = coefficients(decay_raw)
            if sample >= body808.ATTACK_SAMPLES and not split:
                advance = _settled_stepper(decay_raw,subdivisions)
        new_main = main*main_retention+(pulse808.ON_EQUILIBRIUM*(1-main_retention) if sample < body808.PULSE_SAMPLES else 0.)
        new_companion = companion*companion_retention
        if sample < body808.ATTACK_SAMPLES or split:
            if sample >= body808.ATTACK_SAMPLES:
                delta = half*min(main+cw*state.real+cy*state.imag-KNEE,0.)
                state += complex(delta,-n*delta)
            state = q*state+main_gain*main+companion_gain*companion+(bias if sample < body808.PULSE_SAMPLES else 0j)
            if sample >= body808.ATTACK_SAMPLES:
                delta = half*min(new_main+cw*state.real+cy*state.imag-KNEE,0.)
                state += complex(delta,-n*delta)
        else:
            state,new_main,new_companion = advance(state,main,companion)
        main,companion = new_main,new_companion
        result.append(state.real+main)
    return result
