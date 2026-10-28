"""S02 p6/p11, S06: free-running digital noise and the stock BD passive path.

The source uses 31/13 XOR feedback, five further output delays, and a nominal
300kHz clock. This is an explicit component-tolerance baseline, not a universal
measured clock. Logic levels are ideal0/15V from the S02 supply. No recording
amplitude or random phase is fitted. Initialization/seeds belong to one engine
clock owner; a note trigger never resets the source or its passive filters.

The three linear states are C15 deviation from its DC mean, C13 voltage and the
noise-induced component of C11 voltage. The pulse helper owns C11's independent
pulse component, allowing exact linear superposition before the common Q6 VCA.
shortcut: ideal CMOS voltage source, ideal follower and first-order Q6 current
VCA; finite generator impedance/beta and measured clock spread are unqualified.
"""
import math
from . import attack909 as pulse

RATE=48000
CLOCK_HZ=300000
QUANTUM_HZ=4800000
CLOCK_QUANTA=16
SAMPLE_QUANTA=100
SUBSTEPS=4
INTERVAL_QUANTA=25
R10,R9,R46,C15,C13=12000.,4700.,4700.,.47e-6,.1e-6
RTH=R10*R9/(R10+R9)
DIVIDER=R9/(R10+R9)
LOGIC_HIGH=15.
MEAN_V=LOGIC_HIGH*.5*DIVIDER
INITIAL_FILTER=(0.,0.,0.)
DEFAULT_SEED=0x5eed12345
MASK36=(1<<36)-1


def validate_source(source):
    word,phase=source
    if type(word) is not int or not 0<word<=MASK36 or not word&((1<<31)-1) or type(phase) is not int or not 0<=phase<16:
        raise ValueError('source needs a nonzero31-bit core and phase in0..15')


def shift(word):
    """Independent mathematical recurrence, no copied article firmware."""
    feedback=((word>>30)^(word>>12))&1
    return ((word<<1)|feedback)&MASK36


def source_interval(source,quanta=INTERVAL_QUANTA):
    """Exact average Thevenin source over an integer4800kHz time interval."""
    validate_source(source)
    if type(quanta) is not int or quanta<=0:
        raise ValueError('positive integer time interval required')
    word,phase=source;left=quanta;ones=0
    while left:
        count=min(16-phase,left)
        ones+=count*((word>>35)&1)
        phase+=count;left-=count
        if phase==16:word=shift(word);phase=0
    return ((2*ones/quanta)-1)*MEAN_V,(word,phase)


def mix(raw):
    pulse.passive_mix(raw)
    z=pulse.VR3*(1-raw/pulse.RAW_MAX)+pulse.R55
    conductance=1/pulse.R44+1/pulse.R45+1/pulse.R56+1/z
    return z,1/(pulse.R45*conductance),1/(pulse.R44*conductance)


def derivative(state,drive,raw):
    v15,v13,v11=state
    _,alpha,beta=mix(raw)
    node=alpha*v13-beta*v11
    current15=(drive-v15-v13)/(RTH+R46)
    return (current15/C15,(current15-(v13-node)/pulse.R45)/C13,
            (-v11-node)/(pulse.R44*pulse.C11))


def step(state,drive,raw,dt=1/(RATE*SUBSTEPS)):
    a=derivative(state,drive,raw)
    b=derivative(tuple(v+dt*k/2 for v,k in zip(state,a)),drive,raw)
    c=derivative(tuple(v+dt*k/2 for v,k in zip(state,b)),drive,raw)
    d=derivative(tuple(v+dt*k for v,k in zip(state,c)),drive,raw)
    return tuple(v+dt*(i+2*j+2*k+l)/6 for v,i,j,k,l in zip(state,a,b,c,d))


def current(state,raw):
    """Signed current before Q6 ENV2, using the same passive mix as the pulse."""
    z,alpha,beta=mix(raw)
    return (alpha*state[1]-beta*state[2])/z


def continue_reference(source,state,raw,frames,*,changes=None):
    """Four average-drive RK4 intervals/sample; source never depends on voices."""
    validate_source(source);mix(raw)
    if len(state)!=3 or any(not math.isfinite(v) for v in state) or type(frames) is not int or frames<0:
        raise ValueError('invalid passive state or frame count')
    samples=[]
    for n in range(frames):
        raw=(changes or {}).get(n,raw)
        for _ in range(SUBSTEPS):
            drive,source=source_interval(source)
            state=step(state,drive,raw)
        samples.append(current(state,raw))
    return samples,source,state


def oracle(source,state,raw,frames):
    """Independent clock-edge split: actual held logic, four RK4 pieces/edge.

    No averaged input is used. This measures the target average-drive error
    without choosing or optimizing a seed against recorded noise.
    """
    validate_source(source);mix(raw);word,phase=source;samples=[]
    for _ in range(frames):
        left=SAMPLE_QUANTA
        while left:
            span=min(16-phase,left);drive=MEAN_V*(1 if word&(1<<35) else -1)
            for _ in range(4):state=step(state,drive,raw,span/(QUANTUM_HZ*4))
            phase+=span;left-=span
            if phase==16:word=shift(word);phase=0
        samples.append(current(state,raw))
    return samples,(word,phase),state


def env2(frames,*,substeps=128):
    """Independent two-cap ENV2 flow, sharing the source-supported pulse constants."""
    e7=e12=0.;out=[];dt=1/(RATE*substeps)
    def flow(v,w,on):
        gate=v>pulse.Q3_THRESHOLD
        load=(v-pulse.Q6_BASE)/pulse.R18 if gate else v/(pulse.R18+pulse.R17)
        return ((max(pulse.HIGH-pulse.VBE-v,0)/pulse.R20 if on else 0)-load)/pulse.C7,((max(pulse.HIGH-w,0)/pulse.R41 if gate else 0)-max(w-pulse.Q6_BASE,0)/pulse.R42)/pulse.C12
    for n in range(frames):
        for _ in range(substeps):
            a,b=flow(e7,e12,n<96);c,d=flow(e7+dt*a/2,e12+dt*b/2,n<96)
            e,f=flow(e7+dt*c/2,e12+dt*d/2,n<96);g,h=flow(e7+dt*e,e12+dt*f,n<96)
            e7+=dt*(a+2*c+2*e+g)/6;e12+=dt*(b+2*d+2*f+h)/6
        out.append(max(e12-pulse.Q6_BASE,0)/16)
    return out


def audio(currents,envelope):
    if len(currents)!=len(envelope):raise ValueError('current and envelope lengths differ')
    return [-pulse.CURRENT_TO_AUDIO*i*g for i,g in zip(currents,envelope)]
