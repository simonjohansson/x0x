"""Frozen 909 mathematical reference: phase sweep, envelope field and joint onset."""
from pathlib import Path
import hashlib
import numpy as np
from scipy.interpolate import BSpline

ROOT=Path(__file__).resolve().parents[2]
RATE,FRAMES=48000,96000
MODEL_SHA='6ec82575d6355a44e16eba9b5724253295ef8322e4c342f1c4394c59abd450d2'

def coordinate(raw):
    value=np.asarray(raw,dtype=float)
    if not np.isfinite(value).all() or np.any((value<0)|(value>32512)):
        raise ValueError('Native control must be finite in 0..32512')
    cc=np.floor(value/256);fraction=value/256-cc
    lo=np.floor(cc*255/127+.5);hi=np.floor(np.minimum(cc+1,127)*255/127+.5)
    return (lo+fraction*(hi-lo))/255

def spline(x,intervals):
    breaks=np.linspace(0,1,intervals+1)
    knots=np.r_[np.repeat(0.,4),breaks[1:-1],np.repeat(1.,4)]
    return BSpline.design_matrix(np.clip(x,0,1),knots,3).toarray()

def decode(model,name):return model[name+'_q'].astype(float)*model[name+'_scale'][:,None]

def load(path=None):
    source=Path(path or ROOT/'models/909.npz')
    if path is None and hashlib.sha256(source.read_bytes()).hexdigest()!=MODEL_SHA:raise ValueError('Frozen 909 model hash mismatch')
    with np.load(source,allow_pickle=False) as f:model={k:f[k] for k in f.files}
    required={'frequency','phase_poly','time_frames','time_poly_q','harmonics','body_q','body_scale','control_q','control_scale','onset_q','onset_scale','onset_control_q','onset_control_scale','onset_fade','onset_nodes'}
    if set(model)!=required or not all(np.isfinite(x).all() for x in model.values()):raise ValueError('Invalid 909 coefficient source')
    ranks=model['body_q'].shape[0];channels=1+2*len(model['harmonics']);times=len(model['time_frames'])+2
    if (ranks!=5 or channels!=11 or times!=30 or model['body_q'].shape!=(5,330) or model['control_q'].shape!=(ranks,19)
            or model['onset_q'].shape!=(12,529) or model['onset_control_q'].shape!=(12,121)
            or model['time_poly_q'].shape!=(len(model['time_frames'])-1,3,4)
            or model['phase_poly'].shape!=(16,3,4) or np.any(np.diff(model['time_frames'].astype(float))<=0)
            or model['onset_fade'].tolist()!=[288,384,1056,1152] or not np.array_equal(model['onset_nodes'],np.r_[np.arange(320),np.arange(320,1153,4)])):raise ValueError('Invalid 909 geometry')
    for name in ('body','control','onset','onset_control'):
        expected='int8' if name=='onset' else 'int16'
        if model[name+'_q'].dtype!=np.dtype(expected) or model[name+'_scale'].shape!=(model[name+'_q'].shape[0],) or np.any(model[name+'_scale']<=0):raise ValueError('Invalid quantized 909 rows')
    return model

def parameters(model,tune):
    x=float(coordinate(tune))*16;cell=min(int(x),15);u=x-cell
    return np.array([np.polyval(p,u) for p in model['phase_poly'][cell]])

def weights(model,tune,attack,decay):
    b=spline([float(coordinate(decay))],16)@decode(model,'control').T
    c=np.einsum('i,j->ij',spline([float(coordinate(tune))],8)[0],spline([float(coordinate(attack))],8)[0]).ravel()
    p=c@decode(model,'onset_control').T
    return b[0],p

def render(model,tune,attack,decay,frames=FRAMES):
    if type(frames) is not int or not 1<=frames<=FRAMES:raise ValueError('Expected one complete or partial isolated 909 hit')
    phi0,K,lam=parameters(model,tune)
    if not 0<lam<1:raise ValueError('Unstable phase recurrence')
    w,p=weights(model,tune,attack,decay)
    n=np.arange(frames,dtype=float);ph=2*np.pi*(model['frequency'][0]*n/RATE+phi0-K*np.expm1(n*np.log1p(-lam)))
    channels=1+2*len(model['harmonics']);coeff=(w@decode(model,'body')).reshape(channels,-1)
    tf=model['time_frames'];cell=np.clip(np.searchsorted(tf,n,side='right')-1,0,len(tf)-2)
    u=np.clip((n-tf[cell])/(tf[cell+1]-tf[cell]),0,1)
    polys=model['time_poly_q'][cell].astype(float)/4096
    bases=((polys[:,:,0]*u[:,None]+polys[:,:,1])*u[:,None]+polys[:,:,2])*u[:,None]+polys[:,:,3]
    last=coeff[:,cell+3].T
    env=last.copy()
    for j in range(3):env+=bases[:,j,None]*(coeff[:,cell+j].T-last)
    y=env[:,0].copy()
    for j,h in enumerate(model['harmonics']):y+=env[:,1+2*j]*np.sin(h*ph)+env[:,2+2*j]*np.cos(h*ph)
    count=min(frames,int(model['onset_nodes'][-1]));nodes=p@decode(model,'onset')
    onset=np.interp(np.arange(count),model['onset_nodes'],nodes)
    low,high,release,end=model['onset_fade'];g=np.clip((np.arange(count)-low)/(high-low),0,1);g=g*g*(3-2*g)
    f=np.clip((np.arange(count)-release)/(end-release),0,1);f=f*f*(3-2*f)
    y[:count]=g*y[:count]+(1-f)*onset
    return y
