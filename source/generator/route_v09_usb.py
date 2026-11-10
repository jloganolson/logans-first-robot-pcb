"""Route v09 host, hub and PWM USB2 integration pairs, preserving source-cell copper.

Callable apply(integration); CLI writes disposable copies only. Manufacturer
spacing exceptions are bounded package escapes, never blanket clearances.
"""
import argparse,collections,heapq,hashlib,json,math,re,shutil,signal,sys,types
from pathlib import Path
import pcbnew as p
import route_v07 as G
from rev09 import BOARD_SIZE_MM

W=.165; GAP=.300; SEP=(W+GAP)/2
NAMES=[('USB_DP','USB_DM'),('HUB_UP_DP','HUB_UP_DM'),('P4_DP','P4_DM')]
def channel(net):
    if net in NAMES[0]+NAMES[1]:return 'UPSTREAM'
    m=re.fullmatch(r'(P[1-4])_D[PM]',net)
    return m[1] if m else None
def inside(q,box):return box[0]-1e-9<=q[0]<=box[2]+1e-9 and box[1]-1e-9<=q[1]<=box[3]+1e-9
def near(item,q):
    if item.GetClass()=='PAD':
        bb=item.GetBoundingBox();return (max(p.ToMM(bb.GetLeft()),min(q[0],p.ToMM(bb.GetRight()))),max(p.ToMM(bb.GetTop()),min(q[1],p.ToMM(bb.GetBottom()))))
    a,b=p.ToMM(item.GetStart()),p.ToMM(item.GetEnd());v=(b[0]-a[0],b[1]-a[1]);den=v[0]**2+v[1]**2;t=max(0,min(1,((q[0]-a[0])*v[0]+(q[1]-a[1])*v[1])/den)) if den else 0
    return (a[0]+t*v[0],a[1]+t*v[1])
def install_spacing(i):
    regions=[]
    for ref,hx,hy in [('U10',5,5),('U11',3.8,4.45),('U9902',3.75,4.0),('U7002',6.5,6.5),('U7009',2.5,3)]:
        f=i.fps[ref];x,y=p.ToMM(f.GetPosition());nets={q.GetNetname() for q in f.Pads()}
        regions.append(dict(reference=ref,box_mm=(x-hx,y-hy,x+hx,y+hy),nets=nets))
    regions[0]['box_mm']=(202,97,212.5,107)
    regions[0]['rationale']='U10 right edge body+3.5mm only; preserved power-via escape. Other edges body+3mm.'
    esd=next(r for r in regions if r['reference']=='U7009');box=esd['box_mm'];esd['box_mm']=(box[0],box[1],104.9,box[3]);esd['rationale']='U7009 right edge104.50→104.90 only, short pair flare around pin5; body+2.1mm, within3mm package-escape rationale.'
    mcu=next(r for r in regions if r['reference']=='U7002');mcu['rationale']='7mm LQFP body plus3mm bounded escape on all sides, own MCU nets only; actual minima reported.'
    def spacing(self,item,q,ordinary=.205,ownnet=None):
        other=item.GetNetname()
        if ownnet=='GND' or other in ('GND','') or other.endswith('_NC') or other.startswith('IO_NC_'):return ordinary
        if channel(ownnet) and channel(ownnet)==channel(other):return ordinary
        if not channel(ownnet) and not channel(other):return ordinary
        at=near(item,q)
        for region in regions:
            # Keep a small search guard inside the reported boundary, so a
            # grid sample cannot jump over a short outside-region violation.
            box=region['box_mm'];margin=.075 if getattr(self,'usb_search_guard',False) else 0
            guard=(box[0]+margin,box[1]+margin,box[2]-margin,box[3]-margin)
            if ownnet in region['nets'] and other in region['nets'] and inside(q,guard) and inside(at,guard):return ordinary
        return max(ordinary,1.275 if other in ('H_XI','H_XO') or ownnet in ('H_XI','H_XO') else .767)
    i.external_spacing=types.MethodType(spacing,i)
    i.usb_regions=regions

def clear_leg(i,net,path,layer,width=W):
    for a,b in zip(path,path[1:]):
        for q in G.samples([a,b],.035):
            pt=p.VECTOR2I(p.FromMM(q[0]),p.FromMM(q[1]))
            for it in i.fx._items(layer,net,*q,3):
                clr=i.external_spacing(it,q,.205,net)
                if it.HitTest(pt,p.FromMM(width/2+clr)):return False
    return True

def repair_clock(i):
    # Only the existing first clock bend blocks the lower-left P4 escape.
    # Retain the crystal, its other branch, all P1/P2 copper and H_LED.
    path=[i.pad('U10','4'),(203.8,102.25),(203.4,102.6),i.pad('Y1','1')]
    assert clear_leg(i,'H_XI',path,p.F_Cu,.2),'Bounded clock repair obstructed'
    old=[]
    for t in list(i.b.GetTracks()):
        if t.GetNetname()=='H_XI':
            assert t.GetClass()=='PCB_TRACK' and t.GetLayer()==p.F_Cu
            old.append(dict(uuid=t.m_Uuid.AsString(),a=p.ToMM(t.GetStart()),b=p.ToMM(t.GetEnd()),width=p.ToMM(t.GetWidth())))
            i.remove(t)
    i.g.track('H_XI',path,.2,'F');i.fx._index=None
    i.evidence.append(dict(action='Bounded P4 clock first-bend repair',removed=old,replacement=path,width=.2,layer='F',unchanged='Crystal, H_XO, H_LED, P1/P2 and local supply paths'))

def search(i,names,a,b,ad,bd,guide,layer,step=.2,budget=60000,side=-1):
    """Direction-aware coupled centreline; checks both actual offset rails."""
    dirs=((1,0),(1,1),(0,1),(-1,1),(-1,0),(-1,-1),(0,-1),(1,-1))
    hd=lambda d:max(range(8),key=lambda n:sum(d[k]*dirs[n][k] for k in (0,1))/math.hypot(*dirs[n]))
    x0=a[0]-math.ceil((a[0]-min(q[0] for q in guide)+4)/step)*step;y0=a[1]-math.ceil((a[1]-min(q[1] for q in guide)+4)/step)*step
    xy=lambda q:(x0+q[0]*step,y0+q[1]*step)
    start=(round((a[0]-x0)/step),round((a[1]-y0)/step),hd(ad),0)
    # Search to an aligned pre-approach, then close the sub-grid residual
    # with two shallow equal-offset bends and a true final tangent.
    pre=G.add(b,G.mul(bd,-1.0))
    goal=(round((pre[0]-x0)/step),round((pre[1]-y0)/step));gh=hd(bd)
    def blocks(it,rail,net):
        if it.GetNetname() in names:return False
        if it.HitTest(p.VECTOR2I(p.FromMM(rail[0]),p.FromMM(rail[1])),p.FromMM(W/2+i.external_spacing(it,rail,.205,net))):return True
        if it.GetClass()=='PCB_VIA' and it.GetNetname() not in ('GND',''):
            # Preserve adjacent ground at signal centreline even in the
            # bounded package escape; full trace width is protected outside.
            local=any(inside(rail,r['box_mm']) and net in r['nets'] for r in i.usb_regions)
            radius=p.ToMM(it.GetWidth())/2+.300+(.005 if local else W/2+.010)
            if math.dist(rail,p.ToMM(it.GetPosition()))<radius:return True
        return False
    def reference_free(rail):
        if layer!=p.B_Cu:return True
        pt=p.VECTOR2I(p.FromMM(rail[0]),p.FromMM(rail[1]))
        return not any(it.GetClass()=='PCB_TRACK' and it.GetLayer()==p.In2_Cu and it.GetNetname() not in ('GND','')
                       and it.HitTest(pt,p.FromMM(W/2+.270)) for it in i.fx._items(p.In2_Cu,'',*rail,2))
    cache={}
    transition_cache={}
    def free(q,h=None,nh=None):
        h=q[2] if h is None else h;nh=h if nh is None else nh;key=(*q[:2],h,nh)
        if key not in cache:
            point=xy(q);u=G.norm(dirs[h]);v=G.norm(dirs[nh]);n1=(-u[1],u[0]);n2=(-v[1],v[0]);den=1+u[0]*v[0]+u[1]*v[1]
            m=((n1[0]+n2[0])/den,(n1[1]+n2[1])/den)
            valid=.8<point[0]<BOARD_SIZE_MM[0]-.8 and .8<point[1]<BOARD_SIZE_MM[1]-.8 and min(G.point_segment(point,c,d) for c,d in zip(guide,guide[1:]))<3.5
            if valid:
                for net,s in zip(names,(side,-side)):
                    rail=G.add(point,G.mul(m,SEP*s));pt=p.VECTOR2I(p.FromMM(rail[0]),p.FromMM(rail[1]))
                    if not reference_free(rail) or any(blocks(it,rail,net) for it in i.fx._items(layer,'',*rail,3)):
                        valid=False;break
            cache[key]=valid
        return cache[key]
    def transition_clear(q,h,m):
        key=(*q[:3],h)
        if key not in transition_cache:
            c=xy(q);z=xy(m);u=G.norm(dirs[q[2]]);v=G.norm(dirs[h]);n1=(-u[1],u[0]);n2=(-v[1],v[0]);den=1+u[0]*v[0]+u[1]*v[1]
            mit=((n1[0]+n2[0])/den,(n1[1]+n2[1])/den);good=True
            for net,s in zip(names,(side,-side)):
                points=[G.add(c,G.mul(n1,SEP*s)),G.add(c,G.mul(mit,SEP*s)),G.add(z,G.mul(n2,SEP*s))]
                for aa,zz in zip(points,points[1:]):
                    for rail in G.samples([aa,zz],.025):
                        pt=p.VECTOR2I(p.FromMM(rail[0]),p.FromMM(rail[1]))
                        if not reference_free(rail) or any(blocks(it,rail,net)for it in i.fx._items(layer,'',*rail,3)):
                            good=False;break
                    if not good:break
                if not good:break
            transition_cache[key]=good
        return transition_cache[key]
    if not free(start) or not free((*goal,gh,2)):
        print('USB search endpoint blocked',names,free(start),free((*goal,gh,2)),a,b,flush=True);return None
    remaining=[sum(math.dist(c,d) for c,d in zip(guide[k+1:],guide[k+2:])) for k in range(len(guide)-1)]
    hcache={}
    def heuristic(q):
        key=q[:2]
        if key not in hcache:
            point=xy(q);vals=[]
            for k,(c,d) in enumerate(zip(guide,guide[1:])):
                dd=math.dist(c,d);dist=G.point_segment(point,c,d);v=(d[0]-c[0],d[1]-c[1]);den=sum(x*x for x in v);t=max(0,min(1,sum((point[j]-c[j])*v[j] for j in (0,1))/den)) if den else 0
                vals.append((dist+.2*(1-t)*dd+.2*remaining[k],k,t))
            _,k,t=min(vals);hcache[key]=(G.point_segment(point,guide[k],guide[k+1])+(1-t)*math.dist(guide[k],guide[k+1])+remaining[k])/step
        return hcache[key]
    costs={start:0};prev={start:None};queue=[(1.5*heuristic(start),0,start)];count=0
    while queue and count<budget:
        _,cost,q=heapq.heappop(queue);count+=1
        if cost>costs.get(q,1e30):continue
        if q[:2]==goal and q[2]==gh and q[3]>=2:
            states=[]
            while q is not None:states.append(q);q=prev[q]
            points=[xy(s) for s in reversed(states)];points[0]=a
            points.extend([G.add(b,G.mul(bd,-.5)),b])
            out=[points[0]]
            for k in range(1,len(points)-1):
                d1=(points[k][0]-out[-1][0],points[k][1]-out[-1][1]);d2=(points[k+1][0]-points[k][0],points[k+1][1]-points[k][1])
                if abs(d1[0]*d2[1]-d1[1]*d2[0])>1e-8:out.append(points[k])
            out.append(b);print('USB centre found',names,count,len(out),flush=True);return out
        for h in ((q[2]-1)%8,q[2],(q[2]+1)%8) if q[3]>=2 else (q[2],):
            dx,dy=dirs[h];m=(q[0]+dx,q[1]+dy,h,min(4,q[3]+1) if h==q[2] else 1)
            if not free(q,q[2],h) or not free(m) or not free(((q[0]+m[0])/2,(q[1]+m[1])/2,h,2),h,h) or not transition_clear(q,h,m):continue
            nc=cost+math.hypot(dx,dy)+(.8 if h!=q[2] else 0)
            if nc<costs.get(m,1e30):costs[m]=nc;prev[m]=q;heapq.heappush(queue,(nc+1.6*heuristic(m),nc,m))
    print('USB centre exhausted',names,count,len(cache),'nearest', sorted((math.dist(xy(q),b),xy(q),q[2:]) for q in costs)[:3],flush=True);return None

def pair_from_spine(i,names,a,b,source_paths,target_paths,sa,sb,ad,bd,guide,layer='F',ground_at_target=True,source_tapers=None,fixed_spine=None,tune_negative_mm=0):
    ac=G.mul(G.add(source_paths[0][-1],source_paths[1][-1]),.5);normal=(-ad[1],ad[0]);side=1 if sum((source_paths[0][-1][k]-ac[k])*normal[k] for k in (0,1))>=0 else -1
    i.usb_search_guard=True
    signal.alarm(45)
    try:spine=fixed_spine or search(i,names,sa,sb,ad,G.mul(bd,-1),guide,p.F_Cu if layer=='F' else p.B_Cu,side=side,step=.1 if names[0]=='P4_DP' and layer=='B' else .2)
    except TimeoutError:spine=None;print('USB paired search time budget',names,flush=True)
    finally:i.usb_search_guard=False;signal.alarm(0)
    if spine is None:return False
    if names[0]=='P4_DP' and layer=='B' and math.dist(sa,(204,103.2))<.001:
        # Two independent local corrections: move the first short section
        # north; enlarge the final offset bend to remove its self-contact.
        # Both conductors retain equal geometric length change and full gap.
        changes={(202.6,106.0):(202.85,105.75),(202.2,106.0):(202.45,105.75),
                 (181.4,106.6):(181.7,106.9),(181.2,106.6):(181.2,106.9),(181.0,106.8):(181.0,107.1)}
        old=list(spine);matched=[]
        for index,point in enumerate(spine):
            key=tuple(round(v,4)for v in point)
            if key in changes:spine[index]=changes[key];matched.append(key)
        assert set(matched)==set(changes),'PWM source corner changed; re-review its local spacing repair'
        length=lambda pts:sum(math.dist(a,b)for a,b in zip(pts,pts[1:]))
        assert abs(length(spine)-length(old)+.3*math.sqrt(2))<1e-6,'PWM local paired cleanup changed the expected equal-leg length delta'
        i.evidence.append(dict(action='Bounded paired PWM B spacing and fold cleanup',before={str(k):k for k in changes},after={str(k):v for k,v in changes.items()},spacing_corner_shift_mm=(.25,-.25),equal_leg_length_delta_mm=-.3*math.sqrt(2),reason='North translation fixes P4/P2 remote spacing. Lengthening the final tiny straight from0.2to0.5mm removes the measured offset-bend fold while preserving0.300mm P/N gap. Native0.2mm unchanged; fresh independent saved-copper checks required.'))
    ac=G.mul(G.add(source_paths[0][-1],source_paths[1][-1]),.5);normal=(-ad[1],ad[0]);side=1 if sum((source_paths[0][-1][k]-ac[k])*normal[k] for k in (0,1))>=0 else -1
    paths=[]
    for idx,s in enumerate((side,-side)):
        rail=G.offset(spine,SEP*s)
        paths.append([source_paths[idx][-1],*(source_tapers[idx]if source_tapers else []),*rail,target_paths[idx][-1]])
    result=i.pair(names,a,b,ad,bd,[],layer=layer,source=source_paths,target=target_paths,
        source_global=True,main_layer=layer,main_paths=paths,
        create_source_vias=layer=='B',create_target_vias=layer=='B',ground_at_target=ground_at_target,tune_negative_mm=tune_negative_mm)
    if i.pairs:
        i.pairs[-1]['exact_reservation_sha256']=None;i.pairs[-1]['method']='v09 actual-rail guarded paired centreline'
    if not result:print('USB obstruction',i.pairs[-1].get('obstructions'),'vias',[(n,v,i.stitch(n,v,.4,.2,dry=True)) for n,path in zip(names,(source_paths+target_paths)) for v in [path[-1]]] if layer=='B' else [],flush=True)
    return result

def repair_pwm_debug_reference(i):
    # Keep the PWM USB pins/copper fixed. Move only the neighboring debug
    # handoff so both real GND reference and outside-package spacing survive.
    net='IO_PWM_SWDIO';old=(98.03,163.15);new=(98.5,162.7)
    found=[t for t in i.b.GetTracks() if t.GetClass()=='PCB_VIA' and t.GetNetname()==net and math.dist(p.ToMM(t.GetPosition()),old)<.001]
    assert len(found)==1,'Expected PWM SWDIO reference-via repair location'
    via=found[0];removed=[dict(uuid=via.m_Uuid.AsString(),kind='via',at_mm=old,diameter_mm=p.ToMM(via.GetWidth()),drill_mm=p.ToMM(via.GetDrillValue()))];i.remove(via)
    counts={p.F_Cu:0,p.B_Cu:0}
    for t in list(i.b.GetTracks()):
        if t.GetClass()!='PCB_TRACK' or t.GetNetname()!=net:continue
        a,b=p.ToMM(t.GetStart()),p.ToMM(t.GetEnd());ly=t.GetLayer()
        take=(ly==p.F_Cu and any(math.dist(q,(97.88,163.299999))<.001 for q in(a,b))) or (ly==p.B_Cu and any(math.dist(q,old)<.001 for q in(a,b)))
        if take:
            removed.append(dict(uuid=t.m_Uuid.AsString(),kind='track',layer=i.b.GetLayerName(ly),a_mm=a,b_mm=b,width_mm=p.ToMM(t.GetWidth())));counts[ly]+=1;i.remove(t)
    assert counts=={p.F_Cu:2,p.B_Cu:1},('Unexpected PWM debug fanout',counts)
    fp=[(97.3625,163.25),(97.6,163.25),(97.85,163.0),new];bp=[new,(98.03,163.9)]
    assert i.stitch(net,new,.4,.2),'Moved PWM SWDIO via obstructed'
    assert clear_leg(i,net,fp,p.F_Cu,.18) and clear_leg(i,net,bp,p.B_Cu,.18),'Moved PWM SWDIO leads obstructed'
    i.g.track(net,fp,.18,'F');i.g.track(net,bp,.18,'B');i.fx._index=None
    lower=[t for t in i.b.GetTracks() if t.GetClass()=='PCB_VIA' and t.GetNetname()==net and math.dist(p.ToMM(t.GetPosition()),(97.43,165.1))<.001]
    assert len(lower)==1,'Expected second PWM SWDIO handoff via'
    t=lower[0];lower_before=dict(uuid=t.m_Uuid.AsString(),diameter_mm=p.ToMM(t.GetWidth()),drill_mm=p.ToMM(t.GetDrillValue()));i.remove(t)
    assert i.stitch(net,(97.43,165.1),.4,.2),'Second PWM debug via resize obstructed'
    i.evidence.append(dict(action='Move PWM SWDIO handoff and resize second debug via to preserve actual USB reference and spacing',removed=removed,replacement=dict(via_mm=new,diameter_mm=.4,drill_mm=.2,F_path_mm=fp,B_path_mm=bp,width_mm=.18),second_via=dict(at_mm=(97.43,165.1),before=lower_before,after=dict(diameter_mm=.4,drill_mm=.2)),rationale='Only low-current debug copper changes. Existing factory/project0.4/0.2 ordinary-via process; native/all-layer/drill guards retained. Actual saved-copper spacing and reference require independent final verification; no package box expansion.'))

def repair_cc2_spacing(i):
    at=(214.1222,99.7696)
    found=[t for t in i.b.GetTracks() if t.GetClass()=='PCB_VIA' and t.GetNetname()=='USB_CC2' and math.dist(p.ToMM(t.GetPosition()),at)<.001]
    assert len(found)==1,'Expected USB CC2 spacing repair via'
    t=found[0];before=dict(uuid=t.m_Uuid.AsString(),diameter_mm=p.ToMM(t.GetWidth()),drill_mm=p.ToMM(t.GetDrillValue()));i.remove(t)
    assert i.stitch('USB_CC2',at,.4,.2),'USB CC2 via resize obstructed'
    i.evidence.append(dict(action='Resize one CC2 via to preserve outside-ESD USB spacing',at_mm=at,before=before,after=dict(diameter_mm=.4,drill_mm=.2),rationale='Position, connected leads and USB signal copper remain fixed.0.4/0.2 ordinary-via process; expected U11DP-pad gap0.7804mm independently checked on final copper.'))

def ensure_return_vias(i):
    """Verify actual GND-via copper at every installed paired F/B transfer."""
    groups={}
    for row in i.pairs:
        if not row.get('routed'):continue
        pp=row.get('paths',[])
        if len(pp)!=2:continue
        for a,b in zip(pp[0]['vias'],pp[1]['vias']):
            key=tuple(round(v,4)for q in(a,b)for v in q);groups[key]=(a,b)
    records=[]
    for a,b in groups.values():
        c=G.mul(G.add(a,b),.5)
        def nearby():
            return [t for t in i.b.GetTracks() if t.GetClass()=='PCB_VIA' and t.GetNetname()=='GND'
                    and max(math.dist(p.ToMM(t.GetPosition()),q)for q in(a,b))<=2.0]
        for dx,dy in [(1.3,0),(-1.3,0),(0,1.3),(0,-1.3),(1.05,.9),(1.05,-.9),(-1.05,.9),(-1.05,-.9)]:
            if len(nearby())>=2:break
            at=G.add(c,(dx,dy))
            if i.stitch('GND',at,.6,.3,dry=True):assert i.stitch('GND',at,.6,.3)
        # The dense U10 corner permits the already-qualified0.4/0.2mm
        # ordinary-via process, not a blind/small-via exception. Search only
        # the bounded2mm return neighborhood and recheck all copper/drills.
        if len(nearby())<2:
            options=[]
            for ix in range(-20,21):
                for iy in range(-20,21):
                    at=(round(c[0]+ix*.1,4),round(c[1]+iy*.1,4))
                    worst=max(math.dist(at,q)for q in(a,b))
                    if worst<=2.0 and min(math.dist(at,q)for q in(a,b))>=.7:options.append((worst,at))
            for _,at in sorted(options):
                if len(nearby())>=2:break
                if i.stitch('GND',at,.4,.2,dry=True):assert i.stitch('GND',at,.4,.2)
        actual=nearby()
        records.append(dict(signal_vias_mm=[a,b],centre_mm=c,complete=len(actual)>=1,
            target='Prefer two local GND vias; require an actual GND via within2.0mm of both signal vias, with saved-plane connectivity independently checked',
            ground_vias=[dict(uuid=t.m_Uuid.AsString(),at_mm=p.ToMM(t.GetPosition()),diameter_mm=p.ToMM(t.GetWidth()),drill_mm=p.ToMM(t.GetDrillValue()),distances_to_signal_vias_mm=[math.dist(p.ToMM(t.GetPosition()),q)for q in(a,b)])for t in actual]))
    i.evidence.append(dict(action='Actual local GND return vias at every paired F/B transfer',complete=all(r['complete']for r in records),transfers=records,
        plane_connectivity='Fresh saved-fill/native/independent ground-island audit remains mandatory; shared GND name alone is not proof'))
    return all(r['complete']for r in records)

def apply(i):
    if getattr(i,'usb_v09_applied',False):raise RuntimeError('USB helper requires a fresh composition, not duplicate routing')
    i.usb_v09_applied=True;G.W=W;G.GAP=GAP;install_spacing(i);repair_clock(i);repair_pwm_debug_reference(i);repair_cc2_spacing(i)
    host=tuple(i.landing('usb2','J9900',n) for n in NAMES[0]);hub=tuple(i.landing('usb2','J9901',n) for n in NAMES[1])
    # Reserve the actual short ESD launch on F before the hub chooses its
    # adjacent escape. Remove this reservation immediately before the host
    # pair commits the identical copper, so it cannot become a duplicate.
    reserve_ids={t.m_Uuid.AsString() for t in i.b.GetTracks()}
    host_source=[
        [i.pad('U11','1'),(212.9,101.05),(212.9,102.5),(213.30,104.1)],
        [i.pad('U11','3'),(214,102.95),(214.00,104.1)],
    ]
    for net,path in zip(NAMES[0],host_source):i.g.track(net,path,.18,'F')
    reserved=[t for t in i.b.GetTracks() if t.m_Uuid.AsString() not in reserve_ids];i.fx._index=None
    # Short, balanced package bridge crosses the independent host F launch.
    a=(i.pad('U10','15'),i.pad('U10','14'))
    source_p=[a[0],(212.35,102.25),(212.35,102.9)]
    source_n=[a[1],(211.65,102.75),(211.65,102.9)]
    station=((211.95,110.5),(211.25,110.5))
    first=pair_from_spine(i,NAMES[1],a,station,[source_p,source_n],[[q] for q in station],
        (212.5,104.7),(211.6,109.5),(0,1),(0,-1),[(212.5,104.7),(212.5,108),(211.6,109.5)],'B',ground_at_target=False,source_tapers=[[(212.7325,103.0),(212.7325,104.3)],[(212.2675,103.55)]])
    hc=G.mul(G.add(*hub),.5);goal=(hc[0]-.8,hc[1])
    if first:pair_from_spine(i,NAMES[1],station,hub,[[q] for q in station],[[q] for q in hub],
        (211.6,111.5),goal,(0,1),(-1,0),[(211.6,111.5),(214,115),(214,120),(205,120),(203,122),(194,122),(192,124),(180,124),(180,hc[1]),goal],'F')
    # Host exits the ESD on F, uses B with a dedicated L3 GND corridor, then
    # returns to the exact saved support-cell endpoint. No via-in-pad.
    a=(i.pad('U11','1'),i.pad('U11','3'))
    for t in reserved:i.remove(t)
    source=host_source
    hc=G.mul(G.add(*host),.5)
    target=[[host[0],(hc[0]+1.2,hc[1]-.4)],[host[1],(hc[0]+1.2,hc[1]+.4)]]
    sa=(213.6,105.1);sb=(hc[0]+2.2,hc[1])
    pair_from_spine(i,NAMES[0],a,host,source,target,sa,sb,(0,1),(1,0),
        [sa,(215,108),(221,110),(221,hc[1]-5.5),(215,hc[1]-3.5),(215,hc[1]),sb],'B',tune_negative_mm=1.699681)
    # Replace only the source IO cell's old P4 USB header necks. Their
    # staircase ordering needs a real layer crossover for this arrival.
    removed=[]
    for t in list(i.b.GetTracks()):
        if t.GetNetname() in NAMES[2] and not all(x<=103.138 and y>=163.7 for x,y in (p.ToMM(t.GetStart()),p.ToMM(t.GetEnd()))):
            removed.append(dict(uuid=t.m_Uuid.AsString(),net=t.GetNetname(),a=p.ToMM(t.GetStart()),b=p.ToMM(t.GetEnd()),layer=i.b.GetLayerName(t.GetLayer())))
            i.remove(t)
    i.evidence.append(dict(action='Replace IO P4 header neck only; preserve ESD flowthrough links and MCU legs',removed=removed))
    a=(i.pad('U10','6'),i.pad('U10','5'));b=(i.pad('U7009','6'),i.pad('U7009','4'))
    station=((181.35,109),(180.65,109))
    first=pair_from_spine(i,NAMES[2],a,station,
        [[a[0],(204.2,103.55)],[a[1],(204.2,102.85)]],[[station[0]],[station[1]]],
        (204,103.2),(181,108),(-1,0),(0,-1),
        [(204,103.2),(202,103.2),(202,107),(181,108)],'B',ground_at_target=False)
    # Leave the paired layer-transfer station toward north on F. The two
    # adjacent reference planes shield its short B/F turnaround. This facing
    # direction gives the correct physical P/N order at the MCU without a
    # logical polarity swap or a separate extra-via crossover.
    bridge_a=((170.15,116),(170.85,116));bridge_b=((170.15,126),(170.85,126))
    front=[(181,108),(181,106),(180,105),(172.5,105),(170.5,107),(170.5,115)]
    second=first and pair_from_spine(i,NAMES[2],station,bridge_a,[[q]for q in station],[[q]for q in bridge_a],
        (181,108),(170.5,115),(0,-1),(0,-1),front,'F',fixed_spine=front)
    third=second and pair_from_spine(i,NAMES[2],bridge_a,bridge_b,[[q]for q in bridge_a],[[q]for q in bridge_b],
        (170.5,117),(170.5,125),(0,1),(0,-1),[(170.5,117),(170.5,125)],'B',ground_at_target=False,
        fixed_spine=[(170.5,117),(170.5,125)])
    tail=[(170.5,127),(170.5,129),(167.5,132),(114,132),(112.5,133.5),(112.5,162.5),(110,165),(105,165)]
    if third:pair_from_spine(i,NAMES[2],bridge_b,b,[[q]for q in bridge_b],[[q]for q in b],
        (170.5,127),(105,165),(0,1),(1,0),tail,'F',fixed_spine=tail)
    returns_complete=ensure_return_vias(i)
    i.evidence.append(dict(action='v09 USB2 helper summary',local_return_vias_complete=returns_complete,helper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        pair_width_mm=W,pair_gap_mm=GAP,source='JLC041621-2116 1.6mm 4layer2oz outer90ohm factory nominal calculation',
        package_regions=[dict(reference=r['reference'],box_mm=r['box_mm'],nets=sorted(r['nets']),rationale=r.get('rationale','Bounded package escape')) for r in i.usb_regions],
        claims='Candidate routes only; fresh native DRC, whole-channel spacing/reference/skew and factory review remain mandatory'))
    return i.pairs

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('input',type=Path);parser.add_argument('--manifest',type=Path);parser.add_argument('--output',type=Path,default=Path('/tmp/usb-v09-route/kicad/robot_pdb.kicad_pcb'));args=parser.parse_args()
    import route_v09 as R
    R.K=args.output.parent;R.K.mkdir(parents=True,exist_ok=True)
    for file in args.input.parent.iterdir():
        dest=R.K/file.name
        if file.is_dir():shutil.copytree(file,dest,dirs_exist_ok=True)
        elif file.suffix in ('.kicad_pro','.kicad_sch') or file.name in ('fp-lib-table','sym-lib-table'):shutil.copyfile(file,dest)
    if args.manifest:shutil.copyfile(args.manifest,R.K.parent/'composition.json')
    i=R.Integration(args.input);i.output=args.output
    if args.manifest:i.landings=json.loads(args.manifest.read_text())['excluded_landings']
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('USB route budget')))
    signal.alarm(120)
    try:apply(i)
    except TimeoutError:print('USB route timed out; preserving diagnostic',flush=True)
    finally:signal.alarm(0)
    i.finish();print('USB candidate saved',args.output,flush=True)
