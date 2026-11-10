"""Small routed USB2 attachment/power support cell; no v07 source mutations."""
import os,sys,json,math,hashlib,shutil,faulthandler
faulthandler.enable()
from pathlib import Path
import pcbnew as p
import fixer
from indexed_fixer import IndexedFixer
from cells import Board
import usb2_control as circuit

ROOT=Path(__file__).resolve().parents[2]
K=ROOT/'revisions/usb2-control/kicad'; K.mkdir(parents=True,exist_ok=True)
CUSTOM=K/'Robot_PDB.pretty'; circuit.write_footprints(CUSTOM)
assert (CUSTOM/'Panasonic_POSCAP_D3L.kicad_mod').exists()
g=Board([]); b=g.b; g.parts={s['ref']:s for s in circuit.PARTS}
fixer.CLR=.225; fixer.VIA_D=.6; fixer.VIA_DR=.3
for s in circuit.PARTS:
    lib,name=s['fp'].split(':'); directory=CUSTOM if lib=='Robot_PDB' else Path(os.environ['KICAD7_FOOTPRINT_DIR'])/(lib+'.pretty')
    f=p.FootprintLoad(str(directory),name); assert f,(s['ref'],s['fp'])
    f.SetReference(s['ref']); f.SetValue(s['value']); f.SetFPID(p.LIB_ID(lib,name))
    f.Reference().SetLayer(p.F_Fab); f.Value().SetVisible(False)
    if s.get('dnp'):f.SetAttributes(f.GetAttributes()|p.FP_EXCLUDE_FROM_BOM|p.FP_EXCLUDE_FROM_POS_FILES)
    b.Add(f); g.fps[s['ref']]=f
    for q in f.Pads():
        if q.GetNumber() in s['pins']:q.SetNet(g.net(s['pins'][q.GetNumber()]))
positions={
 'U9902':(15,5.5,0),'J9901':(2,5,0),'J9900':(28,5.5,0),
 'C9905':(15,2.8,0),'R9906':(10,8.5,180),'R9907':(13,10.5,180),
 'U9903':(34,10,0),'C9906':(33.6375,7.2,0),'R9903':(38,8,0),'R9904':(28,9.5,0),
 'R9909':(38,10.5,0),'R9910':(40.5,14,0),'C9909':(36.2,12.7,0),
 'U9904':(7,17,0),'R9908':(10.7,17,0),'C9907':(10,20,0),'C9908':(4,14,0),
 'U9900':(22,17,0),'R9901':(26,17,0),'R9902':(29.5,17,0),
 'C9900':(18,13,0),'C9901':(17,20.5,0),'C9902':(27.5,24.2,0),'R9900':(21,22,90),
 'TP9900':(3,12,0),'TP9901':(3,23,0),'TP9902':(15,27,0),'TP9903':(31,27,0),
 'TP9904':(42,3,0),'TP9905':(19,27,0),'TP9906':(23,27,0),
 'TP9909':(42,8,0),'TP9910':(42,27,0),
}
assert set(positions)==set(g.fps),(set(g.fps)-set(positions))
for r,xy in positions.items():g.place(r,*xy)
g.outline(45,30)

PAIR_WIDTH=.165; PAIR_GAP=.300; d=(PAIR_WIDTH+PAIR_GAP)/2
routes=[]
def manual(net,pts,width=.2,layer='F',kind='local'):
    g.track(net,pts,width,layer);routes.append(dict(net=net,points=pts,width=width,layer=layer,kind=kind))
def via(net,x,y):g.via(net,x,y,d=.6,drill=.3)
for positive,negative,ports,pins,centre in [
    ('HUB_UP_DP','HUB_UP_DM','J9901',('1','2'),5),
    ('USB_DP','USB_DM','J9900',('8','7'),5.5),
]:
    for net,sgn,portpin,icpin in [(positive,-1,'1',pins[0]),(negative,1,'2',pins[1])]:
        a=g.pad(ports,portpin);z=g.pad('U9902',icpin)
        if ports=='J9901':pts=[a,(3,centre+sgn*d),(13.2,centre+sgn*d),z]
        else:pts=[z,(16.8,centre+sgn*d),(27,centre+sgn*d),a]
        manual(net,pts,PAIR_WIDTH,kind='USB2_coupled_no_signal_vias')
# Short fixed package escapes precede maze completion.
manual('H_V33',[g.pad('U9902','10'),(15,3.6),g.pad('C9905','1')])
manual('H_V33',[g.pad('C9905','1'),(13.1,2.8)]);via('H_V33',13.1,2.8)
manual('H_V33',[g.pad('R9904','2'),(28.825,8.3)]);via('H_V33',28.825,8.3)
manual('GND',[g.pad('U9902','5'),(15,7.6)]);via('GND',15,7.6)
manual('GND',[g.pad('U9902','9'),(17.2,4.75),(17.2,3.8)]);via('GND',17.2,3.8)
manual('USB2_UNUSED_DP',[g.pad('U9902','3'),(13.5,5.75),(13.5,7.2),g.pad('R9906','1')])
manual('USB2_UNUSED_DM',[g.pad('U9902','4'),(13.9,6.25),(13.9,9.5),g.pad('R9907','1')])
manual('USB2_ILIM',[g.pad('U9900','5'),g.pad('R9901','1')])

HS={'USB_DP','USB_DM','HUB_UP_DP','HUB_UP_DM'}
PACKAGE=(11.25,1.5,18.75,9.5)
def inbox(x,y):return PACKAGE[0]<=x<=PACKAGE[2] and PACKAGE[1]<=y<=PACKAGE[3]
def distance_point_segment(q,a,c):
    dx,dy=c[0]-a[0],c[1]-a[1]; t=max(0,min(1,((q[0]-a[0])*dx+(q[1]-a[1])*dy)/(dx*dx+dy*dy))) if dx or dy else 0
    z=(a[0]+t*dx,a[1]+t*dy);return math.dist(q,z),z
hs_segments=[]
for r in routes:
    if r['net']not in HS:continue
    for a,z in zip(r['points'],r['points'][1:]):
        cuts={0.,1.}
        for axis,edges in [(0,(PACKAGE[0],PACKAGE[2])),(1,(PACKAGE[1],PACKAGE[3]))]:
            if z[axis]!=a[axis]:
                for edge in edges:
                    t=(edge-a[axis])/(z[axis]-a[axis])
                    if 0<t<1:cuts.add(t)
        cuts=sorted(cuts)
        for lo,hi in zip(cuts,cuts[1:]):
            aa=tuple(a[k]+lo*(z[k]-a[k])for k in (0,1));zz=tuple(a[k]+hi*(z[k]-a[k])for k in (0,1))
            hs_segments.append((aa,zz,r['width'],inbox(*tuple((aa[k]+zz[k])/2 for k in (0,1)))))
class USBFixer(IndexedFixer):
    def via_ok(self,net,x,y):
        if not super().via_ok(net,x,y):return False
        at=p.VECTOR2I(p.FromMM(x),p.FromMM(y))
        # Standard process: no plated hole/copper land may overlap an SMD land,
        # including a same-net bypass or integration test pad.
        return not any(q.GetAttribute()==p.PAD_ATTRIB_SMD and q.HitTest(at,p.FromMM(.35))
                       for f in b.GetFootprints() for q in f.Pads())
    def free(self,layer,net,x,y,half):
        if not super().free(layer,net,x,y,half):return False
        if layer!=p.F_Cu or net in HS or net=='GND':return True
        for a,z,width,inside in hs_segments:
            gap,at=distance_point_segment((x,y),a,z)
            if inbox(x,y) and inside:continue
            if gap < half+width/2+.767:return False
        for f in b.GetFootprints():
            for q in f.Pads():
                if not q.IsOnLayer(p.F_Cu) or q.GetNetname() not in HS:continue
                bb=q.GetBoundingBox();xx=max(p.ToMM(bb.GetLeft()),min(x,p.ToMM(bb.GetRight()))); yy=max(p.ToMM(bb.GetTop()),min(y,p.ToMM(bb.GetBottom())))
                if inbox(x,y) and inbox(xx,yy):continue
                if math.hypot(x-xx,y-yy)<half+.767:return False
        return True
fx=USBFixer(b); attempts=[]
ok=fx.route('H_V33',(13.1,2.8),(28.825,8.3),w=.3,step=.075,win=4,layers=('B',))
attempts.append(dict(net='H_V33',a=(13.1,2.8),b=(28.825,8.3),width=.3,routed=bool(ok),kind='preseeded_local_bypass_feed_B'))
print('H_V33 BYPASS BACK FEED',ok,flush=True)
def route(net,a,z,w=.25):
    if any(r['net']==net and ((math.dist(a,r['points'][0])<1e-6 and math.dist(z,r['points'][-1])<1e-6)
                             or (math.dist(z,r['points'][0])<1e-6 and math.dist(a,r['points'][-1])<1e-6)) for r in routes):
        attempts.append(dict(net=net,a=a,b=z,width=w,routed=True,reused_manual=True));return True
    ok=fx.route(net,a,z,w=w,step=.075,win=7,layers=('F','B'))
    attempts.append(dict(net=net,a=a,b=z,width=w,routed=bool(ok))); print(net,a,z,ok,flush=True);return ok
def local_route(net,a,z,w=.25):
    # Short fixed local links still go through the collision-aware router.
    return route(net,a,z,w)

# Grounding is explicit at all IC/capacitor pads. Planes carry these stitches,
# while keeping the outer layers free of coplanar copper beside the USB pair.
for f in g.fps.values():
    for q in f.Pads():
        if q.GetNetname()!='GND':continue
        if f.GetReference()=='U9902' and q.GetNumber() in ('5','9'):continue
        ok=fx.gnd_via(q,w=.2,rmax=2.6);attempts.append(dict(net='GND',ref=f.GetReference(),pin=q.GetNumber(),routed=bool(ok)))
        print('GND',f.GetReference(),q.GetNumber(),ok,flush=True)

# MST completion connects every terminal, including off-board integration pads.
# Wide rail routes are selected before ordinary low-current controls.
nets=[]
for s in circuit.PARTS:
    for net in s['pins'].values():
        if net not in nets and net not in HS and net!='GND' and not net.endswith('_NC'):nets.append(net)
order=['USB_CONTROL_5V','USB2_LIMITED_5V','V5_USB_HUB','V5_USB','H_V33']
nets=order+[n for n in nets if n not in order]
for net in nets:
    pads=[q for f in g.fps.values() for q in f.Pads() if q.GetNetname()==net]
    if not pads:continue
    connected=[pads.pop(0)]
    def expand_connected():
        cn=b.GetConnectivity();cn.Build(b);todo=list(connected);seen=set();allpads=[]
        while todo:
            item=todo.pop();key=item.m_Uuid.AsString()
            if key in seen:continue
            seen.add(key)
            if isinstance(item,p.PAD):allpads.append(item)
            todo.extend(q for q in list(cn.GetConnectedPads(item))+list(cn.GetConnectedTracks(item))if q.GetNetname()==net)
        connected[:]=allpads
        pads[:]=[q for q in pads if q.m_Uuid.AsString()not in seen]
    expand_connected()
    while pads:
        _,i,a=min((math.dist(p.ToMM(q.GetPosition()),p.ToMM(c.GetPosition())),i,c)for i,q in enumerate(pads)for c in connected)
        z=pads.pop(i);w=.6 if net in order[:4] else (.3 if net=='H_V33' else .2)
        # Fine package lands use .2mm only at their own short escapes.
        if min(p.ToMM(a.GetSize().y),p.ToMM(z.GetSize().y))<.5:w=.2
        if route(net,p.ToMM(a.GetPosition()),p.ToMM(z.GetPosition()),w):
            connected.append(z);expand_connected()

print('ADDING PLANES',flush=True)
for layer in ('In1','In2'):g.zone('GND',layer,[(.5,.5),(44.5,.5),(44.5,29.5),(.5,29.5)],clearance=.25)
g.text('USB2 CONTROL',22.5,29,.7,p.F_Fab)
print('SAVING UNFILLED',flush=True)
out=K/'usb2_control.kicad_pcb';p.SaveBoard(str(out),b)
profile={'board':{'design_settings':{'rules':{'min_clearance':.2,'min_track_width':.16,'min_via_diameter':.6,'min_through_hole_diameter':.3,'min_via_annular_width':.1,'min_hole_clearance':.25,'min_hole_to_hole':.45},'rule_severities':{}}},'net_settings':{'classes':[{'name':'Default','clearance':.2,'track_width':.25,'via_diameter':.6,'via_drill':.3,'diff_pair_width':PAIR_WIDTH,'diff_pair_gap':PAIR_GAP,'diff_pair_via_gap':.3}]}}
(K/'usb2_control.kicad_pro').write_text(json.dumps(profile,indent=2)+'\n')
libraries=sorted({s['fp'].split(':')[0]for s in circuit.PARTS})
(K/'fp-lib-table').write_text('(fp_lib_table\n'+''.join(' (lib (name "'+lib+'")(type "KiCad")(uri "'+('${KIPRJMOD}/Robot_PDB.pretty'if lib=='Robot_PDB'else'${KICAD7_FOOTPRINT_DIR}/'+lib+'.pretty')+'")(options "")(descr ""))\n'for lib in libraries)+')\n')
length=lambda r:sum(math.dist(a,z)for a,z in zip(r['points'],r['points'][1:]))
pair_report=[]
for pn in [('HUB_UP_DP','HUB_UP_DM'),('USB_DP','USB_DM')]:
    rr=[next(r for r in routes if r['net']==net)for net in pn];ll=[length(r)for r in rr]
    pair_report.append(dict(nets=pn,copper_lengths_mm=ll,skew_mm=abs(ll[0]-ll[1]),signal_vias=0,width_mm=PAIR_WIDTH,gap_mm=PAIR_GAP,reference='F.Cu continuous In1.Cu GND'))
report={'status':'DEVELOPMENT_REQUIRES_FRESH_NATIVE_DRC','board':str(out.relative_to(ROOT)),'board_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'parts':len(circuit.PARTS),'ports':circuit.PORT_REFS,'positions':positions,'pair_routes':pair_report,'attempts':attempts,'manual_routes':routes,'package_breakout_exception_mm':PACKAGE,'inputs_sha256':{str(q.relative_to(ROOT)):hashlib.sha256(q.read_bytes()).hexdigest()for q in [Path(__file__),ROOT/'source/generator/usb2_control.py']}}
(K/'route-report.json').write_text(json.dumps(report,indent=2)+'\n')
print('SAVED',out,'failed attempts',sum(not a['routed']for a in attempts),flush=True)
