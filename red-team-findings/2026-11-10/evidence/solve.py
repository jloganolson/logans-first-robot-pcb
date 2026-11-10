import json, sys, numpy as np, scipy.sparse as sp, pyamg
from PIL import Image, ImageDraw
G=json.load(open(sys.argv[1]))
PX=10.0; X0,Y0,X1,Y1=0,0,110,140
W=int((X1-X0)*PX); H=int((Y1-Y0)*PX)
LAY=['F','In1','In2','B']; RHO=1.72e-8; PLATE=18e-6
def P(x,y): return ((x-X0)*PX,(y-Y0)*PX)
def raster(net):
    m={}
    for l in LAY:
        im=Image.new('L',(W,H),0); d=ImageDraw.Draw(im)
        for z in G['zones']:
            if z['net']==net and z['layer']==l:
                for p in z['polys']:
                    if len(p['o'])>2: d.polygon([P(*q) for q in p['o']],fill=1)
                # holes after all outlines of this zone
                for p in z['polys']:
                    for h in p['h']:
                        if len(h)>2: d.polygon([P(*q) for q in h],fill=0)
        for t in G['tracks']:
            if t['net']==net and t['layer']==l:
                w=max(1,int(round(t['w']*PX))); a,b_=P(t['x1'],t['y1']),P(t['x2'],t['y2'])
                d.line([a,b_],fill=1,width=w); r=w/2
                for c in (a,b_): d.ellipse([c[0]-r,c[1]-r,c[0]+r,c[1]+r],fill=1)
        for v in G['vias']:
            if v['net']==net:
                c=P(v['x'],v['y']); r=v['d']*PX/2; d.ellipse([c[0]-r,c[1]-r,c[0]+r,c[1]+r],fill=1)
        for p in G['pads']:
            if p['net']==net and l in p['layers']:
                for q in p['poly']:
                    if len(q['o'])>2: d.polygon([P(*s) for s in q['o']],fill=1)
        m[l]=np.array(im,dtype=bool)
    return m
def solve(net, src, snk, thick, hspan, label, I=30.0, report=True):
    """src/snk: list of (ref,num). thick: dict layer->m. hspan: 3 dielectric heights."""
    m=raster(net)
    idx={}; n=0
    for l in LAY:
        ii=-np.ones((H,W),dtype=np.int64); k=m[l].sum(); ii[m[l]]=np.arange(n,n+k); n+=k; idx[l]=ii
    rows=[];cols=[];vals=[]
    def add(a,b,g):
        rows.extend([a,b]);cols.extend([b,a]);vals.extend([g,g])
    R=[];C=[];V=[]
    for l in LAY:
        g=thick[l]/RHO; ii=idx[l]
        a=ii[:,:-1].ravel(); b=ii[:,1:].ravel(); k=(a>=0)&(b>=0); R.append(a[k]);C.append(b[k]);V.append(np.full(k.sum(),g))
        a=ii[:-1,:].ravel(); b=ii[1:,:].ravel(); k=(a>=0)&(b>=0); R.append(a[k]);C.append(b[k]);V.append(np.full(k.sum(),g))
    def barrel(x,y,drill):
        cx,cy=P(x,y); cx=int(cx); cy=int(cy)
        if not(0<=cx<W and 0<=cy<H): return
        for i in range(3):
            a=idx[LAY[i]][cy,cx]; b=idx[LAY[i+1]][cy,cx]
            if a>=0 and b>=0:
                g=np.pi*drill*1e-3*PLATE/(RHO*hspan[i]); R.append(np.array([a]));C.append(np.array([b]));V.append(np.array([g]))
    for v in G['vias']:
        if v['net']==net: barrel(v['x'],v['y'],v['drill'])
    term={}
    def padcells(p):
        cells=[]
        cx,cy=P(p['x'],p['y']); r=max(p['sx'],p['sy'])*PX/2*0.5 if p['tht'] else None
        for l in p['layers']:
            if p['tht']:
                yy,xx=np.ogrid[:H,:W]; mk=((xx-cx)**2+(yy-cy)**2<=(p['drill']*PX/2+2)**2)&m[l]
            else:
                im=Image.new('L',(W,H),0); d=ImageDraw.Draw(im)
                for q in p['poly']: d.polygon([P(*s) for s in q['o']],fill=1)
                mk=np.array(im,dtype=bool)&m[l]
            cells.append(idx[l][mk])
        return np.concatenate(cells) if cells else np.array([],dtype=np.int64)
    fixed={}
    for p in G['pads']:
        if p['net']!=net: continue
        key=(p['ref'],p['num'])
        if key in src:
            for c in padcells(p): fixed[c]=1.0
        elif key in snk:
            for c in padcells(p): fixed[c]=0.0
        elif p['tht']: barrel(p['x'],p['y'],p['drill'])
    R=np.concatenate(R);C=np.concatenate(C);V=np.concatenate(V)
    A=sp.coo_matrix((np.concatenate([V,V]),(np.concatenate([R,C]),np.concatenate([C,R]))),shape=(n,n)).tocsr()
    deg=np.asarray(A.sum(axis=1)).ravel(); Lp=sp.diags(deg)-A
    fx=np.array(list(fixed.keys()),dtype=np.int64); fv=np.array(list(fixed.values()))
    # keep only component connected to fixed nodes
    ncomp,lab=sp.csgraph.connected_components(A,directed=False)
    good=np.isin(lab,np.unique(lab[fx]))
    free=np.ones(n,bool); free[fx]=False; free&=good
    x=np.zeros(n); x[fx]=fv
    Lff=Lp[free][:,free].tocsr(); rhs=-(Lp[free][:,fx]@fv)
    ml=pyamg.smoothed_aggregation_solver(Lff,max_coarse=500)
    x[free]=ml.solve(rhs,tol=1e-8,maxiter=200)
    s1=fx[fv==1.0]; Itot=float((Lp[s1]@x).sum()); Rtot=1/Itot
    out={'label':label,'net':net,'R_mohm':Rtot*1e3,'I':I,'Vdrop_mV':Rtot*I*1e3,'P_W':Rtot*I*I}
    # current density per layer (A per mm width) at I
    scale=I/Itot; hot=[]
    for l in LAY:
        ii=idx[l]; g=thick[l]/RHO; v=np.full((H,W),np.nan); v[m[l]]=x[ii[m[l]]]
        gx=np.zeros((H,W)); gy=np.zeros((H,W))
        dx=(v[:,1:]-v[:,:-1]); dy=(v[1:,:]-v[:-1,:]); dx[np.isnan(dx)]=0; dy[np.isnan(dy)]=0
        gx[:,:-1]=dx; gy[:-1,:]=dy
        # K (A/m) = g*dV/dx(m) ; per mm: A/mm = g*dV/cell * PX /1000... dV per cell -> I through cell edge = g*dV ; width of cell =1/PX mm
        K=np.hypot(gx,gy)*g*scale*PX   # A per mm
        K[~m[l]]=0
        # exclude 2.5mm around terminals
        for p in G['pads']:
            if p['net']==net and ((p['ref'],p['num']) in src or (p['ref'],p['num']) in snk):
                cx,cy=P(p['x'],p['y']); r=(max(p['sx'],p['sy'])/2+0.8)*PX
                yy,xx=np.ogrid[:H,:W]; K[((xx-cx)**2+(yy-cy)**2<=r*r)]=0
        Pl=float(((gx**2+gy**2)*g).sum()*scale*scale)
        j=np.unravel_index(np.argmax(K),K.shape)
        out[l]={'P_W':Pl,'Kmax_A_per_mm':float(K[j]),'Jmax_A_mm2':float(K[j]/(thick[l]*1e3)),'at':(X0+j[1]/PX,Y0+j[0]/PX),'area_mm2':float(m[l].sum()/PX/PX)}
    if report:
        print(json.dumps(out,default=float))
    return out
STACKS={'2oz/1oz (v0.9)':({'F':70e-6,'In1':30e-6,'In2':30e-6,'B':70e-6},(0.109e-3,1.23e-3,0.109e-3)),
        '1oz/0.5oz':({'F':35e-6,'In1':15.2e-6,'In2':15.2e-6,'B':35e-6},(0.21e-3,1.065e-3,0.21e-3)),
        '1oz/1oz':({'F':35e-6,'In1':30e-6,'In2':30e-6,'B':35e-6},(0.21e-3,1.065e-3,0.21e-3)),
        '2oz/0.5oz':({'F':70e-6,'In1':15.2e-6,'In2':15.2e-6,'B':70e-6},(0.21e-3,1.065e-3,0.21e-3))}
CASES=json.load(open(sys.argv[2]))
res=[]
for c in CASES:
    for sn in c.get('stacks',STACKS):
        th,hs=STACKS[sn]
        res.append(solve(c['net'],[tuple(t) for t in c['src']],[tuple(t) for t in c['snk']],th,hs,c['label']+' | '+sn,c.get('I',30.0)))
json.dump(res,open(sys.argv[3],'w'),indent=1,default=float)
