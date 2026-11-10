"""Steady-state board heating estimate for v0.10 from its actual copper.

Model: the board is one conducting sheet (through-thickness temperature
gradients ignored). Each 0.25 mm cell conducts sideways through whatever copper
each of the four layers has there plus the FR-4, and loses heat to still air
from both faces. Part losses are spread over each part's footprint. This gives
BOARD temperature under a part, not junction temperature, and its absolute
accuracy is roughly +/-30% because the air-side coefficient is a guess. It is
most useful for comparing copper weights on identical geometry.
Usage: uv run --with numpy --with scipy --with pillow --with pyamg --with matplotlib python thermal.py geom.json outdir
"""
import json,sys,numpy as np,scipy.sparse as sp,pyamg
from PIL import Image,ImageDraw
G=json.load(open(sys.argv[1]));OUT=sys.argv[2]
PX=4.0;Wmm,Hmm=228.0,195.0;W=int(Wmm*PX);H=int(Hmm*PX);LAY=['F','In1','In2','B']
KCU=390.0;KFR4=0.8;TFR4=1.6e-3
def P(x,y):return (x*PX,y*PX)
def copper(layer):
    im=Image.new('L',(W,H),0);d=ImageDraw.Draw(im)
    for z in G['zones']:
        if z['layer']!=layer:continue
        for q in z['polys']:
            if len(q['o'])>2:d.polygon([P(*s) for s in q['o']],fill=1)
        for q in z['polys']:
            for h in q['h']:
                if len(h)>2:d.polygon([P(*s) for s in h],fill=0)
    for t in G['tracks']:
        if t['layer']==layer:d.line([P(t['x1'],t['y1']),P(t['x2'],t['y2'])],fill=1,width=max(1,int(round(t['w']*PX))))
    for v in G['vias']:
        c=P(v['x'],v['y']);r=v['d']*PX/2;d.ellipse([c[0]-r,c[1]-r,c[0]+r,c[1]+r],fill=1)
    for q in G['pads']:
        if layer in q['layers']:b=q['bbox'];d.rectangle([P(b[0],b[1]),P(b[2],b[3])],fill=1)
    return np.array(im,dtype=float)
CU={l:copper(l) for l in LAY}
def buck(I,vout,dcr,vin=30.0,fsw=500e3):
    D=vout/vin;return dict(ic=I*I*.092*1.3*D+.5*vin*I*20e-9*fsw+vin*.00015,diode=.55*I*(1-D),ind=I*I*dcr*1.2)
def sources(thor_a=8.0,vin=30.0):
    s={}
    D=24.33/vin
    s['Q2']=thor_a**2*.0034*1.3*D+.5*vin*thor_a*25e-9*200e3
    s['Q3']=thor_a**2*.0034*1.3*(1-D)+.9*thor_a*2*30e-9*200e3+.15
    s['L1']=(thor_a**2+.9)*.0086*1.3+.2
    s['U2']=vin*.015
    total_in=(24.33*thor_a/.95+45)/vin
    s['Q1']=total_in**2*.004*1.3
    # rail, IC, diode, inductor, load A, Vout, inductor DCR
    for name,(u,dd,l,I,vo,dcr) in dict(pi_spare_5V=('U3','D101','L2',1.0,5.0,.025),usb_5V=('U4','D201','L3',.6,5.0,.025),xl330_5V=('U5','D301','L4',2.0,5.0,.025),
        xl430_10V8=('U6','D401','L5',2.0,10.8,.030),aux_11V7=('U7','D501','L6',4.0,11.7,.030),mg90s_5V=('U7003','D7101','L7002',1.0,5.0,.025)).items():
        b=buck(I,vo,dcr,vin);s[u]=b['ic'];s[dd]=b['diode'];s[l]=b['ind']
    s['U13']=1.0;s['U12']=.25;s['U10']=.15;s['U7002']=.1
    return s
def solve(th,h_side,src):
    g=sum(CU[l]*KCU*th[l] for l in LAY)+KFR4*TFR4         # W/K per square
    cell=(1e-3/PX)**2;N=W*H;idx=np.arange(N).reshape(H,W)
    gx=2*g[:,:-1]*g[:,1:]/(g[:,:-1]+g[:,1:]);gy=2*g[:-1,:]*g[1:,:]/(g[:-1,:]+g[1:,:])
    r=np.concatenate([idx[:,:-1].ravel(),idx[:-1,:].ravel()]);c=np.concatenate([idx[:,1:].ravel(),idx[1:,:].ravel()]);v=np.concatenate([gx.ravel(),gy.ravel()])
    A=sp.coo_matrix((np.concatenate([v,v]),(np.concatenate([r,c]),np.concatenate([c,r]))),shape=(N,N)).tocsr()
    M=(sp.diags(np.asarray(A.sum(1)).ravel()+2*h_side*cell)-A).tocsr()
    q=np.zeros((H,W))
    for ref,p_w in src.items():
        b=G['parts'][ref]['bbox'];x0,y0,x1,y1=[int(round(k*PX)) for k in b];x0,y0=max(x0,0),max(y0,0)
        q[y0:y1,x0:x1]+=p_w/((y1-y0)*(x1-x0))
    T=pyamg.smoothed_aggregation_solver(M,max_coarse=500).solve(q.ravel(),tol=1e-8,maxiter=300).reshape(H,W)
    return T
STACKS={'2 oz / 1 oz (v0.9)':dict(F=70e-6,In1=30e-6,In2=30e-6,B=70e-6),'1 oz / 0.5 oz (v0.10)':dict(F=35e-6,In1=15.2e-6,In2=15.2e-6,B=35e-6),'1 oz / 1 oz (+$18)':dict(F=35e-6,In1=30e-6,In2=30e-6,B=35e-6)}
res={};maps={}
for case,thor in (('Thor 8 A',8.0),('Thor 5.4 A (130 W)',5.4)):
    src=sources(thor)
    for h_side,hn in ((10.0,'still air, typical'),(6.0,'still air, pessimistic')):
        if thor!=8.0 and h_side!=10.0:continue
        for sn,th in STACKS.items():
            T=solve(th,h_side,src);j=np.unravel_index(np.argmax(T),T.shape)
            under={}
            for ref in src:
                b=G['parts'][ref]['bbox'];x0,y0,x1,y1=[int(round(k*PX)) for k in b];under[ref]=round(float(T[max(y0,0):y1,max(x0,0):x1].max()),1)
            key='%s | %s | %s'%(case,hn,sn);res[key]=dict(total_W=round(sum(src.values()),2),peak_rise_C=round(float(T[j]),1),peak_at_mm=[j[1]/PX,j[0]/PX],board_rise_under_part_C=under)
            if h_side==10.0 and thor==8.0:maps[sn]=T
            print('%-62s total %.1f W  peak +%.0f C at (%.0f,%.0f)  L1 +%.0f Q2 +%.0f U2 +%.0f U7(AUX) +%.0f D501 +%.0f U5 +%.0f U13 +%.0f'%(key,sum(src.values()),T[j],j[1]/PX,j[0]/PX,under['L1'],under['Q2'],under['U2'],under['U7'],under['D501'],under['U5'],under['U13']))
res['assumed_losses_W_thor_8A']={k:round(v,2) for k,v in sources(8.0).items()}
json.dump(res,open(OUT+'/thermal-results.json','w'),indent=1)
import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
fig,ax=plt.subplots(1,3,figsize=(18,5.6));vmax=max(float(m.max()) for m in maps.values())
for a,(sn,T) in zip(ax,maps.items()):
    im=a.imshow(T,extent=[0,Wmm,Hmm,0],cmap='inferno',vmin=0,vmax=vmax);a.set_title('%s\npeak +%.0f C above ambient'%(sn,T.max()));a.set_xlabel('mm');a.set_ylabel('mm')
fig.colorbar(im,ax=ax,label='board temperature rise above ambient (C)',shrink=.85)
fig.suptitle('Robot PDB v0.10 copper, Thor at 8 A plus typical rail loads, still air (model estimate, about +/-30%)')
fig.savefig(OUT+'/thermal-map.png',dpi=110,bbox_inches='tight')
