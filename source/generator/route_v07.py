"""Route v0.7 integration links without regenerating or editing source cells.

Run after build_v07.py through with_kicad.sh. This stage owns only the added
intercell copper and the placement of new9900 support parts. It preserves cell
switching/clock/SuperSpeed copper and records native results and reference
coverage. No current rating or fabrication release follows from connectivity.
"""
import argparse, hashlib, json, math, re, signal, subprocess, heapq
from pathlib import Path
import pcbnew as p
from cells import Board
from robot_io_router import RobotIOFixer
import fixer
from rev07 import PARTS,CELLS,INTEGRATION_PLACEMENTS

ROOT=Path(__file__).resolve().parents[2]
GENERATOR_SHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
CHILD_RESERVATION_PATH=Path(__file__).with_name('usb_child_arrival_reservation.json')
CHILD_RESERVATION_BYTES=CHILD_RESERVATION_PATH.read_bytes()
CHILD_RESERVATION=json.loads(CHILD_RESERVATION_BYTES)
CHILD_RESERVATION_SHA256=hashlib.sha256(CHILD_RESERVATION_BYTES).hexdigest()
PLACEMENTS_SHA256=hashlib.sha256(json.dumps(INTEGRATION_PLACEMENTS,sort_keys=True,separators=(',',':')).encode()).hexdigest()
K=ROOT/'revisions/v0.7/kicad'
W,GAP=.204,.160
PAIR_NAMES=[('P3_DP','P3_DM'),('P4_DP','P4_DM'),('HUB_CHILD_DP','HUB_CHILD_DM')]

def norm(a):
 l=math.hypot(*a);return (a[0]/l,a[1]/l)
def add(a,b):return (a[0]+b[0],a[1]+b[1])
def mul(a,x):return (a[0]*x,a[1]*x)
def offset(path,d):
 normals=[]
 for a,b in zip(path,path[1:]):
  if math.dist(a,b)<1e-8:return None
  u=norm((b[0]-a[0],b[1]-a[1]));normals.append((-u[1],u[0]))
 out=[]
 for i,a in enumerate(path):
  if i==0:n=normals[0]
  elif i==len(path)-1:n=normals[-1]
  else:
   q,r=normals[i-1],normals[i];den=1+q[0]*r[0]+q[1]*r[1]
   if den<.15:return None
   n=((q[0]+r[0])/den,(q[1]+r[1])/den)
  out.append(add(a,mul(n,d)))
 return out
def chamfer(path,d=2):
 path=[q for i,q in enumerate(path) if i==0 or math.dist(q,path[i-1])>1e-8]
 out=[path[0]]
 for a,c,z in zip(path,path[1:],path[2:]):
  u=norm((c[0]-a[0],c[1]-a[1]));v=norm((z[0]-c[0],z[1]-c[1]))
  if abs(u[0]*v[1]-u[1]*v[0])<1e-8:out.append(c);continue
  cut=min(d,math.dist(a,c)/3,math.dist(c,z)/3)
  out.extend((add(c,mul(u,-cut)),add(c,mul(v,cut))))
 out.append(path[-1]);return out
def point_segment(q,a,b):
 u=(b[0]-a[0],b[1]-a[1]);den=u[0]**2+u[1]**2
 t=max(0,min(1,((q[0]-a[0])*u[0]+(q[1]-a[1])*u[1])/den)) if den else 0
 return math.dist(q,add(a,mul(u,t)))
def segment_distance(a,b,c,d):
 cross=lambda x,y,z:(y[0]-x[0])*(z[1]-x[1])-(y[1]-x[1])*(z[0]-x[0])
 if cross(a,b,c)*cross(a,b,d)<0 and cross(c,d,a)*cross(c,d,b)<0:return 0
 return min(point_segment(q,u,v) for q,u,v in ((a,c,d),(b,c,d),(c,a,b),(d,a,b)))
def samples(path,step=.3):
 for a,b in zip(path,path[1:]):
  count=max(1,math.ceil(math.dist(a,b)/step))
  for k in range(count+1):yield (a[0]+(b[0]-a[0])*k/count,a[1]+(b[1]-a[1])*k/count)

class IntegrationFixer(RobotIOFixer):
 def free(self,layer,net,x,y,half):
  if not super().free(layer,net,x,y,half):return False
  # pcbnew.VIA.HitTest inflation is not a reliable radial-clearance check.
  # Keep an explicit5um margin over the actual0.200mm foreign-via rule.
  for item in self._items(layer,net,x,y,half+2.3):
   gap=self.integration.external_spacing(item,(x,y),.205,net) if hasattr(self,'integration') else .205
   if item.GetClass()=='PCB_VIA':
    if math.dist((x,y),p.ToMM(item.GetPosition()))<p.ToMM(item.GetWidth())/2+half+gap:return False
   elif gap>.21 and item.HitTest(p.VECTOR2I(p.FromMM(x),p.FromMM(y)),p.FromMM(half+gap)):return False
  return True

class Integration:
 def __init__(self,path):
  self.path=Path(path);self.output=K/'robot_pdb.kicad_pcb';self.b=p.LoadBoard(str(path));self.dead=[]
  self.g=Board.__new__(Board);self.g.b=self.b;self.g.nets={};self.g.zones=[]
  self.fps={f.GetReference():f for f in self.b.GetFootprints()};self.g.fps=self.fps
  expected={s['ref'] for s in PARTS}
  by={s['ref']:s for s in PARTS}
  for ref in expected-set(self.fps):
   if by[ref].get('source_cell')=='usb' or ref=='H9912':continue
   assert ref in ('R9905','C9904','H9910','H9911'),('Regenerate composition',ref)
   spec=by[ref];lib,name=spec['fp'].split(':');f=p.FootprintLoad(str(Path(__import__('os').environ['KICAD7_FOOTPRINT_DIR'])/(lib+'.pretty')),name);assert f
   self.b.Add(f);f.SetReference(ref);f.SetValue(spec['value']);f.SetFPID(p.LIB_ID(lib,name));f.Reference().SetLayer(p.F_Fab);f.Value().SetVisible(False);self.fps[ref]=f
   if spec.get('dnp'):f.SetAttributes(f.GetAttributes()|p.FP_EXCLUDE_FROM_BOM|p.FP_EXCLUDE_FROM_POS_FILES)
   for q in f.Pads():
    n=spec['pins'].get(q.GetNumber());q.SetNet(self.g.net(n)) if n else q.SetNetCode(0)
  for ref in ('U9900','R9905','C9904'):
   if ref in self.fps:
    for q in self.fps[ref].Pads():
     n=by[ref]['pins'].get(q.GetNumber());q.SetNet(self.g.net(n)) if n else q.SetNetCode(0)
  self.stale_usb_refs=sorted(expected-set(self.fps))
  assert all(by[r].get('source_cell')=='usb' or r=='H9912' for r in self.stale_usb_refs),('Regenerate composition before routing',self.stale_usb_refs)
  self.stale_usb_extra=sorted(set(self.fps)-expected)
  assert all(re.match(r'[A-Z]+95[0-9]+$',r) for r in self.stale_usb_extra),('Unexpected stale source references',self.stale_usb_extra)
  self.initial_ids={t.m_Uuid.AsString() for t in self.b.GetTracks()}
  self.original_copper={t.m_Uuid.AsString():{'net':t.GetNetname(),'layer':int(t.GetLayer()),'class':t.GetClass(),'from':tuple(p.ToMM(t.GetStart())),'to':tuple(p.ToMM(t.GetEnd())),'width_mm':p.ToMM(t.GetWidth()),'drill_mm':p.ToMM(t.GetDrillValue()) if t.GetClass()=='PCB_VIA' else None} for t in self.b.GetTracks()}
  self.zones=list(self.b.Zones())
  for z in self.zones:self.b.Remove(z)
  fixer.VIA_D=.4;fixer.VIA_DR=.2
  self.fx=IntegrationFixer(self.b);self.fx.integration=self;self.fx.via_ok=lambda net,x,y:self.stitch(net,(x,y),.4,.2,dry=True)
  self.evidence=[];self.pairs=[];self.power=[]
  self.settings=self.b.GetDesignSettings()  # Factory process floors come from the composition profile.
  self.source_hash=hashlib.sha256(self.path.read_bytes()).hexdigest()
 def external_spacing(self,item,q,ordinary=.205,ownnet=None):
  other=item.GetNetname();clean=other.removeprefix('USB3_').replace('_AC','').replace('_CONN','');ss=bool(re.fullmatch(r'(UP|CAM|MIC)_(TX|RX)[12]?[PN]',clean));hs={'HUB_CHILD_DP','HUB_CHILD_DM'}
  if ownnet=='GND' or other in ('GND','') or other.removeprefix('USB3_').startswith('NC_') or ownnet in hs and other in hs:return ordinary
  if not ss and ownnet not in hs and other not in hs:return ordinary
  if item.GetClass()=='PAD':
   bb=item.GetBoundingBox();near=(max(p.ToMM(bb.GetLeft()),min(q[0],p.ToMM(bb.GetRight()))),max(p.ToMM(bb.GetTop()),min(q[1],p.ToMM(bb.GetBottom()))))
  else:
   a,b=p.ToMM(item.GetStart()),p.ToMM(item.GetEnd());v=(b[0]-a[0],b[1]-a[1]);den=v[0]*v[0]+v[1]*v[1];t=max(0,min(1,((q[0]-a[0])*v[0]+(q[1]-a[1])*v[1])/den)) if den else 0;near=add(a,mul(v,t))
  #Explicit engineering exceptions: CH334 and USB5744 bodies+3mm.
  #Both copper points and both nets must belong to that physical package.
  for ref,half in (('U10',5),('U9500',6.5)):
   f=self.fps.get(ref)
   if not f:continue
   nets={z.GetNetname() for z in f.Pads()};cx,cy=p.ToMM(f.GetPosition());box=(cx-half,cy-half,cx+half,cy+half)
   if other in nets and (ownnet is None or ownnet in nets) and all(box[0]<=pt[0]<=box[2] and box[1]<=pt[1]<=box[3] for pt in (q,near)):return ordinary
  target=1.275 if other in ('H_XI','H_XO','USB3_HUB_XI','USB3_HUB_XO') or ownnet in ('H_XI','H_XO','USB3_HUB_XI','USB3_HUB_XO') else .767
  return max(ordinary,target) #5um beyond TI's.762/1.270mm recommendation.
 def pad(self,r,n):return self.g.pad(r,str(n))
 def remove(self,item):self.dead.append(item);self.b.Remove(item);self.fx._index=None
 def place_support(self):
  positions=INTEGRATION_PLACEMENTS
  for r,xyz in positions.items():
   if r in self.fps:self.g.place(r,*xyz)
  self.fx._index=None
  # Root-authorized removal: these two unanchored original GND stitch vias
  # conflict with the new Micro-Fit locating peg. Future compositions omit them.
  peg_vias=[]
  for t in list(self.b.GetTracks()):
   if t.GetClass()=='PCB_VIA' and t.GetNetname()=='GND' and any(math.dist(p.ToMM(t.GetPosition()),q)<.001 for q in ((51.2,84),(52.8,84))):
    assert not list(self.b.GetConnectivity().GetConnectedTracks(t)),('Peg via unexpectedly anchors a track',t.m_Uuid.AsString())
    peg_vias.append(t.m_Uuid.AsString());self.remove(t)
  if peg_vias:self.evidence.append({'action':'root-authorized Micro-Fit peg clearance','removed_unanchored_GND_vias':peg_vias})
  # Remove only the former self-power strap's direct physical contact/stub.
  # PSELF itself must remain an isolated NC pad; unrelated ground is retained.
  pad=next(q for q in self.fps['U10'].Pads() if q.GetNumber()=='18');xy=p.ToMM(pad.GetPosition())
  removed=[]
  for t in list(self.b.GetTracks()):
   if t.GetNetname()!='GND':continue
   if t.GetClass()=='PCB_TRACK' and point_segment(xy,p.ToMM(t.GetStart()),p.ToMM(t.GetEnd()))<.5:
    removed.append(t.m_Uuid.AsString());self.remove(t)
  for t in list(self.b.GetTracks()):
   if t.GetClass()=='PCB_VIA' and t.GetNetname()=='GND' and math.dist(p.ToMM(t.GetPosition()),xy)<2:
    # Only isolated strap vias are removed; ground EP/stitch vias retain their
    # existing track connections and their reference-return function.
    if point_segment(p.ToMM(t.GetPosition()),xy,(xy[0]+1.5,xy[1]))<.25:self.remove(t)
  self.evidence.append({'action':'remove former PSELF ground strap','removed_tracks':removed})
 def base_xy(self,q):
  # Original base-cell landmarks are expressed in its native coordinate frame.
  dy=self.pad('U10','21')[1]-80.0625
  return (q[0],q[1]+dy)
 def repair_hub_fanout(self):
  # Audited localized changes: remove the old LED fanout; keep the crystal
  # branch short but move its first bend above the new port4 escape. Move the
  # local VBUS back-layer dogleg away from the EEPROM SDA via. P1/P2 untouched.
  changed=[]
  for t in list(self.b.GetTracks()):
   n=t.GetNetname();a,b=p.ToMM(t.GetStart()),p.ToMM(t.GetEnd())
   dy=self.pad('U10','21')[1]-80.0625
   local=lambda q:(q[0],q[1]-dy)
   if n in ('H_LED','H_XI') or (n=='V5_USB' and t.GetClass()=='PCB_TRACK' and t.GetLayer()==p.B_Cu and all(207<x<209 and 78<y<81 for x,y in (local(a),local(b)))):
    changed.append({'uuid':t.m_Uuid.AsString(),'net':n,'from':a,'to':b});self.remove(t)
   elif n=='V5_USB' and t.GetClass()=='PCB_VIA' and math.dist(local(a),(207.625,78.7))<.01:
    changed.append({'uuid':t.m_Uuid.AsString(),'net':n,'action':'resize via to0.4/0.2mm'});t.SetWidth(p.FromMM(.4));t.SetDrill(p.FromMM(.2));self.fx._index=None
  paths=[('H_LED',[(206.75,80.0625),(206.75,78.8)],'F'),
   ('H_LED',[(206.75,78.8),(213.24,72)],'B'),('H_LED',[(213.24,72),(212.2875,72)],'F'),
   ('H_XI',[(205.0625,82.25),(203.8,82.25),(203.4,82.6),(202.85,82.6)],'F'),
   ('V5_USB',[(208.424999,80),(208.424999,78.7),(207.625,78.7)],'B')]
  for n,path,ly in paths:
   pts=[self.base_xy(q) for q in path];layer=p.F_Cu if ly=='F' else p.B_Cu
   assert all(self.fx.free(layer,n,*q,.1) for q in samples(pts,.025)),('hub fanout clearance',n,path)
   self.g.track(n,pts,.18 if n=='H_LED' else .2,ly);self.fx._index=None
  for q in ((206.75,78.8),(213.24,72)):
   xy=self.base_xy(q);assert self.stitch('H_LED',xy,.4,.2),('LED via',q)
  self.evidence.append({'action':'authorized CH334F local fanout repair','altered_original_copper':changed,'verification_links':['U10.22→D60.1 H_LED','U10.4→Y1.1 H_XI','U10.19→C62.1 V5_USB']})
 def control_bridge(self,net,a,b):
  bridge=(154,158)
  if not self.stitch(net,bridge,.4,.2,dry=True):return False
  before={t.m_Uuid.AsString() for t in self.b.GetTracks()};ok=True
  for aa,bb,ly in ((a,bridge,'F'),(bridge,b,'B')):
   signal.alarm(20)
   try:part=self.fx.route(net,aa,bb,w=.18,step=.15,win=8,layers=(ly,))
   except TimeoutError:part=False
   finally:signal.alarm(0)
   if not part:ok=False;break
  if ok:
   assert self.stitch(net,bridge,.4,.2);self.evidence.append({'net':net,'from':a,'to':b,'routed':True,'method':'fault control F service-strip crossing and B approach','bridge':bridge,'width':.18});return True
  for t in list(self.b.GetTracks()):
   if t.m_Uuid.AsString() not in before:self.remove(t)
  return False
 def stitch(self,net,xy,d=.6,drill=.3,dry=False):
  # Spatial candidates include same-net holes too; manufacturing drill gaps
  # apply even when their copper belongs to the same electrical net.
  nearby=self.fx._items(p.F_Cu,'',*xy,2.5)
  for t in nearby:
   if t.GetClass()=='PCB_VIA':
    distance=math.dist(xy,p.ToMM(t.GetPosition()))
    if distance<(drill+p.ToMM(t.GetDrillValue()))/2+.46:return False
    if t.GetNetname()!=net and distance<(d+p.ToMM(t.GetWidth()))/2+.21:return False
   elif t.GetClass()=='PAD':
    hole=max(p.ToMM(t.GetDrillSize()))
    if hole and math.dist(xy,p.ToMM(t.GetPosition()))<(drill+hole)/2+.46:return False
    if not hole and t.GetAttribute()==p.PAD_ATTRIB_SMD and t.GetNetname()==net and t.HitTest(p.VECTOR2I(p.FromMM(xy[0]),p.FromMM(xy[1])),p.FromMM(drill/2+.10)):return False
  if all(self.fx.free(layer,net,*xy,d/2) for layer in (p.F_Cu,p.In1_Cu,p.In2_Cu,p.B_Cu)):
   if not dry:self.g.via(net,*xy,d,drill);self.fx._index=None
   return True
  return False
 def route(self,net,a,b,w=.25,win=6,step=.15,layers=('F','B')):
  def clear(path,ly):return all(self.fx.free(ly,net,*q,w/2) for q in samples(path,.15))
  alternatives=[[a,b],[a,(a[0],b[1]),b],[a,(b[0],a[1]),b]]
  for path in alternatives:
   path=[q for i,q in enumerate(path) if i==0 or math.dist(q,path[i-1])>.0001]
   if clear(path,p.F_Cu):
    self.g.track(net,path,w,'F');self.fx._index=None
    self.evidence.append({'net':net,'from':a,'to':b,'width':w,'routed':True,'method':'checked F service corridor'});return True
  def b_contact(q):
   if any(t.GetClass()=='PCB_VIA' and t.GetNetname()==net and math.dist(p.ToMM(t.GetPosition()),q)<.001 for t in self.b.GetTracks()):return True
   return any(pad.GetNetname()==net and pad.GetDrillSize().x>0 and math.dist(p.ToMM(pad.GetPosition()),q)<.001 for fp in self.b.GetFootprints() for pad in fp.Pads())
  def escape(q):
   if b_contact(q):return q
   for d in (.7,.9,1.3,1.8):
    for dx,dy in ((d,0),(-d,0),(0,d),(0,-d)):
     v=add(q,(dx,dy))
     if clear([q,v],p.F_Cu) and self.stitch(net,v,.4,.2,dry=True):return v
   return None
  va,vb=escape(a),escape(b)
  if net in ('CHILD_EE_SCL','CHILD_EE_SDA'):print('EEPROM escapes',net,va,vb,flush=True)
  if va and vb:
   paths=[[va,vb],[va,(va[0],vb[1]),vb],[va,(vb[0],va[1]),vb]]
   for shift in (2,-2,5,-5,10,-10):paths.append([va,(va[0]+shift,va[1]),(va[0]+shift,vb[1]),vb])
   for path in paths:
    path=[q for i,q in enumerate(path) if i==0 or math.dist(q,path[i-1])>.0001]
    if clear(path,p.B_Cu):
     self.g.track(net,[a,va],w,'F');self.g.track(net,path,w,'B');self.g.track(net,[vb,b],w,'F')
     for q in (va,vb):
      if not b_contact(q):assert self.stitch(net,q,.4,.2)
     self.fx._index=None
     self.evidence.append({'net':net,'from':a,'to':b,'width':w,'routed':True,'method':'checked B service corridor'});return True
   signal.alarm(20)
   try:ok=self.fx.route(net,va,vb,w=w,step=max(step,.22),win=win,layers=('B',))
   except TimeoutError:ok=False
   finally:signal.alarm(0)
   if ok:
    self.g.track(net,[a,va],w,'F');self.g.track(net,[vb,b],w,'F')
    for q in (va,vb):
     if not b_contact(q):assert self.stitch(net,q,.4,.2)
    self.fx._index=None;self.evidence.append({'net':net,'from':a,'to':b,'routed':True,'method':'B maze from exact escape vias'});return True
  signal.alarm(20)
  try:ok=self.fx.route(net,a,b,w=w,step=step,win=win,layers=layers)
  except TimeoutError:ok=False
  finally:signal.alarm(0)
  self.evidence.append({'net':net,'from':a,'to':b,'width':w,'routed':bool(ok)})
  print('local',net,a,b,ok,flush=True);return ok
 def child_power_wire(self,net,a,b):
  if net=='CHILD_LIMITED_5V':path=[a,(246,a[1]),(246,148),(210,148),(210,b[1]),b]
  else:path=[a,(214,110.5),(214,124),(b[0],124),b]
  before={t.m_Uuid.AsString() for t in self.b.GetTracks()};ok=True
  for aa,bb in zip(path,path[1:]):
   if all(self.fx.free(p.F_Cu,net,*q,.15) for q in samples([aa,bb],.05)):
    self.g.track(net,[aa,bb],.3,'F');self.fx._index=None;continue
   signal.alarm(12)
   try:part=self.fx.route(net,aa,bb,w=.3,step=.1,win=3,layers=('F',))
   except TimeoutError:part=False
   finally:signal.alarm(0)
   if not part:ok=False;break
  if ok:
   self.evidence.append({'net':net,'from':a,'to':b,'routed':True,'method':'explicit F child-logic power path','width':.3,'path':path,'current_design_target_A':.55});return True
  for t in list(self.b.GetTracks()):
   if t.m_Uuid.AsString() not in before:self.remove(t)
  return False
 def eeprom_bridge(self,net,a,b):
  candidates=[(211,106),(211.5,106)] if net=='CHILD_EE_SCL' else [(212,107.5),(212.5,107.5)]
  for bridge in candidates:
   if not self.stitch(net,bridge,.4,.2,dry=True):continue
   before={t.m_Uuid.AsString() for t in self.b.GetTracks()};ok=True
   for aa,bb,ly in ((a,bridge,'B'),(bridge,b,'F')):
    signal.alarm(15)
    try:part=self.fx.route(net,aa,bb,w=.18,step=.1,win=8 if ly=='F' else 4,layers=(ly,))
    except TimeoutError:part=False
    finally:signal.alarm(0)
    if not part:ok=False;break
   if ok:
    assert self.stitch(net,bridge,.4,.2);self.evidence.append({'net':net,'from':a,'to':b,'routed':True,'method':'explicit EEPROM B-to-F bridge','bridge':bridge,'width':.18});return True
   for t in list(self.b.GetTracks()):
    if t.m_Uuid.AsString() not in before:self.remove(t)
  return False
 def local_support(self):
  # New local logic and optional EEPROM. Never complete USB3 cell-local nets.
  fine={}
  for r,n,raw,d,drill in [('U10','21',(207.25,79.35),.4,.2),('U10','13',(209.55,83.4),.35,.15)]:
   a=self.pad(r,n);q=self.base_xy(raw);net=next(x for x in self.fps[r].Pads() if x.GetNumber()==n).GetNetname()
   assert all(self.fx.free(p.F_Cu,net,*x,.09) for x in samples([a,q],.025)),('fine neck',r,n)
   assert self.stitch(net,q,d,drill),('fine via',r,n)
   self.g.track(net,[a,q],.18);self.fx._index=None;fine[(r,n)]=q
   self.evidence.append({'action':'bounded EEPROM package escape','reference':r,'pin':n,'via':q,'via_diameter_mm':d,'drill_mm':drill,'neck_width_mm':.18,'drill_to_SMD_pad_margin_mm':.10})
  for r,n,direction in [('U9500','36',(-1,0))]:
   pad=next(q for q in self.fps[r].Pads() if q.GetNumber()==n);net=pad.GetNetname();a=p.ToMM(pad.GetPosition())
   for distance in (1.4,1.8,2.2,2.8,3.4):
    q=add(a,mul(direction,distance))
    clear=all(not any(it.HitTest(p.VECTOR2I(p.FromMM(x),p.FromMM(y)),p.FromMM(.09+.20)) for it in self.fx._items(p.F_Cu,net,x,y,2)) for x,y in samples([a,q],.05))
    if clear and self.stitch(net,q,.4,.2,dry=True):
     self.g.track(net,[a,q],.18);assert self.stitch(net,q,.4,.2);self.fx._index=None;fine[(r,n)]=q;break
   self.evidence.append({'action':'fine pitch escape','reference':r,'pin':n,'success':(r,n) in fine})
  def endpoint(r,n):return fine.get((r,n),self.pad(r,n))
  links=[('CHILD_ILIM','U9900','5','R9901','1'),('CHILD_ILIM_MID','R9901','2','R9902','1'),
   ('CHILD_LIMITED_5V','U9900','6','FB1','1'),('V5_USB','FB1','2','C9902','1'),
   ('H_V33','C63','1','U9901','8'),('H_V33','U9901','8','U9901','7'),('H_V33','U9901','8','C9903','1'),
   ('CHILD_EE_SCL','U10','13','U9901','6'),('CHILD_EE_SDA','U10','21','U9901','5'),
   ('CHILD_PRT_CTL','U9900','4','U9500','36')]
  if 'R9905' in self.fps:
   links.extend([('CHILD_PRT_CTL','U9900','4','R9905','1'),('CHILD_SWITCH_EN','R9905','2','U9900','3'),('CHILD_SWITCH_EN','U9900','3','C9904','1')])
  else:links.append(('CHILD_PRT_CTL','U9900','3','U9900','4'))
  priority={'CHILD_EE_SCL':0,'CHILD_EE_SDA':1,'H_V33':2,'CHILD_PRT_CTL':3,'CHILD_SWITCH_EN':3,'CHILD_ILIM':4,'CHILD_ILIM_MID':4,'CHILD_LIMITED_5V':5,'V5_USB':5}
  links.sort(key=lambda item:priority[item[0]])
  for n,r,a,s,c in links:
   if r in self.fps and s in self.fps:
    for rr,pp in ((r,a),(s,c)):
     assert next(q for q in self.fps[rr].Pads() if q.GetNumber()==pp).GetNetname()==n,(rr,pp,n)
   if r in self.fps and s in self.fps:
    if n in ('CHILD_EE_SCL','CHILD_EE_SDA') and self.eeprom_bridge(n,endpoint(r,a),endpoint(s,c)):continue
    if n=='CHILD_PRT_CTL' and s=='U9500' and self.control_bridge(n,endpoint(r,a),endpoint(s,c)):continue
    self.route(n,endpoint(r,a),endpoint(s,c),.3 if n in ('V5_USB','CHILD_LIMITED_5V') else .25,8,.18)
  #A deliberately tented.4/.2 GND via under the SOT23 body avoids the
  #crowded outside pin2 escape. It is not in an SMD copper/paste pad.
  ground_pad=self.pad('U9900','2');ground_via=p.ToMM(self.fps['U9900'].GetPosition())
  assert self.stitch('GND',ground_via,.4,.2),('U9900 dedicated GND via',ground_via)
  ground_via_item=next(t for t in self.b.GetTracks() if t.GetClass()=='PCB_VIA' and t.GetNetname()=='GND' and math.dist(p.ToMM(t.GetPosition()),ground_via)<1e-5);assert ground_via_item.IsTented(),'Under-body ground via must remain tented'
  assert all(self.fx.free(p.F_Cu,'GND',*q,.15) for q in samples([ground_pad,ground_via],.025)),'U9900 GND stub blocked'
  self.g.track('GND',[ground_pad,ground_via],.3,'F');self.fx._index=None
  self.evidence.append({'action':'Explicit U9900 pin2 GND plane landing','from':ground_pad,'via':ground_via,'track_width_mm':.3,'via_diameter_mm':.4,'drill_mm':.2,'via_is_in_pad':False,'via_tented':ground_via_item.IsTented()})
  for ref in ('U9901','C9900','C9901','C9902','C9903','R9902','C9904'):
   if ref not in self.fps:continue
   for q in self.fps[ref].Pads():
    if q.GetNetname()!='GND':continue
    xy=p.ToMM(q.GetPosition())
    for d in (.9,1.2,1.6):
     if any(self.stitch('GND',add(xy,z)) and self.route('GND',xy,add(xy,z),.3) for z in ((d,0),(-d,0),(0,d),(0,-d))):break
 def power_spine(self,net,path,width,description,layers=('F','B')):
  path=chamfer(path,2)
  # Boolean-union the segment rectangles before creating ONE zone. Separate
  # overlapping zones without a pad can be removed as islands independently.
  combined=p.SHAPE_POLY_SET()
  for a,b in zip(path,path[1:]):
   tangent=norm((b[0]-a[0],b[1]-a[1]));normal=(-tangent[1],tangent[0]);aa=add(a,mul(tangent,-width/2));bb=add(b,mul(tangent,width/2))
   poly=[add(aa,mul(normal,width/2)),add(bb,mul(normal,width/2)),add(bb,mul(normal,-width/2)),add(aa,mul(normal,-width/2))]
   rect=p.SHAPE_POLY_SET();rect.NewOutline()
   for x,y in poly:rect.Append(p.FromMM(x),p.FromMM(y))
   combined.BooleanAdd(rect,p.SHAPE_POLY_SET.PM_STRICTLY_SIMPLE)
  assert combined.OutlineCount()==1,('Power union is disconnected',net)
  outline=combined.COutline(0);poly=[p.ToMM(outline.CPoint(i)) for i in range(outline.PointCount())]
  for layer in layers:self.g.zone(net,layer,poly,1,.5,minw=.5)
  count=0
  candidates=samples(path,3) if len(layers)>1 else (path[0],path[-1])
  for q in candidates:
   if self.stitch(net,q,.8,.4):count+=1
  self.power.append({'net':net,'centreline':path,'nominal_width_mm_per_outer_layer':width,'parallel_outer_layers':len(layers),'layers':list(layers),'stitch_vias':count,'description':description,'current_rating':'unqualified; native connectivity is not a thermal/fuse-coordination rating'})
 def power_links(self):
  # Fused-source coordination: both5A fuse inputs remain behind the30A logic
  # fuse. Extend the broad original VIN plane directly into their service strip.
  self.g.zone('VIN','In2',[(35,124),(210,124),(210,145),(35,145)],2,.5,minw=.6)
  self.power_spine('MOTOR_FUSED_INPUT',[self.pad('F1','1'),(14,4),(32,4),self.pad('Q9910','2')],4,'Short15A-fused motor feed into new hardware reverse-blocking stage')
  for layer in ('F','B'):self.g.zone('MOTOR_FUSED_INPUT',layer,[(30.8,2),(38,2),(38,8),(30.8,8)],10,.3,minw=.5)
  self.power_spine('MOTOR_VIN',[self.pad('Q9910','5'),(42,15),(240,15),self.pad('C6014','1')],8,'Protected motor top-edge bus, nominal10A operating-design target; bench qualification required')
  self.power_spine('PWM_VIN',[self.pad('F7000','2'),(130,147),(7.5,147),(7.5,196)],4,'5A-fused PWM converter input landing on its existing L3 input plane',layers=('F',))
  self.power_spine('VIN',[(220,121),self.pad('F8000','1')],8,'Broad pre-fuse VIN feed into vertically mounted USB input fuse; source30A coordination remains qualification',layers=('F','B'))
  self.g.zone('VIN','F',[(219,118.8),(227.4,118.8),(227.4,123.2),(219,123.2)],1,.4,minw=.5)
  self.g.zone('VIN','B',[(219,118.8),(227.4,118.8),(227.4,123.2),(219,123.2)],1,.4,minw=.5)
  bank=0
  for x in (220.9,222.1,223.3,224.5,225.7,226.9):
   for y in (119.8,121,122.2):
    if self.stitch('VIN',(x,y),.8,.4):bank+=1
  total_bank=sum(t.GetClass()=='PCB_VIA' and t.GetNetname()=='VIN' and 219<=p.ToMM(t.GetPosition())[0]<=227.4 and 118.8<=p.ToMM(t.GetPosition())[1]<=123.2 for t in self.b.GetTracks())
  self.evidence.append({'action':'USB fuse pre-feed VIN layer-transfer bank','added_vias':bank,'total_vias':total_bank,'design_target_minimum':8,'qualified_source_fuse_coordination':False})
  self.power_spine('USB_POWER_VIN',[self.pad('F8000','2'),self.pad('C8014','1')],4,'5A-fused USB converter input direct in right service gap',layers=('F','B'))
  raw_target=self.pad('C9546','1')
  self.power_spine('+5_USB_RAW',[self.pad('L8001','2'),(265,217.8),(250,235),raw_target],8,'USB output trunk;8A target remains converter/copper/connector thermal qualification',layers=('B',))
  # Eight or more legal plated vias carry the camera-input handoff from the
  # broad B rail to the F bulk pad; one nominal endpoint via is insufficient.
  x,y=raw_target;self.g.zone('+5_USB_RAW','F',[(x-3.2,y-2.5),(x+1.8,y-2.5),(x+1.8,y+2.5),(x-3.2,y+2.5)],1,.3,minw=.5)
  added=0
  for dx in (-2.4,-1.2,0,1.2):
   for dy in (-1.8,-.6,.6,1.8):
    if self.stitch('+5_USB_RAW',(x+dx,y+dy),.8,.4):added+=1
  existing=[t.m_Uuid.AsString() for t in self.b.GetTracks() if t.GetClass()=='PCB_VIA' and t.GetNetname()=='+5_USB_RAW' and abs(p.ToMM(t.GetPosition())[0]-x)<3.3 and abs(p.ToMM(t.GetPosition())[1]-y)<2.6]
  self.evidence.append({'action':'USB8A-design-target bulk handoff via bank','at':raw_target,'added_vias':added,'total_legal_vias':len(existing),'via_uuids':existing,'minimum_design_target':8,'qualified_current_rating':False})
  handoff=next(q for q in ((245.2,138.8),(245.2,137.8),(246.2,138.8),(244.5,138.8)) if self.stitch('+5_USB_RAW',q,.8,.4,dry=True))
  self.power_spine('+5_USB_RAW',[(265,217.8),(260,205),(260,132),(handoff[0],132),handoff],3,'Child-hub limiter input tap, routed on the right of its output conductor',layers=('B',))
  # A deliberate F handoff crosses the one B control-power conductor; its
  # short feed then reaches the current limiter without drilling an SMD pad.
  self.g.zone('+5_USB_RAW','F',[(237.5,131.5),(247.0,131.5),(247.0,139.5),(237.5,139.5)],2,.3,minw=.4)
  # The filled F landing provides this connection; no redundant narrow
  # trace is needed through the current-limiter output fanout.
  for r in ('C9900','C9901'):self.route('+5_USB_RAW',self.pad(r,'1'),self.pad('U9900','1'),.3)
  for x in (75,101):self.g.zone('V5_USB','F',[(x-.85,183.15),(x+.85,183.15),(x+.85,184.85),(x-.85,184.85)],3,.2,minw=.25)
  vbus_path=[self.pad('C9902','1'),(248.95,130.5),(225,130.5),(225,136),(110,136)]
  self.power_spine('V5_USB',vbus_path,1.2,'Current-limited0.55A-target downstream VBUS main distribution on F; local B branches cross the PWM feed; no host VBUS connection',layers=('F',))
  #Bridge the limited-input F trace and P4 F pair on B; F crosses the HS B pair.
  #These two local transitions avoid alternating disconnected plane islands.
  vbus_tracks=[('F',[self.pad('C9902','1'),(248.95,130.5),(237,130.5)]),('B',[(237,130.5),(229,130.5)]),('F',[(229,130.5),(225,130.5),(225,136)]),('B',[(225,136),(217.5,136)]),('F',[(217.5,136),(110,136)])]
  for ly,path in vbus_tracks:
   assert all(self.fx.free(p.F_Cu if ly=='F' else p.B_Cu,'V5_USB',*q,.6) for q in samples(path,.05)),('Dedicated1.2mm VBUS spine obstruction',ly,path)
   self.g.track('V5_USB',path,1.2,ly);self.fx._index=None
  for q in ((237,130.5),(229,130.5),(225,136),(217.5,136)):assert self.stitch('V5_USB',q,.8,.4),('VBUS bridge via',q)
  self.power[-1]['explicit_track_segments']=[{'layer':ly,'path':path,'width_mm':1.2} for ly,path in vbus_tracks]
  self.power[-1]['bridge_note']='Filled F pour crosses other F conductors; four vias and two short B track bridges make the actual0.55A-target spine continuous. Zone-only cross sections at the bridges are intentionally incomplete.'
  for x,cap in ((103.225,'C7021'),(75.225,'C7001')):
   self.power_spine('V5_USB',[(110,136),(x,136),(x,150.5)],1.2,'B feed crosses F PWM input branch; transfer below that branch and above USB2 B lanes',layers=('B',))
   self.power_spine('V5_USB',[(x,150.5),self.pad(cap,'1')],1.2,'F feed crosses USB2 B lanes into the logic input capacitor',layers=('F',))
 def pair_spine(self,names,a,b,ad,bd,guide,layer=p.B_Cu):
  # Direction-constrained shared centreline. The guide reserves pair ordering;
  # both conductors are offset from this one path and committed atomically.
  step=.25;approach=.5;dest=add(b,mul(bd,approach));dirs=((1,0),(1,1),(0,1),(-1,1),(-1,0),(-1,-1),(0,-1),(1,-1))
  hd=lambda d:max(range(8),key=lambda i:(d[0]*dirs[i][0]+d[1]*dirs[i][1])/math.hypot(*dirs[i]))
  x0=min(x for x,y in guide)-4;y0=min(y for x,y in guide)-4
  x0=a[0]-math.ceil((a[0]-x0)/step)*step;y0=a[1]-math.ceil((a[1]-y0)/step)*step
  xy=lambda q:(x0+q[0]*step,y0+q[1]*step)
  start=(round((a[0]-x0)/step),round((a[1]-y0)/step),hd(ad),0);goal=(round((dest[0]-x0)/step),round((dest[1]-y0)/step));gh=hd(mul(bd,-1));cache={}
  def clear(q,h=None,next_h=None):
   h=q[2] if h is None else h;next_h=h if next_h is None else next_h;k=(*q[:2],h,next_h)
   if k not in cache:
    x,y=xy(q);u=norm(dirs[h]);v=norm(dirs[next_h]);n1=(-u[1],u[0]);n2=(-v[1],v[0]);den=1+u[0]*v[0]+u[1]*v[1]
    m=((n1[0]+n2[0])/den,(n1[1]+n2[1])/den)
    valid=.9<x<339.1 and .9<y<259.1 and min(point_segment((x,y),c,d) for c,d in zip(guide,guide[1:]))<3.2
    if valid:
     for sign in (-1,1):
      xx,yy=add((x,y),mul(m,(W+GAP)/2*sign));pt=p.VECTOR2I(p.FromMM(xx),p.FromMM(yy))
      if any(it.GetNetname() not in names and (math.dist((xx,yy),p.ToMM(it.GetPosition()))<p.ToMM(it.GetWidth())/2+W/2+self.external_spacing(it,(xx,yy),ownnet=names[0]) if it.GetClass()=='PCB_VIA' else it.HitTest(pt,p.FromMM(W/2+self.external_spacing(it,(xx,yy),ownnet=names[0])))) for it in self.fx._items(layer,'',xx,yy,2)):
       valid=False;break
    cache[k]=valid
   return cache[k]
  if not clear(start) or not clear((*goal,gh,4)):
   print('pair spine blocked endpoint',names,clear(start),clear((*goal,gh,4)),a,dest,flush=True);return None
  remaining=[sum(math.dist(c,d) for c,d in zip(guide[i+1:],guide[i+2:])) for i in range(len(guide)-1)];hc={}
  def heuristic(q):
   k=q[:2]
   if k not in hc:
    point=xy(q);values=[]
    for i,(c,d) in enumerate(zip(guide,guide[1:])):
     v=(d[0]-c[0],d[1]-c[1]);den=v[0]**2+v[1]**2;t=max(0,min(1,((point[0]-c[0])*v[0]+(point[1]-c[1])*v[1])/den)) if den else 0;projection=add(c,mul(v,t))
     values.append((math.dist(point,projection),(remaining[i]+math.dist(projection,d))/step))
    hc[k]=min(values)[1]
   return hc[k]
  pq=[(heuristic(start),0,start)];prev={start:None};cost={start:0};count=0
  while pq and count<600000:
   _,c,q=heapq.heappop(pq);count+=1
   if c>cost.get(q,1e30):continue
   if q[:2]==goal and q[2]==gh and q[3]>=4:
    path=[]
    while q is not None:path.append(xy(q));q=prev[q]
    path.reverse();path[0]=a;out=[a]
    for i in range(1,len(path)-1):
     v1=(path[i][0]-out[-1][0],path[i][1]-out[-1][1]);v2=(path[i+1][0]-path[i][0],path[i+1][1]-path[i][1])
     if abs(v1[0]*v2[1]-v1[1]*v2[0])>1e-8:out.append(path[i])
    out.extend((path[-1],add(b,mul(bd,.25)),b));return out
   headings=(q[2],) if q[3]<4 else ((q[2]-1)%8,q[2],(q[2]+1)%8)
   for h in headings:
    dx,dy=dirs[h];m=(q[0]+dx,q[1]+dy,h,min(4,q[3]+1) if h==q[2] else 1)
    if not clear(q,q[2],h) or not clear(m) or not clear(((q[0]+m[0])/2,(q[1]+m[1])/2),h,h):continue
    nc=c+math.hypot(dx,dy)+(.8 if h!=q[2] else 0)
    if nc<cost.get(m,1e30):cost[m]=nc;prev[m]=q;heapq.heappush(pq,(nc+2.0*heuristic(m),nc,m))
  print('pair spine exhausted',names,count,len(cache),'nearest remaining mm',min(hc.values())*step,flush=True)
  return None
 def pair_spine_3d(self,names,a,b,ad,bd,guide,side):
  # Local direction-constrained paired search. A layer transition reserves
  # two complete fanouts and a pair of ordinary through-vias atomically.
  step=.25;dirs=((1,0),(1,1),(0,1),(-1,1),(-1,0),(-1,-1),(0,-1),(1,-1));sep=(W+GAP)/2
  hd=lambda d:max(range(8),key=lambda i:(d[0]*dirs[i][0]+d[1]*dirs[i][1])/math.hypot(*dirs[i]))
  x0=a[0]-math.ceil((a[0]-min(x for x,y in guide)+7)/step)*step;y0=a[1]-math.ceil((a[1]-min(y for x,y in guide)+7)/step)*step
  xy=lambda q:(x0+q[0]*step,y0+q[1]*step)
  dest=add(b,mul(bd,.5));goal=(round((dest[0]-x0)/step),round((dest[1]-y0)/step));gh=hd(mul(bd,-1));start=(round((a[0]-x0)/step),round((a[1]-y0)/step),hd(ad),4,p.B_Cu);cache={};v_cache={}
  def foreign(q,layer,radius):
   x,y=q;pt=p.VECTOR2I(p.FromMM(x),p.FromMM(y))
   return any(it.GetNetname() not in names and (math.dist(q,p.ToMM(it.GetPosition()))<p.ToMM(it.GetWidth())/2+radius+self.external_spacing(it,q,ownnet=names[0]) if it.GetClass()=='PCB_VIA' else it.HitTest(pt,p.FromMM(radius+self.external_spacing(it,q,ownnet=names[0])))) for it in self.fx._items(layer,'',x,y,2))
  def clear(q,h=None,next_h=None):
   h=q[2] if h is None else h;next_h=h if next_h is None else next_h;key=(*q[:2],h,next_h,q[4])
   if key not in cache:
    x,y=xy(q);u=norm(dirs[h]);v=norm(dirs[next_h]);n1=(-u[1],u[0]);n2=(-v[1],v[0]);den=1+u[0]*v[0]+u[1]*v[1];m=((n1[0]+n2[0])/den,(n1[1]+n2[1])/den)
    valid=.9<x<339.1 and .9<y<259.1 and min(point_segment((x,y),c,d) for c,d in zip(guide,guide[1:]))<7
    cache[key]=valid and all(not foreign(add((x,y),mul(m,sign*sep)),q[4],W/2) for sign in (-1,1))
   return cache[key]
  def transition(q):
   key=(*q[:3],q[4])
   if key not in v_cache:
    c=xy(q);u=norm(dirs[q[2]]);n=(-u[1],u[0]);points=[add(c,mul(n,sign*side*.35)) for sign in (1,-1)]
    good=all(self.stitch(net,v,.4,.2,dry=True) and all(not foreign(v,layer,.2) for layer in (p.F_Cu,p.B_Cu)) for net,v in zip(names,points))
    if good:
     for layer in (p.F_Cu,p.B_Cu):
      for t in (-1,-.75,-.5,-.25,0,.25,.5,.75,1):
       sp=.35-(.35-sep)*abs(t)
       if any(foreign(add(add(c,mul(u,t)),mul(n,sign*sp)),layer,W/2) for sign in (-1,1)):good=False;break
      if not good:break
    v_cache[key]=good
   return v_cache[key]
  if not clear(start) or not clear((*goal,gh,4,p.B_Cu)):return None
  def heur(q):
   dx=abs(q[0]-goal[0]);dy=abs(q[1]-goal[1]);return max(dx,dy)+(math.sqrt(2)-1)*min(dx,dy)+(0 if q[4]==p.B_Cu else 8)
  cost={start:0};prev={start:None};pq=[(heur(start),0,start)];count=0;found=None
  while pq and count<900000:
   _,c,q=heapq.heappop(pq);count+=1
   if c>cost.get(q,1e30):continue
   if q[:2]==goal and q[2]==gh and q[3]>=4 and q[4]==p.B_Cu:found=q;break
   headings=(q[2],) if q[3]<4 else ((q[2]-1)%8,q[2],(q[2]+1)%8)
   moves=[]
   for h in headings:
    dx,dy=dirs[h];m=(q[0]+dx,q[1]+dy,h,min(8,q[3]+1) if h==q[2] else 1,q[4])
    if clear(q,q[2],h) and clear(m) and clear(((q[0]+m[0])/2,(q[1]+m[1])/2,h,4,q[4]),h,h):moves.append((m,math.hypot(dx,dy)+(.8 if h!=q[2] else 0)))
   if q[3]>=8 and transition(q):moves.append(((*q[:3],0,p.F_Cu if q[4]==p.B_Cu else p.B_Cu),32))
   for m,delta in moves:
    nc=c+delta
    if nc<cost.get(m,1e30):cost[m]=nc;prev[m]=q;heapq.heappush(pq,(nc+2.0*heur(m),nc,m))
  if found is None:print('local3D paired route failed',names,count,len(v_cache),'nearest',sorted((heur(q)*step,xy(q),q[2:]) for q in cost)[:3],'legal_via_stations',sum(v_cache.values()),flush=True);return None
  states=[];q=found
  while q is not None:states.append(q);q=prev[q]
  states.reverse();chunks=[];current=[];layer=states[0][4]
  for q in states:
   point=xy(q)
   if q[4]!=layer:chunks.append((layer,current));current=[point];layer=q[4]
   elif not current or math.dist(current[-1],point)>1e-9:current.append(point)
  chunks.append((layer,current));chunks[0][1][0]=a;chunks[-1][1].extend((add(b,mul(bd,.25)),b))
  # Preserve1mm of the straight run either side of each expanded via station.
  result=[]
  for layer,path in chunks:
   out=[path[0]]
   for i in range(1,len(path)-1):
    u=norm((path[i][0]-out[-1][0],path[i][1]-out[-1][1]));v=norm((path[i+1][0]-path[i][0],path[i+1][1]-path[i][1]))
    if abs(u[0]*v[1]-u[1]*v[0])>1e-7:out.append(path[i])
   out.append(path[-1]);result.append((layer,out))
  print('local3D paired route found',names,count,'layers',[self.b.GetLayerName(x) for x,_ in result],flush=True);return result
 def pair(self,names,a,b,ad,bd,middle,layer='B',shift=(0,0),source=None,target=None,main_layer='B',source_global=False,target_lead=1,source_lead=1,tune_negative_mm=0,ground_at_target=True,create_source_vias=True,create_target_vias=True,main_paths=None):
  # Endpoints are ordered positive,negative. No USB2 polarity inversion allowed.
  sep=(W+GAP)/2
  def launch(points,direction,translation=(0,0)):
   ac=mul(add(points[0],points[1]),.5);axis=(-direction[1],direction[0]);dv=(points[0][0]-ac[0],points[0][1]-ac[1]);side=1 if dv[0]*axis[0]+dv[1]*axis[1]>=0 else -1
   if layer=='F':return points,[[q] for q in points],ac,side
   length=math.hypot(*translation)
   centres=[add(ac,mul(direction,1.2)),add(ac,mul(direction,2))]
   if length:centres.append(add(add(ac,mul(direction,2+length)),translation))
   centres.append(add(add(ac,mul(direction,2.8+length)),translation))
   vc=add(centres[-1],mul(direction,.8));paths=[];vias=[]
   for s,q in zip((side,-side),points):
    spine=offset(centres,sep*s);v=add(vc,mul(axis,.35*s));paths.append([q,add(q,mul(direction,.6)),*spine,v]);vias.append(v)
   return vias,paths,vc,side
  af=launch(a,ad,shift);bf=launch(b,bd)
  if source:
   vs=[[q if source_global else self.base_xy(q) for q in path] for path in source];vc=mul(add(vs[0][-1],vs[1][-1]),.5);axis=(-ad[1],ad[0]);side=1 if (vs[0][-1][0]-vc[0])*axis[0]+(vs[0][-1][1]-vc[1])*axis[1]>=0 else -1
   af=([v[-1] for v in vs],vs,vc,side)
  if target:
   vs=target;vc=mul(add(vs[0][-1],vs[1][-1]),.5);axis=(-bd[1],bd[0]);side=1 if (vs[0][-1][0]-vc[0])*axis[0]+(vs[0][-1][1]-vc[1])*axis[1]>=0 else -1
   bf=([v[-1] for v in vs],vs,vc,side)
  sa=add(af[2],mul(ad,source_lead));sb=add(bf[2],mul(bd,target_lead))
  centre=chamfer([sa,*middle,sb],2)
  chunks=None
  if main_paths is not None:pass
  elif main_layer=='AUTO':
   signal.alarm(90)
   try:chunks=self.pair_spine_3d(names,sa,sb,ad,bd,centre,af[3])
   except TimeoutError:chunks=None
   finally:signal.alarm(0)
   if chunks is None:
    self.pairs.append({'pair':names,'routed':False,'reason':'No validated local paired3D path'});return False
   centre=chunks[-1][1]
  elif layer=='B':
   signal.alarm(50)
   try:found=self.pair_spine(names,sa,sb,ad,bd,centre,p.F_Cu if main_layer=='F' else p.B_Cu)
   except TimeoutError:found=None
   finally:signal.alarm(0)
   if found:centre=found
  # Correct end-facing order is a topological requirement, not a reason to swap.
  end_tangent=norm((centre[-1][0]-centre[-2][0],centre[-1][1]-centre[-2][1]));en=(-end_tangent[1],end_tangent[0]);ep=(b[0][0]-bf[2][0],b[0][1]-bf[2][1])
  if main_paths is None and (ep[0]*en[0]+ep[1]*en[1])*af[3]<0:
   self.pairs.append({'pair':names,'routed':False,'reason':'manual corridor endpoint polarity/heading incompatible'});return False
  items=[]
  for i,s in enumerate((af[3],-af[3])):
   if main_paths is not None:
    path=main_paths[i]
    if math.dist(path[0],af[0][i])>1e-5 or math.dist(path[-1],bf[0][i])>1e-5:
     self.pairs.append({'pair':names,'routed':False,'reason':'Exact reserved arrival no longer matches its physical endpoints'});return False
    items.append((names[i],[('F',af[1][i]),(main_layer,path),('F',list(reversed(bf[1][i])))],([af[0][i]] if create_source_vias else [])+([bf[0][i]] if create_target_vias else [])));continue
   spine=offset(centre,sep*s)
   if not spine:return False
   if layer=='F':items.append((names[i],[('F',[a[i],add(a[i],mul(ad,.8)),*spine,add(b[i],mul(bd,.8)),b[i]])],[]))
   elif chunks:
    segs=[('F',af[1][i])];vias=[]
    for index,(ly,path) in enumerate(chunks):
     trace=offset(path,sep*s);u0=norm((path[1][0]-path[0][0],path[1][1]-path[0][1]));u1=norm((path[-1][0]-path[-2][0],path[-1][1]-path[-2][1]));n0=(-u0[1],u0[0]);n1=(-u1[1],u1[0])
     if index:
      v=add(path[0],mul(n0,.35*s));trace[0]=add(add(path[0],u0),mul(n0,sep*s));trace.insert(0,v)
     else:trace.insert(0,af[0][i])
     if index<len(chunks)-1:
      v=add(path[-1],mul(n1,.35*s));trace[-1]=add(add(path[-1],mul(u1,-1)),mul(n1,sep*s));trace.append(v);vias.append(v)
     else:trace.append(bf[0][i])
     trace=[q for k,q in enumerate(trace) if k==0 or math.dist(q,trace[k-1])>1e-8];segs.append(('F' if ly==p.F_Cu else 'B',trace))
    segs.append(('F',list(reversed(bf[1][i]))));vias=([af[0][i]] if create_source_vias else [])+vias+([bf[0][i]] if create_target_vias else []);items.append((names[i],segs,vias))
   else:items.append((names[i],[('F',af[1][i]),(main_layer,[af[0][i],*spine,bf[0][i]]),('F',list(reversed(bf[1][i])))],[] if main_layer=='F' else ([af[0][i]] if create_source_vias else [])+([bf[0][i]] if create_target_vias else [])))
  tuning=None
  if tune_negative_mm:
   body=items[1][1][1][1];amplitude=tune_negative_mm/(4*(math.sqrt(2)-1));run=.8;between=1.0;required=4*amplitude+2*run+between
   for index,(aa,bb) in enumerate(zip(body,body[1:])):
    length=math.dist(aa,bb)
    if length<required+2:continue
    u=norm((bb[0]-aa[0],bb[1]-aa[1]));outward=mul((-u[1],u[0]),-af[3]);lead=(length-required)/2;start=add(aa,mul(u,lead));points=[start];here=start
    for bump in range(2):
     points.extend((add(add(here,mul(u,amplitude)),mul(outward,amplitude)),add(add(here,mul(u,amplitude+run)),mul(outward,amplitude)),add(here,mul(u,2*amplitude+run))))
     here=points[-1]
     if bump==0:here=add(here,mul(u,between));points.append(here)
    body[index+1:index+1]=points;tuning={'net':names[1],'added_length_mm':tune_negative_mm,'amplitude_mm':amplitude,'window':points,'reason':'Local length compensation; this bounded window is not uniform90ohm pair geometry.'};break
   if tuning is None:
    self.pairs.append({'pair':names,'routed':False,'reason':'No long segment available for bounded HS length compensation'});return False
  obstacles=[]
  pads_by_net={n:[p.ToMM(q.GetPosition()) for fp in self.b.GetFootprints() for q in fp.Pads() if q.GetNetname()==n] for n in names}
  def segment_width(net,a,b,ly):
   return .18 if ly=='F' and any(math.dist(q,a)<1e-5 or math.dist(q,b)<1e-5 for q in pads_by_net[net]) else W
  def clear(net,path,ly):
   layer0=p.F_Cu if ly=='F' else p.B_Cu
   for k,(a0,b0) in enumerate(zip(path,path[1:])):
    width0=segment_width(net,a0,b0,ly)
    for x,y in samples([a0,b0],.04):
     pt=p.VECTOR2I(p.FromMM(x),p.FromMM(y))
     hits=[it for it in self.fx._items(layer0,net,x,y,2) if (math.dist((x,y),p.ToMM(it.GetPosition()))<p.ToMM(it.GetWidth())/2+width0/2+self.external_spacing(it,(x,y),.160 if it.GetNetname() in names else .205,net) if it.GetClass()=='PCB_VIA' else it.HitTest(pt,p.FromMM(width0/2+self.external_spacing(it,(x,y),.160 if it.GetNetname() in names else .20,net))))]
     if hits:
      it=hits[0];obstacles.append({'net':net,'layer':ly,'point':(x,y),'blocked_by_net':it.GetNetname(),'object':it.GetClass(),'object_uuid':it.m_Uuid.AsString()});return False
   return True
  good=all(all(clear(n,q,ly) for ly,q in segs) and all(self.stitch(n,q,.4,.2,dry=True) for q in vias) for n,segs,vias in items)
  for la,pa in items[0][1]:
   for lb,pb in items[1][1]:
    if la==lb and any(segment_distance(c,d,e,f)<W+GAP-1e-6 for c,d in zip(pa,pa[1:]) for e,f in zip(pb,pb[1:])):good=False;obstacles.append({'reason':'pairmate conductor spacing','layer':la})
  if any(math.dist(c,d)<.65-1e-6 for c in items[0][2] for d in items[1][2]):good=False;obstacles.append({'reason':'pair drill spacing'})
  for vias,segments in ((items[0][2],items[1][1]),(items[1][2],items[0][1])):
   if any(point_segment(v,c,d)<.2+W/2+.2-1e-6 for v in vias for ly,q in segments for c,d in zip(q,q[1:])):good=False;obstacles.append({'reason':'via to pairmate track'})
  lengths=[sum(math.dist(c,d) for ly,q in segs for c,d in zip(q,q[1:])) for _,segs,_ in items]
  rec={'pair':names,'routed':bool(good),'layer':layer,'width':W,'gap':GAP,'obstructions':obstacles,'length_mm':lengths,'skew_mm':abs(lengths[0]-lengths[1]),'length_compensation':tuning,'exact_reservation_sha256':CHILD_RESERVATION_SHA256 if main_paths is not None else None,'paths':[{'net':n,'segments':segs,'vias':vs} for n,segs,vs in items]}
  self.pairs.append(rec);print('USB2 pair',names,good,'skew',rec['skew_mm'],flush=True)
  if not good:return False
  for n,segs,vias in items:
   for ly,q in segs:
    for aa,bb in zip(q,q[1:]):self.g.track(n,[aa,bb],segment_width(n,aa,bb,ly),ly)
   for q in vias:assert self.stitch(n,q,.4,.2)
  self.fx._index=None
  if layer=='B' and main_layer in ('B','AUTO'):
   # A dedicated continuous L3 ground corridor follows every new bottom signal
   # segment. L2 remains the composition's uninterrupted full-board ground.
   ground=p.SHAPE_POLY_SET()
   for ly,q in items[0][1]+items[1][1]:
    if ly!='B':continue
    for a0,b0 in zip(q,q[1:]):
     u=norm((b0[0]-a0[0],b0[1]-a0[1]));n=(-u[1],u[0]);aa=add(a0,mul(u,-1));bb=add(b0,mul(u,1));rect=p.SHAPE_POLY_SET();rect.NewOutline()
     for x,y in [add(aa,mul(n,1.5)),add(bb,mul(n,1.5)),add(bb,mul(n,-1.5)),add(aa,mul(n,-1.5))]:rect.Append(p.FromMM(x),p.FromMM(y))
     ground.BooleanAdd(rect,p.SHAPE_POLY_SET.PM_STRICTLY_SIMPLE)
   z=self.g.zone('GND','In2',[(0,0),(1,0),(1,1)],100,.25,minw=.25);z.Outline().RemoveAllContours();z.Outline().Append(ground)
   for vc in ((af[2],bf[2]) if ground_at_target else (af[2],)):
    for dx,dy in ((1.3,0),(-1.3,0),(0,1.3),(0,-1.3)):self.stitch('GND',add(vc,(dx,dy)))
  return True
 def usb_channel(self,label,steps):
  tracks={t.m_Uuid.AsString() for t in self.b.GetTracks()};zones={z.m_Uuid.AsString() for z in self.b.Zones()};start=len(self.pairs)
  for step in steps:
   if self.pair(**step):continue
   for t in list(self.b.GetTracks()):
    if t.m_Uuid.AsString() not in tracks:self.remove(t)
   for zone in list(self.b.Zones()):
    if zone.m_Uuid.AsString() not in zones:self.remove(zone)
   for row in self.pairs[start:]:row.update(routed=False,rolled_back=True,channel=label)
   return False
  for row in self.pairs[start:]:row['channel']=label
  return True
 def usb_pairs(self):
  #HighSpeed is routed first into the USB cell's explicitly reserved B arrival.
  #The local paired3D search may add checked transitions if that corridor changes.
  cx,cy=p.ToMM(self.fps['U9500'].GetPosition());land=lambda q:(q[0]+cx-180,q[1]+cy-217)
  hs1=(land((196.35,190)),land((195.65,190)));hub=(self.pad('U9500','1'),self.pad('U9500','2'));root=(self.pad('U10','15'),self.pad('U10','14'));diag=math.sqrt(.5)
  preserved=[]
  for net in PAIR_NAMES[2]:
   candidates=[t for t in self.b.GetTracks() if t.GetClass()=='PCB_VIA' and t.GetNetname()==net and math.dist(p.ToMM(t.GetPosition()),(cx,cy))<8]
   preserved.append(min(candidates,key=lambda t:math.dist(p.ToMM(t.GetPosition()),(cx,cy))) if candidates else None)
  existing_hub_escape=all(v is not None for v in preserved)
  target_vias=tuple(p.ToMM(v.GetPosition()) for v in preserved) if existing_hub_escape else (land((184.8,219.8)),land((184.8,219.1)))
  hub_target=[[q] for q in target_vias] if existing_hub_escape else [[hub[0],add(hub[0],(.5,0)),target_vias[0]],[hub[1],add(hub[1],(.5,0)),target_vias[1]]]
  self.evidence.append({'action':'HS arrival uses preserved USB-cell package escapes','preserved':existing_hub_escape,'via_uuids':[v.m_Uuid.AsString() for v in preserved if v is not None],'via_positions':target_vias,'fallback_note':None if existing_hub_escape else 'Old diagnostic source lacks the coherent cell package escapes; not final input.'})
  reserved={x['net']:x for x in CHILD_RESERVATION['legs']};assert set(reserved)==set(PAIR_NAMES[2])
  exact_paths=[[(x+cx-65,y+cy-57) for x,y in reserved[n]['points_mm']] for n in PAIR_NAMES[2]] if existing_hub_escape else None
  self.usb_channel('USB5744 to CH334 HighSpeed',[
   dict(names=PAIR_NAMES[2],a=root,b=hs1,ad=(diag,diag),bd=(0,-1),middle=[(214,108),land((196,186))],layer='B',source=[[(208.9375,82.25),(209.5375,82.25),(211.3,82.25),(211.65,82.1),(212.68,82.07)],[(208.9375,82.75),(209.5375,82.75),(211.4,82.65),(211.7,82.6),(212.15,82.6)]],source_lead=.4,target=[[hs1[0]],[hs1[1]]],ground_at_target=False,create_target_vias=False,tune_negative_mm=1.0),
   dict(names=PAIR_NAMES[2],a=hs1,b=target_vias,ad=(0,1),bd=(1,0),middle=[land((196,200)),land((190,210)),land((190,218)),land((186,219.4))],layer='B',main_layer='B' if existing_hub_escape else 'AUTO',source=[[hs1[0]],[hs1[1]]],source_global=True,target=hub_target,target_lead=.8,create_source_vias=False,create_target_vias=not existing_hub_escape,main_paths=exact_paths)])
  a=(self.pad('U10','8'),self.pad('U10','7'));b=((80.08,184),(77.54,184))
  self.pair(PAIR_NAMES[0],a,b,(0,1),(0,-1),[(205.85,110),(190,126),(190,150),(78.81,150)],'B',source=[[(206.25,83.9375),(206.2,84.5875)],[(205.75,83.9375),(205.5,84.5875)]],target=[[b[0]],[b[1]]],target_lead=4)
  # FullSpeed port4 crosses the new HS B corridor on F.Cu. Its compact
  # balanced transitions stay outside SMD pads and are counted in the audit.
  a=(self.pad('U10','6'),self.pad('U10','5'));b=((106.08,184),(103.54,184));p41=((209.65,112),(210.35,112));p42=((110,189.65),(110,190.35))
  self.usb_channel('CH334 to PWM FullSpeed',[
   dict(names=PAIR_NAMES[1],a=a,b=p41,ad=(1,0),bd=(0,-1),middle=[(207,103.2),(207,110)],layer='B',source=[[(205.0625,83.25),(204.2,83.55)],[(205.0625,82.75),(204.2,82.85)]],target=[[p41[0]],[p41[1]]],ground_at_target=False),
   dict(names=PAIR_NAMES[1],a=p41,b=p42,ad=(0,1),bd=(1,0),middle=[(220,130),(220,155),(113.5,155),(113.5,190)],layer='B',main_layer='F',source=[[p41[0]],[p41[1]]],source_global=True,target=[[p42[0]],[p42[1]]]),
   dict(names=PAIR_NAMES[1],a=p42,b=b,ad=(-1,0),bd=(0,1),middle=[(108.5,190),(104.81,190)],layer='B',source=[[p42[0]],[p42[1]]],source_global=True,target=[[b[0]],[b[1]]],target_lead=4)])
 def can_links(self):
  # Reuse the retained CAN-header escape, then cross USB2 B lanes on F.Cu in
  # the service strip. No separate-leg USB routing or clearance relaxation.
  for n,source,target,x,y in [('CAN_H',(49.54,168),'2',246,128.5),('CAN_L',(52.08,168),'3',224,129.2)]:
   assert self.stitch(n,source,.4,.2),('CAN retained-header via',n)
   left=(46 if n=='CAN_H' else 47,y);right=(x,y);upper=next((x,yy) for yy in ((42,40,38,30,26) if n=='CAN_H' else (48,49,47,50)) if self.fx.free(p.B_Cu,n,x,yy,.15))
   def service_via(wanted):
    candidates=[wanted]+[add(wanted,(dx,dy)) for dx,dy in ((.8,0),(-.8,0),(1.2,0),(-1.2,0),(0,-.8),(0,.8),(1.6,0),(-1.6,0))]
    chosen=next((q for q in candidates if self.stitch(n,q,.4,.2,dry=True)),None)
    assert chosen,('CAN service via has no legal nearby position',n,wanted)
    assert self.stitch(n,chosen,.4,.2);return chosen
   left=service_via(left);right=service_via(right)
   legs=[(source,left),(right,upper),(upper,self.pad('J6007',target))] if n=='CAN_H' else [(source,left),(right,upper),(upper,(236,48)),((236,48),(264,44)),((264,44),self.pad('J6007',target))]
   for aa,bb in legs:
    signal.alarm(30)
    try:ok=self.fx.route(n,aa,bb,w=.3,step=.25,win=8 if n=='CAN_H' else 24,layers=('B',) if n=='CAN_H' else ('B','F'))
    except TimeoutError:ok=False
    finally:signal.alarm(0)
    self.evidence.append({'net':n,'from':aa,'to':bb,'routed':bool(ok),'method':'CAN B corridor'});print('CAN',n,aa,bb,ok,flush=True)
   path=[left,right];good=all(self.fx.free(p.F_Cu,n,*q,.15) for q in samples(path,.08))
   if good:self.g.track(n,path,.3,'F');self.fx._index=None
   else:
    signal.alarm(30)
    try:good=self.fx.route(n,left,right,w=.3,step=.25,win=4,layers=('F','B'))
    except TimeoutError:good=False
    finally:signal.alarm(0)
   self.evidence.append({'net':n,'from':left,'to':right,'routed':good,'method':'F service strip crossing'});print('CAN F crossing',n,good,flush=True)
 def protect_hs_from_power_pours(self):
  # Native clearance is a manufacturing minimum. Independently keep positive
  # outer-layer pours out of the HS signal's.762mm SI isolation envelope.
  # Inside a declared package escape, BOTH copper points must stay in its box.
  hs=[t for t in self.b.GetTracks() if t.GetNetname() in ('HUB_CHILD_DP','HUB_CHILD_DM')];cache={};changed=[]
  def signature(poly):
   return tuple(tuple(tuple((line.CPoint(i).x,line.CPoint(i).y) for i in range(line.PointCount())) for line in [poly.COutline(k)]+[poly.CHole(k,h) for h in range(poly.HoleCount(k))]) for k in range(poly.OutlineCount()))
  def polygon(points):
   poly=p.SHAPE_POLY_SET();poly.NewOutline()
   for x,y in points:poly.Append(p.FromMM(x),p.FromMM(y))
   return poly
  def box_polygon(box):return polygon([(box[0],box[1]),(box[2],box[1]),(box[2],box[3]),(box[0],box[3])])
  for zone in self.zones+list(self.b.Zones()):
   net=zone.GetNetname();layer=zone.GetLayer()
   if net in ('','GND','HUB_CHILD_DP','HUB_CHILD_DM') or layer not in (p.F_Cu,p.B_Cu):continue
   key=(net,layer)
   if key not in cache:
    boxes=[]
    for ref,half in (('U10',5),('U9500',6.5)):
     fp=self.fps.get(ref)
     if fp and net in {pad.GetNetname() for pad in fp.Pads()}:
      cx,cy=p.ToMM(fp.GetPosition());boxes.append((cx-half,cy-half,cx+half,cy+half))
    guard=p.SHAPE_POLY_SET()
    for track in hs:
     if not track.IsOnLayer(layer):continue
     aa,bb=p.ToMM(track.GetStart()),p.ToMM(track.GetEnd());radius=p.ToMM(track.GetWidth())/2+.770;cuts={0.,1.}
     for box in boxes:
      for axis,edges in ((0,(box[0],box[2])),(1,(box[1],box[3]))):
       if abs(bb[axis]-aa[axis])<1e-10:continue
       for edge in edges:
        t=(edge-aa[axis])/(bb[axis]-aa[axis])
        if 0<t<1:cuts.add(t)
     cuts=sorted(cuts)
     for lo,hi in zip(cuts,cuts[1:]):
      a=add(aa,mul((bb[0]-aa[0],bb[1]-aa[1]),lo));b=add(aa,mul((bb[0]-aa[0],bb[1]-aa[1]),hi));mid=mul(add(a,b),.5)
      if math.dist(a,b)<1e-9:
       r=radius/math.cos(math.pi/24);part=polygon([add(a,(r*math.cos(k*math.pi/12),r*math.sin(k*math.pi/12))) for k in range(24)])
      else:
       u=norm((b[0]-a[0],b[1]-a[1]));n=(-u[1],u[0]);a0=add(a,mul(u,-radius));b0=add(b,mul(u,radius));part=polygon([add(a0,mul(n,radius)),add(b0,mul(n,radius)),add(b0,mul(n,-radius)),add(a0,mul(n,-radius))])
      for box in boxes:
       if box[0]<=mid[0]<=box[2] and box[1]<=mid[1]<=box[3]:part.BooleanSubtract(box_polygon(box),p.SHAPE_POLY_SET.PM_STRICTLY_SIMPLE)
      guard.BooleanAdd(part,p.SHAPE_POLY_SET.PM_STRICTLY_SIMPLE)
    cache[key]=guard
   if not cache[key].OutlineCount() or not zone.Outline().Collide(cache[key]):continue
   before=signature(zone.Outline());zone.Outline().BooleanSubtract(cache[key],p.SHAPE_POLY_SET.PM_STRICTLY_SIMPLE);after=signature(zone.Outline())
   if before!=after:changed.append({'uuid':zone.m_Uuid.AsString(),'net':net,'layer':self.b.GetLayerName(layer),'before_geometry_sha256':hashlib.sha256(repr(before).encode()).hexdigest(),'after_geometry_sha256':hashlib.sha256(repr(after).encode()).hexdigest()})
  self.hs_zone_exclusions=changed
 def finish(self):
  self.protect_hs_from_power_pours()
  for z in self.zones:self.b.Add(z)
  profiles={q:q.read_bytes() for q in {self.output.with_suffix('.kicad_pro'),self.path.with_suffix('.kicad_pro')} if q.exists()}
  try:p.SaveBoard(str(self.output),self.b)
  finally:
   for q,data in profiles.items():q.write_bytes(data)
  subprocess.run(['python3',str(ROOT/'source/fabrication/refill_drc.py'),str(self.output),str(K.parent/'drc.rpt')],check=True)
  current={t.m_Uuid.AsString():{'net':t.GetNetname(),'layer':int(t.GetLayer()),'class':t.GetClass(),'from':tuple(p.ToMM(t.GetStart())),'to':tuple(p.ToMM(t.GetEnd())),'width_mm':p.ToMM(t.GetWidth()),'drill_mm':p.ToMM(t.GetDrillValue()) if t.GetClass()=='PCB_VIA' else None} for t in self.b.GetTracks()}
  original_changes={'removed':[{**self.original_copper[q],'uuid':q} for q in sorted(self.initial_ids-set(current))],'modified':[{'uuid':q,'before':self.original_copper[q],'after':current[q]} for q in sorted(self.initial_ids&set(current)) if self.original_copper[q]!=current[q]]}
  report={'integration_placements_sha256':PLACEMENTS_SHA256,'child_arrival_reservation_sha256':CHILD_RESERVATION_SHA256,'hs_power_pour_exclusions':self.hs_zone_exclusions,'HS_package_escape_note':'CH334 and USB5744 body+3mm are explicit prototype SI/EMI bench exceptions. Ordinary manufacturing clearance remains unchanged.','original_copper_changes':original_changes,'generator_sha256':GENERATOR_SHA256,'routed_board_sha256':hashlib.sha256(self.output.read_bytes()).hexdigest(),'profile_sha256':hashlib.sha256(self.output.with_suffix('.kicad_pro').read_bytes()).hexdigest(),'stale_USB_inventory_references':self.stale_usb_refs,'obsolete_USB_inventory_references':self.stale_usb_extra,'source_sha256':self.source_hash,'live_cell_files_sha256_at_completion':{k:hashlib.sha256((ROOT/c['board']).read_bytes()).hexdigest() for k,c in CELLS.items()},'cell_hash_note':'Live cells may advance beyond the input snapshot; source_sha256 and the composition manifest identify the actual input.','power':self.power,'pairs':self.pairs,'ordinary_routes':self.evidence,'added_track_uuids':[t.m_Uuid.AsString() for t in self.b.GetTracks() if t.m_Uuid.AsString() not in self.initial_ids],'release':'engineering integration; inspect native DRC plus intercell audit; cell-local USB work may remain open'}
  (K.parent/'integration-routing.json').write_text(json.dumps(report,indent=2)+'\n')

def write_pair_rules():
 # Preserve the USB cell rules already copied by the composition generator.
 path=K/'robot_pdb.kicad_dru';text=path.read_text() if path.exists() else '(version 1)\n'
 a='# BEGIN v07 integration USB2 mates';z='# END v07 integration USB2 mates'
 text=text.replace('; BEGIN v07 integration USB2 mates',a).replace('; END v07 integration USB2 mates',z)
 if a in text:text=text[:text.index(a)]+text[text.index(z)+len(z):]
 rules=[]
 for pn,nn in PAIR_NAMES:
  condition=f"(A.NetName == '{pn}' && B.NetName == '{nn}') || (A.NetName == '{nn}' && B.NetName == '{pn}')"
  rules.append(f'(rule "v07 {pn} mate spacing" (condition "{condition}") (constraint clearance (min 0.160mm)))')
 path.write_text(text.rstrip()+'\n'+a+'\n'+'\n'.join(rules)+'\n'+z+'\n')

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--input',default=str(K/'robot_pdb.kicad_pcb'));ap.add_argument('--stage',choices=['local','power','usb','can','all'],default='all');args=ap.parse_args()
 def timeout(a,b):raise TimeoutError('integration route time budget')
 signal.signal(signal.SIGALRM,timeout);write_pair_rules()
 job=Integration(args.input);job.place_support();job.repair_hub_fanout()
 if args.stage in ('usb','all'):job.usb_pairs()
 if args.stage in ('local','all'):job.local_support()
 if args.stage in ('can','all'):job.can_links()
 if args.stage in ('power','all'):job.power_links()
 job.finish()
if __name__=='__main__':main()
