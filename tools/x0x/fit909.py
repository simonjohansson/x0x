"""Data-driven 909: Tune phase sweep, Decay envelope field and joint onset field."""
from pathlib import Path
import json,math,time
import numpy as np
from scipy.interpolate import BSpline,PPoly
from scipy.optimize import least_squares
from scipy.linalg import solve
import csv,struct
import soundfile as sf
from . import cpu,fit808,field909
ROOT=cpu.ROOT/'research/reference/909-fit-model'
FIXTURES=cpu.ROOT/'tests/fixtures/909-model'
OUT=cpu.ROOT/'out/909-model/host'
RATE=48000;FRAMES=96000
TIME=np.array([.004,.006,.009,.014,.022,.035,.05,.058,.060,.062,.064,.066,.070,.075,.080,.09,.105,.125,.15,.18,.22,.26,.32,.4,.55,.8,1.2,2.])
PHASE_BREAKS=np.linspace(0,1,6)
CONTROL_BREAKS=np.linspace(0,1,17)
HARMONICS=(1,2,3,4,5)
NCHANNEL=1+2*len(HARMONICS)

def coord(cc):
    cc=np.asarray(cc,dtype=float)
    if not np.isfinite(cc).all() or np.any((cc<0)|(cc>127)):raise ValueError('Control outside 0..127')
    lo=np.floor(cc);fraction=cc-lo
    a=np.floor(lo*255/127+.5);b=np.floor(np.minimum(lo+1,127)*255/127+.5)
    return (a+fraction*(b-a))/255

def spline(x,breaks):
    knots=np.r_[np.repeat(breaks[0],4),breaks[1:-1],np.repeat(breaks[-1],4)]
    return BSpline.design_matrix(np.clip(x,breaks[0],breaks[-1]),knots,3).toarray()

def signal(raw,e):return np.asarray(raw[e['onset_sample']:e['onset_sample']+FRAMES,0],dtype=float)

def zeroes(y):
    z=np.flatnonzero((y[:-1]<=0)&(y[1:]>0));z=z[(z>200)&(z<18000)]
    z=z[np.maximum(abs(y[z+200]),abs(y[z-200]))>.0001]
    return (z-y[z]/(y[z+1]-y[z]))/RATE

def fit_phase(raw,events):
    chosen=[e for e in events if e['split']=='interaction' and e['partition']=='train' and e['attack_cc']==0 and e['decay_cc']==127]
    datasets=[];params=[]
    for e in chosen:
        t=zeroes(signal(raw,e));cycles=np.arange(len(t))
        def evaluate(p):return p[0]*t+p[1]-np.exp(p[2])*np.exp(-t/np.exp(p[3]))
        fit=least_squares(lambda p:evaluate(p)-cycles,[52.58,1.,np.log(3),np.log(.015)],bounds=([50,-30,-10,np.log(.0001)],[55,30,10,np.log(.3)]))
        p=fit.x;p[1]+=round(np.exp(p[2])-p[1])
        # Shift only the arbitrary cycle numbering, never the recorded samples.
        cycles=np.round(evaluate(p))
        params.append(p);datasets.append((coord(e['tune_cc']),t,cycles))
    params=np.array(params);C=spline(np.array([v[0] for v in datasets]),PHASE_BREAKS)
    initial=np.r_[np.median(params[:,0]),np.linalg.lstsq(C,params[:,1:],rcond=None)[0].T.ravel()]
    def objective(p):
        maps=p[1:].reshape(3,-1);rows=[]
        for x,t,y in datasets:
            b,lk,lt=(spline([x],PHASE_BREAKS)@maps.T)[0]
            rows.extend(p[0]*t+b-np.exp(lk)*np.exp(-t/np.exp(lt))-y)
        # Weak smoothness in the control maps, to avoid fitting source reset jitter.
        rows.extend((np.diff(maps,n=2,axis=1)*.001).ravel())
        return rows
    fitted=least_squares(objective,initial,max_nfev=400)
    model=dict(frequency=np.array([fitted.x[0]]),phase=fitted.x[1:].reshape(3,-1),phase_breaks=PHASE_BREAKS,time_knots=TIME,
               control_breaks=CONTROL_BREAKS,harmonics=np.array(HARMONICS))
    print('phase f0',model['frequency'],'rms cycles',np.sqrt(np.mean(np.array(objective(fitted.x))**2)),flush=True)
    return model

def angle(model,t,u):
    b,lk,lt=(spline([coord(u)],model['phase_breaks'])@model['phase'].T)[0]
    return 2*np.pi*(model['frequency'][0]*t+b-np.exp(lk)*np.exp(-t/np.exp(lt)))

def features(model,t,u):
    ph=angle(model,t,u)
    carrier=np.column_stack([np.ones(len(t)),*[f(h*ph) for h in model['harmonics'] for f in (np.sin,np.cos)]])
    return (spline(t,model['time_knots'])[:,None,:]*carrier[:,:,None]).reshape(len(t),-1)

def body(model,t,u,d):
    weights=(spline([coord(d)],model['control_breaks'])@model['control'].T)[0]
    coefficients=weights@model['basis']
    knots=model['time_knots'];extended=np.r_[np.repeat(knots[0],4),knots[1:-1],np.repeat(knots[-1],4)]
    env=BSpline(extended,coefficients.reshape(NCHANNEL,-1).T,3)(np.clip(t,knots[0],knots[-1]))
    ph=angle(model,t,u);y=env[:,0].copy()
    for j,h in enumerate(model['harmonics']):y+=env[:,1+2*j]*np.sin(h*ph)+env[:,2+2*j]*np.cos(h*ph)
    return y

def fit_body(raw,events,model,rank=5):
    chosen=[e for e in events if e['split']=='interaction' and e['partition']=='train' and e['attack_cc']==0]
    indices=np.r_[np.arange(240,2400,2),np.arange(2400,12000,8),np.arange(12000,36000,32),np.arange(36000,96000,128)]
    widths=np.diff(np.r_[indices,96000]);t=indices/RATE
    designs={u:features(model,t,u) for u in sorted({e['tune_cc'] for e in chosen})}
    n=next(iter(designs.values())).shape[1];matrices=[];grams=[];decays=sorted({e['decay_cc'] for e in chosen})
    for d in decays:
        G=np.zeros((n,n));b=np.zeros(n)
        for e in chosen:
            if e['decay_cc']!=d:continue
            y=signal(raw,e)[indices];X=designs[e['tune_cc']];w=widths/float(np.sum(y*y*widths))
            G+=X.T@(X*w[:,None]);b+=X.T@(y*w)
        G+=np.eye(n)*1e-5;matrices.append(solve(G,b,assume_a='pos'));grams.append(G)
    matrices=np.array(matrices);G=sum(grams)/len(grams)
    val,vec=np.linalg.eigh(G);good=val>val[-1]*1e-10
    root=vec[:,good]*np.sqrt(val[good]);inverse=(vec[:,good]/np.sqrt(val[good])).T
    U,S,V=np.linalg.svd(matrices@root,full_matrices=False)
    model['basis']=(V[:rank]@inverse)
    print('body singular values',S,flush=True)
    # Fit control weights against original waveforms, including dense train Decay axis.
    chosen=[e for e in events if e['partition']=='train' and e['attack_cc']==0]
    first={}
    for e in chosen:first.setdefault((e['tune_cc'],e['decay_cc']),e)
    nc=spline([0],model['control_breaks']).shape[1];G=np.zeros((rank*nc,rank*nc));b=np.zeros(rank*nc)
    designs={}
    for e in first.values():
        u,d=e['tune_cc'],e['decay_cc'];y=signal(raw,e)[indices]
        if u not in designs:designs[u]=features(model,t,u)@model['basis'].T
        X=designs[u];w=widths/float(np.sum(y*y*widths));inner=X.T@(X*w[:,None]);target=X.T@(y*w)
        c=spline([coord(d)],model['control_breaks'])[0]
        G+=np.kron(inner,np.outer(c,c));b+=np.kron(target,c)
    smooth=np.diff(np.eye(nc),n=2,axis=0);reg=np.kron(np.eye(rank),smooth.T@smooth)*.002
    model['control']=solve(G+reg+np.eye(rank*nc)*1e-8,b,assume_a='pos').reshape(rank,nc)
    print('body fit',len(first),'settings, rank',rank,flush=True)

def onset_control(events,model):
    tunes=spline(np.array([coord(e['tune_cc']) for e in events]),model['onset_tune_breaks'])
    attacks=spline(np.array([coord(e['attack_cc']) for e in events]),model['onset_attack_breaks'])
    decays=np.ones((len(events),1))
    return np.einsum('ij,ik,il->ijkl',tunes,attacks,decays).reshape(len(events),-1)

def fit_onset(raw,events,model,rank=12):
    chosen=[];seen=set()
    for e in events:
        key=tuple(e[k+'_cc'] for k in ('tune','attack','decay'))
        if e['partition']=='train' and key not in seen:chosen.append(e);seen.add(key)
    nodes=np.r_[np.arange(320),np.arange(320,1153,4)];t=nodes/RATE
    widths=np.r_[np.diff(nodes),4];rows=[];norms=[]
    fade=np.clip((nodes-288)/96,0,1);fade=fade*fade*(3-2*fade)
    bodies={}
    for e in chosen:
        y=signal(raw,e);key=(e['tune_cc'],e['decay_cc'])
        if key not in bodies:bodies[key]=body(model,t,*key)
        rows.append(y[nodes]-fade*bodies[key]);norms.append(np.linalg.norm(y))
    residual=np.array(rows);scale=np.array(norms)
    _,S,V=np.linalg.svd(residual*np.sqrt(widths)[None,:]/scale[:,None],full_matrices=False)
    model['onset_basis']=V[:rank]/np.sqrt(widths)[None,:];model['onset_nodes']=nodes
    print('onset singular',S[:16],flush=True)
    model['onset_tune_breaks']=np.linspace(0,1,9);model['onset_attack_breaks']=np.linspace(0,1,9)
    C=onset_control(chosen,model);target=(residual*widths[None,:])@model['onset_basis'].T
    G=C.T@(C/scale[:,None]**2)+np.eye(C.shape[1])*.01
    model['onset_control']=solve(G,C.T@(target/scale[:,None]**2),assume_a='pos').T
    model['onset_fade']=np.array([288,384,1056,1152])
    print('onset control fitted',model['onset_control'].shape,flush=True)

def render(model,u,a,d,frames=96000):
    t=np.arange(frames)/RATE;y=body(model,t,u,d)
    n=min(frames,int(model['onset_nodes'][-1]));C=onset_control([dict(tune_cc=u,attack_cc=a,decay_cc=d)],model)
    residual=(C@model['onset_control'].T@model['onset_basis'])[0]
    onset=np.interp(np.arange(n),model['onset_nodes'],residual)
    fade=np.clip((np.arange(n)-288)/96,0,1);fade=fade*fade*(3-2*fade)
    end=np.clip((np.arange(n)-1056)/96,0,1);end=end*end*(3-2*end)
    y[:n]=y[:n]*fade+onset*(1-end)
    return y


def evaluate(raw,events,model,partition,limit=0):
    # Start with axis and stratified settings; full partition scoring follows a frozen candidate.
    chosen=[e for e in events if e['partition']==partition]
    if limit:chosen=chosen[::max(1,len(chosen)//limit)][:limit]
    result=[]
    for e in chosen:
        u,a,d=(e[k+'_cc'] for k in ('tune','attack','decay'));y=signal(raw,e);pred=render(model,u,a,d)
        err=pred-y;row=dict(index=e['index'],settings=[u,a,d],l2=float(np.linalg.norm(err)/np.linalg.norm(y)),max_fs=float(abs(err).max()),after10ms_l2=float(np.linalg.norm(err[480:])/np.linalg.norm(y[480:])),peak=float(abs(pred).max()))
        result.append(row)
        print(partition,len(result),row,flush=True)
    return result

def load_events():
    path=FIXTURES/'events.csv'
    if fit808.digest(path)!='e20bf4b026c50ae1bf301e614fa121977bb8f76c4bc637b10b2ad7b0080ae29f':
        raise ValueError('909 setting/partition manifest changed')
    with path.open() as f:
        return [{k:v if k in ('split','partition') else int(float(v)) for k,v in row.items()} for row in csv.DictReader(f)]

def raw_audio():
    path=ROOT/'909-corpus.wav'
    if fit808.digest(path)!='ad05ef41060e4477dd5bb8fddcfe9de4c106576f448800b29f0693b86fc667ba':
        raise ValueError('909 source capture changed')
    info=sf.info(path)
    if (info.samplerate,info.channels,info.frames,info.subtype)!=(48000,2,430128000,'FLOAT'):
        raise ValueError('909 source capture format changed')
    with path.open('rb') as f:
        if f.read(12)[:4]!=b'RIFF':raise ValueError('909 capture is not RIFF')
        while True:
            name,size=struct.unpack('<4sI',f.read(8))
            if name==b'data':offset=f.tell();break
            f.seek(size+(size&1),1)
    return np.memmap(path,dtype='<f4',mode='r',offset=offset,shape=(info.frames,2))

def freeze(m):
    result=dict(frequency=m['frequency'].astype('float32'),time_frames=np.rint(m['time_knots']*48000).astype('uint32'),harmonics=m['harmonics'].astype('uint8'),onset_fade=m['onset_fade'].astype('uint16'),onset_nodes=m['onset_nodes'].astype('uint16'))
    
    def rows(name,values,bits):
        maximum=(1<<(bits-1))-1;scale=(np.max(abs(values),axis=1)/maximum).astype('float32');scale[scale==0]=1
        result[name+'_q']=np.clip(np.rint(values/scale[:,None]),-maximum,maximum).astype('int'+str(bits));result[name+'_scale']=scale
    
    basis=m['basis'].copy().reshape(5,11,-1);basis[:,:,0]=0 # This unused basis has support entirely before the body crossfade.
    rows('body',basis.reshape(5,-1),16);rows('control',m['control'],16)
    rows('onset',m['onset_basis'],8);rows('onset_control',m['onset_control'],16)
    frames=result['time_frames'].astype(float);knots=np.r_[np.repeat(frames[0],4),frames[1:-1],np.repeat(frames[-1],4)]
    polys=np.zeros((len(frames)-1,3,4))
    for segment in range(len(frames)-1):
        width=frames[segment+1]-frames[segment]
        for j in range(3):
            unit=np.zeros(len(frames)+2);unit[segment+j]=1
            p=PPoly.from_spline((knots,unit,3));polys[segment,j]=p.c[:,segment+3]*width**np.arange(3,-1,-1)
    q=np.rint(polys*4096);assert abs(q).max()<32767;result['time_poly_q']=q.astype('int16')
    phase=[]
    for cell in range(16):
        u=np.arange(4)/3;x=(cell+u)/16
        b,lk,lt=(spline(x,m['phase_breaks'])@m['phase'].T).T;K=np.exp(lk);lam=-np.expm1(-1/(48000*np.exp(lt)))
        values=np.array([b-K,K,lam]).T
        phase.append(np.linalg.solve(np.vander(u),values).T)
    result['phase_poly']=np.asarray(phase,dtype='float32')
    path=OUT/'909.npz';np.savez(path,**result);field909.load(path)
    return path

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    events=load_events();raw=raw_audio()
    model=fit_phase(raw,events);fit_body(raw,events,model);fit_onset(raw,events,model)
    np.savez(OUT/'candidate.npz',**model)
    path=freeze(model)
    print('Frozen coefficient source:',path,'SHA-256',fit808.digest(path),flush=True)

if __name__=='__main__':main()
