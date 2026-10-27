"""S02/S05 ENV1 finite C8 charge, Q12 base loading and small-signal current VCA.

shortcut: ideal .7V switching diodes and a fixed .6V base clamp; transistor
compression, temperature, signal-dependent loading and physical A taper remain open.
"""
import math

from . import body909

RATE=body909.SAMPLE_RATE
C8=.33e-6
R35,R36,R22,R54=1000.,47000.,10000.,470000.
R58,VR5=47000.,1000000.
SOURCE_V=14.8  # Nominal +15V less the provisional .2V switching drop, before D9.
DIODE_V,BASE_V=.7,.6
VOLT_UNIT=16.0  # Fixed private current/audio unit, not normalization by the peak.
STATE_SCALE=body909.GAIN/VOLT_UNIT  # Reuse the current amplitude word as C8/64.
TRIGGER_SAMPLES=96
DIVIDER_V=SOURCE_V*R22/(R36+R22)
DRIVE_LIMIT=((SOURCE_V-DIODE_V)/R35+SOURCE_V/R36)/(1/R35+1/R36+1/R22)


def resistance(raw):
    if type(raw) is not int or not 0<=raw<=body909.RAW_MAX:
        raise ValueError('Decay must be an exact native word in 0..32512')
    return R58+VR5*raw/body909.RAW_MAX


def drive_current(voltage,on):
    """D9 charging current after ideal D8/R36/R22 switching, in amperes."""
    if not on:return 0.
    current=(SOURCE_V-DIODE_V-voltage)/R35
    if voltage>DIVIDER_V:
        current+=(SOURCE_V-voltage)/R36-voltage/R22
    return max(current,0.)


def base_current(voltage):
    return max(voltage-BASE_V,0.)/R54


def derivative(voltage,raw,on):
    return (drive_current(voltage,on)-voltage/resistance(raw)-base_current(voltage))/C8


def linear_region(voltage,raw,on):
    """Return positive loss (/s) and fixed equilibrium volts for this branch."""
    conductance=1/resistance(raw)
    forcing=0.
    if voltage>BASE_V:
        conductance+=1/R54
        forcing+=BASE_V/R54
    if on and voltage<DRIVE_LIMIT:
        conductance+=1/R35
        forcing+=(SOURCE_V-DIODE_V)/R35
        if voltage>DIVIDER_V:
            conductance+=1/R36+1/R22
            forcing+=SOURCE_V/R36
    return conductance/C8,forcing/conductance


def step(voltage,raw,on,dt=1/RATE):
    """Exact piecewise-affine capacitor step, splitting physical diode/base events."""
    if isinstance(voltage,bool) or not math.isfinite(voltage) or not 0<=voltage<=SOURCE_V:
        raise ValueError('C8 voltage must be finite in 0..source voltage')
    if isinstance(dt,bool) or not math.isfinite(dt) or dt<=0:
        raise ValueError('interval must be finite and positive')
    resistance(raw)
    remaining=dt
    edges=(BASE_V,DIVIDER_V,DRIVE_LIMIT) if on else (BASE_V,)
    for _ in range(8):
        direction=derivative(voltage,raw,on)
        probe=math.nextafter(voltage,math.inf if direction>=0 else -math.inf)
        loss,equilibrium=linear_region(probe,raw,on)
        result=equilibrium+(voltage-equilibrium)*math.exp(-loss*remaining)
        crossed=[v for v in edges if voltage<v<result or result<v<voltage]
        if not crossed:return result
        boundary=min(crossed) if result>voltage else max(crossed)
        elapsed=-math.log((boundary-equilibrium)/(voltage-equilibrium))/loss
        remaining-=elapsed
        voltage=boundary
    raise ArithmeticError('C8 event integration did not converge')


def candidate_step(voltage,raw,on):
    """Four affine TPT quarter steps leave numeric room for the oscillator/shaper."""
    for _ in range(4):
        loss,equilibrium=linear_region(voltage,raw,on)
        half_loss=loss/(8*RATE)
        delta=-2*half_loss/(1+half_loss)
        voltage+=delta*(voltage-equilibrium)
    return voltage


def port_region(voltage,on):
    if not on or voltage>=DRIVE_LIMIT:return int(voltage>BASE_V)
    if voltage<=BASE_V:return 2
    return 3 if voltage<=DIVIDER_V else 4


def port_coefficients(raw):
    """Five (radius-1,bias) pairs for four quarter updates of encoded C8/64.

    A fourth-order reciprocal polynomial avoids per-sample division. The only
    raw-dependent reciprocal is the existing unloaded R58/VR5 conductance.
    """
    alpha_decay=1/(8*RATE*C8*resistance(raw))
    result=[]
    for base,on,d8 in ((False,False,False),(True,False,False),
                       (False,True,False),(True,True,False),(True,True,True)):
        alpha=alpha_decay
        forcing=0.
        if base:
            alpha+=1/(8*RATE*C8*R54)
            forcing+=BASE_V/R54
        if on:
            alpha+=1/(8*RATE*C8*R35)
            forcing+=(SOURCE_V-DIODE_V)/R35
        if d8:
            alpha+=(1/R36+1/R22)/(8*RATE*C8)
            forcing+=SOURCE_V/R36
        delta=-2*(alpha-alpha**2+alpha**3-alpha**4)
        beta=forcing/C8/(4*RATE)*STATE_SCALE
        result.append((delta,beta*(1+delta/2)))
    return result


def gain(voltage):
    """First-order base-current VCA in the retained provisional audition unit.

    R54*Ib/16V is current-controlled gain; it does not model finite-beta
    compression or the signal-dependent transistor/diode-port load.
    """
    return R54*base_current(voltage)/VOLT_UNIT


def envelope(frames,raw=body909.DEFAULT_DECAY,changes=None,*,candidate=False):
    if type(frames) is not int or frames<0:
        raise ValueError('frame count must be a nonnegative integer')
    resistance(raw)
    voltage=0.
    result=[]
    for sample in range(frames):
        raw=(changes or {}).get(sample,raw)
        voltage=(candidate_step if candidate else step)(voltage,raw,sample<TRIGGER_SAMPLES)
        result.append(voltage)
    return result
