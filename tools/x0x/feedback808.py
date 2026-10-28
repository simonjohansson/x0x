"""S01/S03 capacitor-state 808 bridge with the complete C43 shelf and Q43 leakage.

shortcut: ideal op-amps, resistance-linear VR6, independent C39 loading and
hard-knee Q43 leakage and fixed switch; soft knee, accent and loading remain open.
"""
import math

from . import body808, pulse808, retrigger808, leakage808

R164 = R169 = 47000.0
C43 = 33e-6
VR6 = 500000.0


def _scales(capacitor_scale,r170_scale):
    for value in (capacitor_scale,r170_scale):
        if isinstance(value,bool) or not math.isfinite(value) or value<=0:
            raise ValueError("physical component scales must be positive and finite")


def shelf(decay_raw):
    """Return high-frequency gain magnitude and the physical shelf pole (/s)."""
    if type(decay_raw) is not int or not 0<=decay_raw<=body808.RAW_MAX:
        raise ValueError("Decay must be an exact native word in 0..32512")
    resistance = VR6*decay_raw/body808.RAW_MAX
    return R169/R164*resistance/(R169+resistance), 1/((R169+resistance)*C43)


def matrix(decay_raw, attack, *, on=False, capacitor_scale=1., r170_scale=1.):
    """Continuous x'=Ax for x=(q41,q42,h,u,r,1), encoded volts throughout.

    q41=u-Vcomm, q42=Vcomm-Vbt and h'=p*(Vbt-h). The ideal buffer gives
    Vfb=-d*Vbt-(R169/R164-d)*h, with Vbt=u-q41-q42. Substitution closes
    the feedback algebraically; there is no inserted sample of delay.
    The last coordinate is always one; ON forcing is explicit.
    """
    d, p = shelf(decay_raw)
    _scales(capacitor_scale,r170_scale)
    c41,c42=retrigger808.C41*capacitor_scale,retrigger808.C42*capacitor_scale
    a = 1/(retrigger808.R167*c41)
    k = 1/(retrigger808.R170*r170_scale*c42)
    g = (1/retrigger808.R161+1/(retrigger808.R170*r170_scale)+1/(6800. if attack else 53800.))/c42
    low = R169/R164-d
    return [
        [-a,-a,0.,0.,0.,0.],
        [g-a+d*k,-a+d*k,-low*k,-g-d*k,1/(retrigger808.R161*c42),0.],
        [-p,-p,-p,p,0.,0.],
        [0.,0.,0.,-1/pulse808.TAU,0.,pulse808.ON_EQUILIBRIUM/pulse808.TAU if on else 0.],
        [0.,0.,0.,0.,-1/retrigger808.TAU,0.],
        [0.,0.,0.,0.,0.,0.],
    ]


def _multiply(a, b):
    return [[sum(x*y for x,y in zip(row,col)) for col in zip(*b)] for row in a]


def transition(decay_raw, attack, sample_rate=48000, *, on=False, capacitor_scale=1., r170_scale=1.):
    """Exact one-interval state transition via scaled matrix exponential."""
    if type(sample_rate) is not int or sample_rate <= 0:
        raise ValueError("sample rate must be a positive integer")
    a = [[value/sample_rate for value in row] for row in matrix(decay_raw,attack,on=on,capacitor_scale=capacitor_scale,r170_scale=r170_scale)]
    norm = max(sum(map(abs,row)) for row in a)
    scale = max(0,math.ceil(math.log2(norm/.25))) if norm else 0
    a = [[value/2**scale for value in row] for row in a]
    result = [[float(i == j) for j in range(6)] for i in range(6)]
    term = [row[:] for row in result]
    for n in range(1,40):
        term = [[value/n for value in row] for row in _multiply(term,a)]
        result = [[x+y for x,y in zip(row,t)] for row,t in zip(result,term)]
        if max(abs(value) for row in term for value in row) < 1e-18:
            break
    else:
        raise ArithmeticError("feedback matrix exponential did not converge")
    for _ in range(scale):
        result = _multiply(result,result)
    return result


def leak_half(state,dt,capacitor_scale=1.):
    """Exact leakage-only flow: q41 and Vcomm remain fixed, without division."""
    common=state[3]-state[0]
    delta=-leakage808.LEAK_RATE/capacitor_scale*dt*min(common-leakage808.KNEE,0.)
    return [state[0],state[1]+delta,*state[2:]]


def _physical_derivative(raw,attack,on,capacitor_scale,r170_scale):
    """Independent original-node KCL, not the expanded transition matrix."""
    d,p=shelf(raw)
    c41,c42=retrigger808.C41*capacitor_scale,retrigger808.C42*capacitor_scale
    feedback_r=retrigger808.R170*r170_scale
    ground_r=6800. if attack else 53800.
    equilibrium=pulse808.ON_EQUILIBRIUM if on else 0.
    def derivative(state):
        q1,q2,h,u,r=state
        common=u-q1
        output=common-q2
        feedback=-d*output-(R169/R164-d)*h
        first=-(q1+q2)/(retrigger808.R167*c41)
        leak=0. if attack else leakage808.R165/(leakage808.R165+leakage808.R166)*leakage808.SLOPE*min(common-leakage808.KNEE,0.)
        second=(c41*first-(common-r)/retrigger808.R161
                -(common-feedback)/feedback_r-common/ground_r-leak)/c42
        return (first,second,p*(output-h),(equilibrium-u)/pulse808.TAU,-r/retrigger808.TAU)
    return derivative


def reference(frames,decay_raw=body808.DEFAULT_DECAY,changes=None,*,split=False,
              subdivisions=4,capacitor_scale=1.,r170_scale=1.,states=False):
    """Physical nonlinear shelf audio, source edges and after-interval convention.

    The independent reference integrates original capacitor KCL with RK4.
    The CPU-ready candidate uses exact linear shelf/source flow bracketed by
    exact leakage half flows. No calibrated modal pole/damping enters either.
    """
    if type(frames) is not int or frames<0:
        raise ValueError("frame count must be a nonnegative integer")
    if type(subdivisions) is not int or subdivisions<=0:
        raise ValueError("subdivisions must be a positive integer")
    _scales(capacitor_scale,r170_scale)
    shelf(decay_raw)
    changes=changes or {}
    x=[0.,0.,0.,pulse808.TRIGGER_V*pulse808.VOLT_SCALE,
       retrigger808.DIODE_DROP_V*retrigger808.VOLT_SCALE]
    result=[];history=[]
    for sample in range(frames):
        if sample==body808.PULSE_SAMPLES:x[3]=-retrigger808.DIODE_DROP_V*retrigger808.VOLT_SCALE
        if sample==body808.ATTACK_SAMPLES:x[4]-=retrigger808.ENVELOPE_V*retrigger808.VOLT_SCALE
        if sample in (0,body808.PULSE_SAMPLES,body808.ATTACK_SAMPLES) or sample in changes:
            decay_raw=changes.get(sample,decay_raw)
            attack=sample<body808.ATTACK_SAMPLES
            on=sample<body808.PULSE_SAMPLES
            if split:
                step=transition(decay_raw,attack,on=on,capacitor_scale=capacitor_scale,r170_scale=r170_scale)
            else:
                derivative=_physical_derivative(decay_raw,attack,on,capacitor_scale,r170_scale)
        if split:
            if not attack:x=leak_half(x,1/(2*48000),capacitor_scale)
            x=[sum(a*b for a,b in zip(row,[*x,1.])) for row in step[:5]]
            if not attack:x=leak_half(x,1/(2*48000),capacitor_scale)
        else:
            dt=1/(48000*subdivisions)
            for _ in range(subdivisions):
                a=derivative(x)
                b=derivative([v+dt*k/2 for v,k in zip(x,a)])
                c=derivative([v+dt*k/2 for v,k in zip(x,b)])
                d=derivative([v+dt*k for v,k in zip(x,c)])
                x=[v+dt*(a+2*b+2*c+d)/6 for v,a,b,c,d in zip(x,a,b,c,d)]
        result.append(x[3]-x[0]-x[1])
        if states:history.append(tuple(x))
    return (result,history) if states else result


