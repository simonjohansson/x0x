"""Finite opamp swing in a capacitor-KCL embedding of the CURRENT808 calibration.

The band-equivalent conductances reproduce the existing quiet poles exactly;
they are not newly identified physical parts or a rescue of the C43 candidate.
Source-supported14V typical/12V guaranteed swings are fixed hypotheses (S23).
shortcut: static rails, no slew/common-mode reversal or finite output impedance.
"""
import math
from . import body808,leakage808,pulse808,retrigger808

RATE=48000
C41,C42=retrigger808.C41,retrigger808.C42
R167,R170,R161=retrigger808.R167,retrigger808.R170,retrigger808.R161
SCALE=retrigger808.VOLT_SCALE
TYPICAL_V,GUARANTEED_V=14.,12.


def coefficients(raw,attack):
    sigma=-RATE*math.log(body808.retention(raw))
    omega=2*math.pi*(body808.ATTACK_FREQUENCY if attack else body808.FREQUENCY)
    a=1/(R167*C41)
    g=(sigma*sigma+omega*omega)/a
    k=1/(R170*C42)
    feedback=2*(a-sigma)/k
    ground=C42*g-1/R161-1/R170
    assert ground>0 and 0<feedback<1
    return a,g,k,feedback,ground


def _limit(voltage,rail):
    return voltage if rail is None else min(max(voltage,-rail),rail)


def nodes(q1,q2,u,feedback,main_rail,feedback_rail):
    requested=u-q1-q2
    output=_limit(requested,main_rail)
    requested_fb=-feedback*output
    actual_fb=_limit(requested_fb,feedback_rail)
    common=output+q2
    minus=output+q1+q2
    # Inverting amplifier's summing node for its calibrated band-equivalent Rf.
    minus_fb=(feedback*output+actual_fb)/(1+feedback)
    return requested,output,common,minus,requested_fb,actual_fb,minus_fb


def _mode(q1,q2,u,feedback,main_rail,feedback_rail,attack):
    request,out,common,_,fb_request,fb,_=nodes(q1,q2,u,feedback,main_rail,feedback_rail)
    main=0 if request==out else (1 if request>out else -1)
    buffer=0 if fb_request==fb else (1 if fb_request>fb else -1)
    return main,buffer,not attack and common<leakage808.KNEE


def _affine(mode,u,r,coef,main_rail,feedback_rail):
    a,g,k,d,_=coef
    main,buffer,active=mode
    leak=leakage808.LEAK_RATE if active else 0.
    if main:
        output=main*main_rail
        fb=buffer*feedback_rail if buffer else -d*output
        return -a,-a,-a,-a-g-leak,(-g-leak)*output+k*fb+r/(R161*C42)+leak*leakage808.KNEE
    if buffer:
        return -a,-a,-a+g+leak,-a,(-g-leak)*u+k*buffer*feedback_rail+r/(R161*C42)+leak*leakage808.KNEE
    return -a,-a,-a+g+k*d+leak,-a+k*d,(-g-k*d-leak)*u+r/(R161*C42)+leak*leakage808.KNEE


def midpoint(q1,q2,u,r,dt,coef,main_rail,feedback_rail,attack):
    """Implicit midpoint policy solve; changed opamp voltage feeds capacitor KCL."""
    mode=_mode(q1,q2,u,coef[3],main_rail,feedback_rail,attack)
    half=dt/2
    for _ in range(8):
        a,b,c,d,bias=_affine(mode,u,r,coef,main_rail,feedback_rail)
        aa,bb,cc,dd=1-half*a,-half*b,-half*c,1-half*d
        rhs1,rhs2=q1,q2+half*bias
        determinant=aa*dd-bb*cc
        x=(dd*rhs1-bb*rhs2)/determinant
        y=(aa*rhs2-cc*rhs1)/determinant
        after=_mode(x,y,u,coef[3],main_rail,feedback_rail,attack)
        if after==mode:return 2*x-q1,2*y-q2
        # At a rounded boundary either affine policy is valid to machine precision.
        aa,bb,cc,dd,bias=_affine(after,u,r,coef,main_rail,feedback_rail)
        residual=max(abs(x-q1-half*(aa*x+bb*y)),abs(y-q2-half*(cc*x+dd*y+bias)))
        if residual<2e-15:return 2*x-q1,2*y-q2
        mode=after
    raise ArithmeticError('opamp midpoint policy failed to converge')


def _derivative(coef,attack,on,main_rail,feedback_rail):
    """Independent capacitor-node branch currents, not expanded affine policies."""
    _,_,_,feedback,ground=coef
    equilibrium=pulse808.ON_EQUILIBRIUM if on else 0.
    def derivative(state):
        q1,q2,u,r=state
        requested=u-q1-q2
        output=_limit(requested,main_rail)
        common=output+q2
        fb=_limit(-feedback*output,feedback_rail)
        first=-(q1+q2)/(R167*C41)
        ic=0. if attack else leakage808.R165/(leakage808.R165+leakage808.R166)*leakage808.SLOPE*min(common-leakage808.KNEE,0.)
        second=(C41*first-(common-r)/R161-(common-fb)/R170-ground*common-ic)/C42
        return first,second,(equilibrium-u)/pulse808.TAU,-r/retrigger808.TAU
    return derivative


def reference(frames,raw=body808.DEFAULT_DECAY,changes=None,*,main_limit_v=TYPICAL_V,
              feedback_limit_v=TYPICAL_V,subdivisions=32,midpoint_candidate=False,states=False):
    """Independent RK4 KCL, or an explicitly selected midpoint candidate.

    The fixed 12 V hypothesis crosses a rail in the first few samples. Eight
    and sixteen RK4 substeps failed the existing 1e-7 refinement guard there;
    32 is checked against 64 without changing that guard. Candidate step counts
    are supplied explicitly by its tests, independently of this oracle default.
    """
    if type(frames) is not int or frames<0:raise ValueError('frames must be nonnegative integer')
    if type(subdivisions) is not int or subdivisions<=0:raise ValueError('subdivisions must be positive integer')
    for rail in (main_limit_v,feedback_limit_v):
        if rail is not None and (isinstance(rail,bool) or not math.isfinite(rail) or rail<=0):
            raise ValueError('rail must be positive finite volts or None')
    main_rail=None if main_limit_v is None else main_limit_v*SCALE
    feedback_rail=None if feedback_limit_v is None else feedback_limit_v*SCALE
    changes=changes or {};x=[0.,0.,pulse808.TRIGGER_V*SCALE,retrigger808.DIODE_DROP_V*SCALE]
    result=[];history=[]
    body808.retention(raw)
    for sample in range(frames):
        if sample==body808.PULSE_SAMPLES:x[2]=-retrigger808.DIODE_DROP_V*SCALE
        if sample==body808.ATTACK_SAMPLES:x[3]-=retrigger808.ENVELOPE_V*SCALE
        if sample in (0,body808.PULSE_SAMPLES,body808.ATTACK_SAMPLES) or sample in changes:
            raw=changes.get(sample,raw);attack=sample<body808.ATTACK_SAMPLES;on=sample<body808.PULSE_SAMPLES
            coef=coefficients(raw,attack)
            derivative=_derivative(coef,attack,on,main_rail,feedback_rail)
        dt=1/(RATE*subdivisions)
        if midpoint_candidate:
            ue=pulse808.ON_EQUILIBRIUM if on else 0.
            ru=math.exp(-dt/pulse808.TAU);rr=math.exp(-dt/retrigger808.TAU)
            mu=-math.expm1(-dt/pulse808.TAU)/(dt/pulse808.TAU)
            mr=-math.expm1(-dt/retrigger808.TAU)/(dt/retrigger808.TAU)
            for _ in range(subdivisions):
                q1,q2,u,r=x
                q1,q2=midpoint(q1,q2,ue+(u-ue)*mu,r*mr,dt,coef,main_rail,feedback_rail,attack)
                x=[q1,q2,ue+(u-ue)*ru,r*rr]
        else:
            for _ in range(subdivisions):
                a=derivative(x);b=derivative([v+dt*k/2 for v,k in zip(x,a)])
                c=derivative([v+dt*k/2 for v,k in zip(x,b)]);d=derivative([v+dt*k for v,k in zip(x,c)])
                x=[v+dt*(a+2*b+2*c+d)/6 for v,a,b,c,d in zip(x,a,b,c,d)]
        requested,out,common,minus,fb_request,fb,minus_fb=nodes(x[0],x[1],x[2],coef[3],main_rail,feedback_rail)
        result.append(out)
        if states:history.append(tuple(x)+(requested,common,minus,fb_request,fb,minus_fb))
    return (result,history) if states else result
