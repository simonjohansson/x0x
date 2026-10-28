"""S02 p2/p11, S05 p12: separate deterministic PULSE branch, noise port zero.

Q8 is PNP: the positive electrical trigger turns it OFF; C5 discharges through
R14 and the loaded C2/filter branch.
Release restores its collector high and excites the C2/C3/C4 Q9 filter. Q9 is
an NPN follower, so the leading negative transient is cut off, not rectified.
VR3 is 500 ohm (B), confirmed in the manufacturer's p2 parts list.

Idle Q8 clamps its collector at HIGH. C2 holds HIGH volts while Q9 base and
emitter, C11 and the remaining pulse-filter nodes are at zero volts. Therefore
cutting off Q9 on the leading negative transient does not erase a signed change
from a positive follower bias. The release pulse raises the follower; C11 then
preserves the subsequent signed high-pass decay/undershoot.

shortcut: nominal switch/.7V base drops, ideal follower, ideal Q3/Q4 switching,
fixed nominal accent and first-order Q6 current VCA; finite beta/loading and
the upstream noise filter's source impedance remain later circuit work.
"""
import math

from . import body909 as body,vca909

RATE=48000
RAW_MAX=32512
DEFAULT_ATTACK=16384
SUPPLY=15.0
HIGH=SUPPLY-.2
VBE=.7
Q6_BASE=.6
C5,R14=6.8e-9,22000.0
C2,R7,R15=3.3e-9,100000.0,100000.0
C3,C4,R16=4.7e-9,100e-12,39000.0
C11,R44,R45,R56,VR3,R55=.47e-6,22000.0,47000.0,330.0,500.0,47.0
C7,R20,R18,R17=.033e-6,6800.0,470000.0,470000.0
C12,R41,R42=.033e-6,22000.0,470000.0
Q3_THRESHOLD=Q6_BASE*(1+R18/R17)
TRIGGER_SAMPLES=96
# d5=VC5-HIGH,d2=VC2-HIGH,v3=Va-VE9,b=VB9,v11=VC11,e7=VC7,e12=VC12.
INITIAL_STATE=(0.0,)*7
CURRENT_TO_AUDIO=body.GAIN*(body.R53+body.R43)/body.LINEAR_VOLTS


def passive_mix(raw):
    """Pulse-port load with the noise input at the left ofR45 held at zero.

    The B rheostat is resistance-linear; orientation follows increasing Attack
    level. The finite source impedance/C13/C15 arrive with the noise branch.
    """
    if type(raw) is not int or not 0<=raw<=RAW_MAX:
        raise ValueError('Attack must be an exact native word in0..32512')
    pot=VR3*(1-raw/RAW_MAX)
    load=1/(1/R56+1/R45+1/(pot+R55))
    resistance=R44+load
    return resistance*C11,load/resistance*R55/(pot+R55)


def follower(base):
    return min(max(base-VBE,0.0),HIGH)


def derivative(state,on,tau11):
    d5,d2,v3,b,v11,e7,e12=state
    emitter=follower(b)
    a=v3+emitter
    x=d5-d2
    gate=e7>Q3_THRESHOLD
    gate_load=(e7-Q6_BASE)/R18 if gate else e7/(R18+R17)
    return (-(d5+HIGH)/(R14*C5)-(x-a)/(R7*C5) if on else 0.0,
            (x-a)/(R7*C2),
            ((x-a)/R7-a/R15-(a-b)/R16)/C3,
            (a-b)/(R16*C4),
            (emitter-v11)/tau11,
            ((max(HIGH-.7-e7,0.0)/R20 if on else 0.0)-gate_load)/C7,
            ((max(HIGH-e12,0.0)/R41 if gate else 0.0)-max(e12-Q6_BASE,0.0)/R42)/C12)


def step(state,on,raw,substeps=128):
    """High-rate independent RK4 of the physical capacitor KCL equations."""
    tau,_=passive_mix(raw)
    values=list(state)
    if not on:values[0]=0.0  # Ideal conducting Q8 restores the quiescent source.
    dt=1/(RATE*substeps)
    for _ in range(substeps):
        a=derivative(values,on,tau)
        b=derivative([v+dt*k/2 for v,k in zip(values,a)],on,tau)
        c=derivative([v+dt*k/2 for v,k in zip(values,b)],on,tau)
        d=derivative([v+dt*k for v,k in zip(values,c)],on,tau)
        values=[v+dt*(i+2*j+2*k+l)/6 for v,i,j,k,l in zip(values,a,b,c,d)]
    return tuple(values)


def current(state,raw):
    """Signed branch current injected into IC11a's inverting summing node."""
    _,transfer=passive_mix(raw)
    port=(follower(state[3])-state[4])*transfer
    return port/R55*max(state[6]-Q6_BASE,0.0)/vca909.VOLT_UNIT


def continue_reference(state,remaining,raw,frames,*,substeps=128,changes=None):
    """Return current samples, state7 and remaining electrical-trigger samples.

    START callers pass INITIAL_STATE/96; native slot history is never inferred.
    States are physical volts with C5/C2 quiescent offsets, not saved controls.
    """
    if (len(state)!=7 or any(not math.isfinite(v) for v in state)
            or type(remaining) is not int or not 0<=remaining<=TRIGGER_SAMPLES
            or type(frames) is not int or frames<0
            or type(substeps) is not int or substeps<=0):
        raise ValueError('invalid pulse state, trigger count or sample count')
    passive_mix(raw)
    result=[]
    for sample in range(frames):
        raw=(changes or {}).get(sample,raw)
        state=step(state,remaining>0,raw,substeps)
        remaining=max(remaining-1,0)
        result.append(current(state,raw))
    return result,state,remaining


def reference(frames,raw=DEFAULT_ATTACK,*,substeps=128,changes=None):
    return continue_reference(INITIAL_STATE,TRIGGER_SAMPLES,raw,frames,
                              substeps=substeps,changes=changes)


def audio(currents):
    """Use the existing body's fixed current unit; IC11a inverts once."""
    return [-CURRENT_TO_AUDIO*value for value in currents]
