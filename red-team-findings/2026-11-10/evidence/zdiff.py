import numpy as np, scipy.sparse as sp, scipy.sparse.linalg as spl
E0=8.854e-12; C0L=299792458.0
def zmode(w,s,h,t,er,mask=0.0,er_m=3.5,odd=True,d=0.005):
    # half-domain x>=0, symmetry plane at x=0 (odd: V=0 wall, even: Neumann). units mm
    Wd=max(8*h,2.5)+s/2+w; Ht=h+t+max(8*h,2.0)
    nx=int(round(Wd/d)); ny=int(round(Ht/d))
    X=(np.arange(nx)+0.5)*d; Y=(np.arange(ny)+0.5)*d
    xx,yy=np.meshgrid(X,Y)
    cond=(xx>=s/2)&(xx<=s/2+w)&(yy>=h)&(yy<=h+t)
    def solve(diel):
        eps=np.ones((ny,nx))
        if diel:
            eps[yy<h]=er
            if mask>0:
                mk=(yy>=h)&(yy<h+mask)&~cond
                mk|=(yy>=h+t)&(yy<h+t+mask)&(xx>=s/2-mask)&(xx<=s/2+w+mask)
                mk|=(yy>=h)&(yy<h+t)&(((xx>=s/2-mask)&(xx<s/2))|((xx>s/2+w)&(xx<=s/2+w+mask)))
                eps[mk]=er_m
        N=nx*ny; idx=np.arange(N).reshape(ny,nx)
        ex=2*eps[:,:-1]*eps[:,1:]/(eps[:,:-1]+eps[:,1:]); ey=2*eps[:-1,:]*eps[1:,:]/(eps[:-1,:]+eps[1:,:])
        r=np.concatenate([idx[:,:-1].ravel(),idx[:-1,:].ravel()]); c=np.concatenate([idx[:,1:].ravel(),idx[1:,:].ravel()]); v=np.concatenate([ex.ravel(),ey.ravel()])
        A=sp.coo_matrix((np.concatenate([v,v]),(np.concatenate([r,c]),np.concatenate([c,r]))),shape=(N,N)).tocsr()
        diag=np.asarray(A.sum(1)).ravel()
        # boundaries: bottom ground (y=0) Dirichlet 0 via half-cell conductance 2*eps; left wall if odd
        diag+= np.where(np.arange(N)<nx, 2*eps[0,:].repeat(1)[np.arange(N)%nx], 0)
        if odd: diag+= np.where(np.arange(N)%nx==0, 2*eps[:,0][np.arange(N)//nx], 0)
        Lp=sp.diags(diag)-A
        fx=idx[cond]; free=np.ones(N,bool); free[fx]=False
        x=np.zeros(N); x[fx]=1
        x[free]=spl.spsolve(Lp[free][:,free].tocsc(), -(Lp[free][:,fx]@np.ones(len(fx))))
        q=(Lp[fx]@x).sum()
        return q*E0   # F/m
    C=solve(True); Ca=solve(False)
    return 1/(C0L*np.sqrt(C*Ca))
def zd(w,s,h,t,er,mask=0.02): return 2*zmode(w,s,h,t,er,mask)
def z0(w,h,t,er,mask=0.02): return zmode(w,20.0,h,t,er,mask,odd=False) if False else zmode(w,6.0,h,t,er,mask,odd=False)
stk={'v0.9 JLC041621-2116 2oz':(0.109,0.065,4.16),'default JLC04161H-7628 1oz':(0.2104,0.035,4.4),'JLC04161H-3313 1oz':(0.0994,0.035,4.1),'JLC04161H-2116? 1oz':(0.1164,0.035,4.16)}
for n,(h,t,er) in stk.items():
    print(n,'| existing 0.165/0.300 Zdiff = %.1f (mask) %.1f (bare)'%(zd(.165,.3,h,t,er),zd(.165,.3,h,t,er,0)))
def find(s,h,t,er,target=90):
    lo,hi=0.08,0.6
    for _ in range(14):
        m=(lo+hi)/2
        if zd(m,s,h,t,er)>target: lo=m
        else: hi=m
    return (lo+hi)/2
for n in ['default JLC04161H-7628 1oz','JLC04161H-3313 1oz']:
    h,t,er=stk[n]
    for s in (0.127,0.15,0.2,0.3):
        print(n,'90 ohm: gap %.3f -> width %.3f mm'%(s,find(s,h,t,er)))
# FS/other widths on 7628
h,t,er=stk['default JLC04161H-7628 1oz']
print('7628 0.25/?: existing FS 0.25 wide gap0.2 ->',round(zd(.25,.2,h,t,er),1))
