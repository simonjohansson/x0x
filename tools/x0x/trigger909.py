"""S02 p11 / S05 p12 Q7/Q11/R51 oscillator reset, ideal-transistor limit.

Q11 and SERIES R51=2.2k bridge C14=.033uF, not Attack's C4=100pF. Q7 also
forces IC13b through R48/D12. Its C1/R12/R13 pulse survives the 2ms trigger;
the opposite edge releases Q7. R51/C14 gives finite reset, never a phase hold.
Transistor/diode/opamp drops are unmeasured; the nominal reset uses ideal Q11.
Forced-high IC13b turns PNP Q10 off; negative IC12b CV makes raw IC13a rise.
Q12 conducts into IC11a's minus summing node, so the rendered body falls.
Complete transistor loading and opamp/switch settling remain unqualified.
"""
import math

from . import tune909

C1, R12, R13 = .068e-6, 100000.0, 47000.0
R51, C14 = 2200.0, .033e-6
# shortcut: nominal switch drops; replace only with circuit/device evidence.
VBE, Q1_LOW = .7, .2
TRIGGER_SAMPLES = tune909.TRIGGER_SAMPLES
INITIAL_STATE = (0.0, 0.0, TRIGGER_SAMPLES)
RESET_X = 1/(tune909.SAMPLE_RATE*R51*C14)
RESET_RADIUS = math.exp(-RESET_X)
RESET_MEAN = -math.expm1(-RESET_X)/RESET_X


def _moment(n):
    # Beta-integral expansion avoids cancellation in the upward moment recurrence.
    return math.fsum((-RESET_X)**k*math.factorial(n)/math.factorial(n+k+1)
                     for k in range(20))


# (mR-M(x))/x = I1 - x*I2/2 + x²*I3/6 - ...; x never exceeds .0318.
RESET_QUOTIENT = tuple((-1)**n*_moment(n+1)/math.factorial(n+1) for n in range(6))


def reset_series_coefficients(raw):
    """Target-ready, regular polynomial form of the exact reset coefficients."""
    c = tune909.coefficients(raw)
    x = 1/(tune909.SAMPLE_RATE*c['tau_on'])
    quotient = RESET_QUOTIENT[-1]
    for coefficient in reversed(RESET_QUOTIENT[:-1]):
        quotient = coefficient+x*quotient
    coupled_mean = RESET_MEAN-x*quotient
    base = tune909.SETTLED_HZ/tune909.SAMPLE_RATE
    boost = base*c['cv_ratio']
    source = tune909.CHARGE_V/tune909.SUPPLY_V/(tune909.SAMPLE_RATE*tune909.R21*tune909.C9)
    return RESET_RADIUS,base*RESET_MEAN+boost*source*quotient,boost*coupled_mean


def reset_coefficients(raw):
    """Exact simultaneous C9 forcing and R51/C14 feedback, in cycle units.

    Existing settled-Hz calibration sets the ramp rate; this does not refit it.
    While Q11 conducts, p' = f(C9)-p/(R51*C14), with the forced rising branch.
    """
    c = tune909.coefficients(raw)
    a, b = 1/c['tau_on'], 1/(R51*C14)
    radius = math.exp(-b/tune909.SAMPLE_RATE)
    integral = (c['radius_on']-radius)/(b-a)
    drive = tune909.SETTLED_HZ*c['cv_ratio']*integral
    constant = tune909.SETTLED_HZ*((1+c['cv_ratio']*c['on_level'])*(1-radius)/b
                                 - c['cv_ratio']*c['on_level']*integral)
    return radius,constant,drive


def q7_base_current(seconds):
    """Available PNP base drive while TRIG stays high, in the VBE-clamp limit.

    Q1's falling collector edge couples through C1. R12 charges the capacitor;
    R13 supplies the opposing emitter-to-base restoration current. This is a
    circuit check, not an audio envelope or a fitted reset duration.
    """
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError("time must be finite and nonnegative")
    return max(0.0, (tune909.SUPPLY_V-VBE-Q1_LOW)/R12
               * math.exp(-seconds/(R12*C1)) - VBE/R13)


def continue_reference(state, tune_raw, frames, starts=(), *, changes=None):
    """Continue phase/C9/count; START forces direction but retains both charges.

    Samples use the same end-of-interval convention as tune909. C9 charging
    continues during the finite reset; the first free interval follows it,
    with no added phase or time fitting. A comparator direction change maps
    phase onto the equal-voltage rising branch, never erases C14 voltage.
    """
    phase, voltage, remaining = state
    if type(frames) is not int or frames < 0:
        raise ValueError("frames must be a nonnegative integer")
    starts = set(starts)
    if any(type(n) is not int or not 0 <= n < frames for n in starts):
        raise ValueError("START must address a rendered sample")
    radius,constant,drive = reset_coefficients(tune_raw)
    phases, voltages = [], []
    for sample in range(frames):
        if sample in (changes or {}):
            tune_raw=changes[sample]
            radius,constant,drive=reset_coefficients(tune_raw)
        if sample in starts:
            phase = math.asin(math.sin(2*math.pi*phase))/(2*math.pi)
            remaining = TRIGGER_SAMPLES
        charging = remaining > 0
        old_voltage = voltage
        increment, charged, remaining = tune909.continue_reference(
            0.0, voltage, remaining, tune_raw, 1)
        voltage = charged[0]
        phase = radius*phase+constant+drive*old_voltage if charging else phase+increment[0]
        phases.append(phase)
        voltages.append(voltage)
    return phases, voltages, (phase, voltage, remaining)


def reference(frames, tune_raw=tune909.DEFAULT_TUNE, starts=(), *, changes=None):
    return continue_reference(INITIAL_STATE, tune_raw, frames, starts,changes=changes)
