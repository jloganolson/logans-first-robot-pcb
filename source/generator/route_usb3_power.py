"""Explicit USB cell power distribution, separate from coupled data routing.

Run on a coherent, saved140x100mm cell snapshot. Every proposed track and
via is checked against existing copper before it is added. A failed branch is
left open and recorded, never silently replaced by a long thin trace. Native
DRC and independent saved-copper checks remain required after this stage.
"""
import argparse,hashlib,json,math,shutil
from pathlib import Path
import pcbnew as p
import fixer
from build_usb3_frontend import USB3Fixer,DATA_NETS

def xy(q):return tuple(p.ToMM(q.GetPosition()))
def vec(q):return p.VECTOR2I(p.FromMM(q[0]),p.FromMM(q[1]))

def reserve_critical_power_anchors(board):
 """Reserve four narrow supply exits before adjacent SS launch allocation.

 A .25mm supply via cannot fit between two straight .204mm SS traces on
 .4mm pitch with .20mm foreign clearance. The data escapes must splay
 around the actual supply landing, rather than stealing this corridor.
 """
 r=Power(board)
 for ref,pin,q in [('U500','12',(69.05,55.2)),('U500','21',(65.2,52.95)),('U500','49',(64.8,61.05)),('U501','8',(19,72.15))]:
  pad=r.pad(ref,pin);net=pad.GetNetname()
  if r.via('critical supply landing '+ref+'.'+pin,net,q,.25,.15):r.path('critical supply escape '+ref+'.'+pin,net,[xy(pad),q],.17)
 return dict(complete=all(q['routed'] for q in r.rows),routes=r.rows)

def prepare_local_bypasses(board):
 """Place and seed local decoupling BEFORE the data router reserves copper.

 Positions below name the positive solderland, not ambiguous footprint
 origins. Grounddirection is derived from actual loaded pad geometry, so
 the same placement works for the selected0603/0805 and backside parts.
 This is engineering placement evidence, not an absolute-mm vendor rule.
 """
 r=Power(board);placements=[];anchors={}
 def move(ref,positive,direction,back=False):
  f=board.FindFootprintByReference(ref);old=[xy(q) for q in f.Pads()]
  assert not any(any(math.dist(tuple(p.ToMM(end)),q)<1e-6 for q in old) for t in board.GetTracks() for end in (t.GetStart(),t.GetEnd())),('pre-route stage called after cap routing',ref)
  if f.IsFlipped()!=back:f.Flip(f.GetPosition(),False)
  for angle in (0,90,180,270):
   f.SetOrientationDegrees(angle);f.SetPosition(vec(positive));a=xy(r.pad(ref,1));b=xy(r.pad(ref,2));v=(b[0]-a[0],b[1]-a[1])
   if v[0]*direction[0]+v[1]*direction[1]>.9*math.hypot(*v):break
  else:raise AssertionError(('no orientation',ref,direction))
  a=xy(r.pad(ref,1));f.Move(vec((positive[0]-a[0],positive[1]-a[1])))
  placements.append(dict(ref=ref,positive=xy(r.pad(ref,1)),ground=xy(r.pad(ref,2)),side='B' if back else 'F',rotation=f.GetOrientationDegrees()))
 #Each hub powerpin has its own0.1uF capacitor. Adjacent voltage domains
 #use opposite assembly sides and staggered throughvias, preserving pinout.
 hub=[('C513','5',(70.425,58),(1,0),False,(69.55,58)),
      ('C514','12',(68.35,55.2),(-1,0),True,(69.05,55.2)),
      ('C515','15',(68.8,51.6),(1,0),False,(68.15,52.4)),
      ('C516','21',(65.2,53.65),(0,1),True,(65.2,52.95)),
      ('C517','28',(62.4,51.575),(0,-1),False,(62.4,52.4)),
      ('C518','33',(59.575,56),(-1,0),False,(60.4,56)),
      ('C519','43',(61.2,62.8),(-1,0),False,(61.8,61.6)),
      ('C520','49',(64.8,60.35),(0,-1),True,(64.8,61.05)),
      ('C521','16',(68.25,53.4),(1,0),True,(67.2,54.25)),
      ('C522','31',(59.575,55.15),(-1,0),True,(60.4,55.15)),
      ('C523','44',(62.8,60.55),(-1,0),True,(62.8,59.75)),
      ('C524','55',(67.2,60.55),(1,0),True,(67.2,59.75))]
 for cap,pin,pos,direction,back,q in hub:move(cap,pos,direction,back)
 local=[('C509','U512','6',(128.1,17.05),(0,1)),
        ('C510','U513','6',(128.1,27.05),(0,1)),
        ('C511','U514','6',(128.1,37.05),(0,1)),
        ('C512','U515','5',(100.4,27),(0,1)),
        ('C529','U501','30',(24.4,71.5),(-1,0)),
        ('C530','U501','8',(18.5,72.85),(0,1)),
        ('C536','U502','3',(78.7,83.75),(0,-1)),
        ('C537','U502','2',(78.7,83.75),(-1,0)),
        ('C538','U502','5',(79.4,85.7),(-1,0)),
        ('C539','U503','6',(69.1,72.8),(-1,0))]
 for cap,ic,pin,pos,direction in local:move(cap,pos,(0,-1) if cap=='C537' else direction,cap in ('C537','C530','C539'))
 move('C535',(20,94.9),(0,1),True)
 move('C544',(68.75,94.9),(0,1),True);move('C545',(71.25,94.9),(0,1),True)
 move('C550',(120,91.5),(1,0),True)
 r.fx=PowerFixer(board)
 def seed(cap,ic,pin,q=None):
  pad=r.pad(ic,pin);net=pad.GetNetname();a=xy(pad);c=xy(r.pad(cap,1));layer='B' if board.FindFootprintByReference(cap).IsFlipped() else 'F'
  assert r.pad(cap,1).GetNetname()==net,(cap,ic,pin,'wrong supply')
  if q is None:
   centre=xy(pad.GetParent());v=(a[0]-centre[0],a[1]-centre[1]);normal=(math.copysign(1,v[0]),0) if abs(v[0])>abs(v[1]) else (0,math.copysign(1,v[1]))
   choices=[(a[0]+normal[0]*d,a[1]+normal[1]*d) for d in (.9,1.1,1.3,1.5)]
  else:choices=[q]
  diameter=.25 if cap in ('C514','C516','C520','C521','C523','C524','C530','C536','C537','C539') else .4;okay=False
  for candidate in choices:
   if not r.via(cap,net,candidate,diameter,.15,trial=True):continue
   centre=xy(pad.GetParent());v=(a[0]-centre[0],a[1]-centre[1]);normal=(math.copysign(1,v[0]),0) if abs(v[0])>abs(v[1]) else (0,math.copysign(1,v[1]))
   paths=[[a,candidate],[a,(a[0]+normal[0]*.65,a[1]+normal[1]*.65),candidate]]
   feed=next((path for path in paths if r.path(cap,net,path,.17,trial=True)),None)
   if feed is None:continue
   if not r.path(cap,net,[candidate,c],.2,layer,trial=True):continue
   r.via('local supply landing '+cap,net,candidate,diameter,.15);r.path('local IC feed '+cap,net,feed,.17);r.path('local capacitor feed '+cap,net,[candidate,c],.2,layer)
   anchors[cap]=dict(net=net,via=candidate,ic=ic,pin=pin,supply_pad_distance_mm=math.dist(a,c));okay=True;break
  if not okay:r.rows.append(dict(label='local supply '+cap,net=net,routed=False,reason='No legal short IC-to-capacitor seed'))
 for cap,pin,pos,direction,back,q in hub:seed(cap,'U500',pin,q)
 explicit={'C509':(126.95,16.1),'C510':(126.95,26.1),'C511':(126.95,36.1),'C512':(99.3,27),'C530':(19,72.15),'C536':(79.7,83.75),'C537':(79.7,83.75),'C538':(79.4,84.9),'C539':(69.75,72.2)}
 for cap,ic,pin,pos,direction in local:seed(cap,ic,pin,explicit.get(cap))
 for pin,y in [('7',86.8),('8',87.3)]:
  a=xy(r.pad('U502',pin));c=xy(r.pad('C538',1));r.path('camera mode strap '+pin,'+3V3_USB',[a,(a[0],y),(c[0],y),c],.17)
 for jref,net in [('J500','UP_VBUS'),('J501','CAM_VBUS')]:
  for num in ('B4','B9','A9','A4'):
   a=xy(r.pad(jref,num));q=(a[0],a[1]-(.59 if num.startswith('B') else 1.2))
   if r.via('connector supply escape '+jref+'.'+num,net,q,.25,.15):
    r.path('connector supply F '+jref+'.'+num,net,[a,q],.17)
    bx=xy(r.pad(jref,{'A9':'B4','A4':'B9'}.get(num,num)))[0]
    path=[q,(bx,q[1]+.65),(bx,94.9)] if num.startswith('A') else [q,(bx,94.9)]
    r.path('connector supply B '+jref+'.'+num,net,path,.30,'B')
  x=xy(board.FindFootprintByReference(jref))[0]
  r.path('connector supply bus '+jref,net,[(x-1.25,94.9),(x+1.25,94.9)],.6,'B')
 #Connector-side capacitance returns to the nearest plated shield ground.
 #No throughvia is drilled inside the Molex F.Cu pattern-restricted body.
 for cap,jref in [('C535','J500'),('C544','J501'),('C545','J501'),('C550','J502')]:
  ground=xy(r.pad(cap,2));candidates=[q for q in board.FindFootprintByReference(jref).Pads() if q.GetNetname()=='GND' and q.GetDrillSize().x]
  target=min(candidates,key=lambda q:math.dist(ground,xy(q)))
  r.path('local connector ground '+cap,'GND',[ground,xy(target)],.6,'B')
 #Local ground returns are established before data, so a later ground
 #stitch cannot puncture an accepted differential path.
 #This return stays to the left of the dedicated1.5mm raw5V B-side feed.
 if r.via('local ground via C538','GND',(76.65,84.5)):
  r.path('local ground C538','GND',[xy(r.pad('C538',2)),(76.65,84.5)],.4)
 for cap in [q[0] for q in hub]+[q[0] for q in local]:
  pad=r.pad(cap,2);a=xy(pad);positive=xy(r.pad(cap,1));v=(a[0]-positive[0],a[1]-positive[1]);length=math.hypot(*v);direction=(v[0]/length,v[1]/length);layer='B' if pad.IsOnLayer(p.B_Cu) else 'F';done=False
  existing=[t for t in board.GetTracks() if isinstance(t,p.PCB_VIA) and t.GetNetname()=='GND' and math.dist(a,xy(t))<(2.8 if cap in ('C514','C516','C520','C521','C530') else 1.7)]
  for via in sorted(existing,key=lambda q:math.dist(a,xy(q))):
   if r.path(cap,'GND',[a,xy(via)],.4,layer,trial=True):r.path('local ground '+cap,'GND',[a,xy(via)],.4,layer);done=True;break
  if not done:
   for angle in (0,math.pi/2,-math.pi/2,math.pi/4,-math.pi/4):
    vector=(direction[0]*math.cos(angle)-direction[1]*math.sin(angle),direction[0]*math.sin(angle)+direction[1]*math.cos(angle))
    for distance in (.8,1.1,1.4):
     q=(a[0]+vector[0]*distance,a[1]+vector[1]*distance)
     if r.via(cap,'GND',q,trial=True) and r.path(cap,'GND',[a,q],.4,layer,trial=True):
      r.via('local ground via '+cap,'GND',q);r.path('local ground '+cap,'GND',[a,q],.4,layer);done=True;break
    if done:break
  if not done:r.rows.append(dict(label='local ground '+cap,net='GND',routed=False,reason='No local ground landing'))
 local_complete=all(q['routed'] for q in r.rows)
 r.rows.extend(route(board,distribute_rails=True))
 connectivity=power_connectivity(board)
 return dict(placements=placements,anchors=anchors,routes=r.rows,local_preparation_complete=local_complete,
             power_connectivity=connectivity,complete=local_complete and all(not q['unconnected'] for q in connectivity),
             qualification='Pre-data engineering geometry. Exploratory failed routes remain recorded; completeness uses physical rail connectivity and all local bypass/ground seeds. Native DRC, manufacturer review and actual power/USB qualification remain required.')

class PowerFixer(USB3Fixer):
 strict_data_spacing=False
 data_escape_regions=()
 def __init__(self,board):
  super().__init__(board);self.pad_bins={};self.via_bins={}
  reservation=json.loads(Path(__file__).with_name('usb_child_arrival_reservation.json').read_text())
  self.child_arrival=reservation['legs']
  #Footprints are fixed in this stage. Index their complete pad bounds,
  #including same-net lands excluded by the ordinary foreign-copper index.
  for f in board.GetFootprints():
   for pad in f.Pads():
    bb=pad.GetBoundingBox()
    for ix in range(math.floor(p.ToMM(bb.GetLeft())/2),math.floor(p.ToMM(bb.GetRight())/2)+1):
     for iy in range(math.floor(p.ToMM(bb.GetTop())/2),math.floor(p.ToMM(bb.GetBottom())/2)+1):self.pad_bins.setdefault((ix,iy),[]).append(pad)
  for t in board.GetTracks():
   if isinstance(t,p.PCB_VIA):self._index_via(t)
   else:assert t.GetLayer() not in (p.In1_Cu,p.In2_Cu),'This stage expects inner ground planes, not inner-layer signal tracks'
 def _index_via(self,via):
  x,y=xy(via);self.via_bins.setdefault((math.floor(x/2),math.floor(y/2)),[]).append(via)
 def nearby(self,index,x,y):
  return {item.m_Uuid.AsString():item for ix in range(math.floor((x-2)/2),math.floor((x+2)/2)+1) for iy in range(math.floor((y-2)/2),math.floor((y+2)/2)+1) for item in index.get((ix,iy),[])}.values()
 def add_via(self,net,x,y):
  before={t.m_Uuid.AsString() for t in self.b.GetTracks() if isinstance(t,p.PCB_VIA)}
  super().add_via(net,x,y)
  for t in self.b.GetTracks():
   if isinstance(t,p.PCB_VIA) and t.m_Uuid.AsString() not in before:self._index_via(t)
 def free(self,layer,net,x,y,r):
  if layer==p.B_Cu and net!='GND':
   for leg in self.child_arrival:
    for a,b in zip(leg['points_mm'],leg['points_mm'][1:]):
     v=(b[0]-a[0],b[1]-a[1]);length=v[0]**2+v[1]**2;t=max(0,min(1,((x-a[0])*v[0]+(y-a[1])*v[1])/length));closest=(a[0]+t*v[0],a[1]+t*v[1])
     package_escape=net in ('+1V2_USB','+3V3_USB') and all(58.5<=q[0]<=71.5 and 50.5<=q[1]<=63.5 for q in ((x,y),closest))
     clearance=.205 if package_escape else .767
     if math.dist((x,y),closest)<r+leg['width_mm']/2+clearance:return False
  if not super().free(layer,net,x,y,r):return False
  if not self.strict_data_spacing or any(math.dist((x,y),q)<rad for q,rad in self.data_escape_regions):return True
  pt=vec((x,y))
  for item in self._items(layer,net,x,y,r+3):
   name=item.GetNetname()
   spacing=.762 if name in DATA_NETS else 1.27 if name in ('HUB_XI','HUB_XO') else 0
   if spacing:
    #Match the independent saved-copper auditor's conservative pad bounds.
    #Native rounded-land HitTest alone can accept a corner that its
    #bounding-edge isolation screen correctly leaves for review.
    if isinstance(item,p.PAD):
     bb=item.GetBoundingBox();left,top,right,bottom=[p.ToMM(q) for q in (bb.GetLeft(),bb.GetTop(),bb.GetRight(),bb.GetBottom())]
     if math.hypot(max(left-x,0,x-right),max(top-y,0,y-bottom))<r+spacing+.005:return False
    elif item.HitTest(pt,p.FromMM(r+spacing+.005)):return False
  return True
 def via_ok(self,net,x,y):
  for via in self.nearby(self.via_bins,x,y):
   d=math.dist((x,y),xy(via))
   if d<1e-6 and via.GetNetname()==net:return True
   if d<(fixer.VIA_DR+p.ToMM(via.GetDrillValue()))/2+.25-1e-6:return False
  if not all(self.free(ly,net,x,y,fixer.VIA_D/2) for ly in (p.F_Cu,p.B_Cu)):return False
  pt=vec((x,y))
  for pad in self.nearby(self.pad_bins,x,y):
   if not pad.GetDrillSize().x and pad.HitTest(pt,p.FromMM(fixer.VIA_D/2+.10)):return False
   if pad.GetDrillSize().x and math.dist((x,y),xy(pad))<max(p.ToMM(pad.GetDrillSize().x),p.ToMM(pad.GetDrillSize().y))/2+fixer.VIA_DR/2+.45-1e-6:return False
  return True

class Power:
 def __init__(self,board):
  self.b=board;self.fx=PowerFixer(board);self.rows=[]
  fixer.CLR=.20
 def pad(self,ref,num):
  return next(q for q in self.b.FindFootprintByReference(ref).Pads() if q.GetNumber()==str(num))
 def path(self,label,net,points,width,layer='F',trial=False):
  ly=p.F_Cu if layer=='F' else p.B_Cu;blocked=[]
  for a,b in zip(points,points[1:]):
   count=max(1,math.ceil(math.dist(a,b)/.04))
   for i in range(count+1):
    f=i/count;q=(a[0]+f*(b[0]-a[0]),a[1]+f*(b[1]-a[1]))
    if not self.fx.free(ly,net,*q,width/2):blocked.append(q);break
  if trial:return not blocked
  row=dict(label=label,net=net,layer=layer,width_mm=width,points=points,routed=not blocked,blocked_points=blocked)
  self.rows.append(row)
  if blocked:return False
  self.fx.add_track(net,points,width,ly);return True
 def maze(self,label,net,start,end,width,layer='B',escape_regions=(),allow_layer_changes=False):
  print(label,flush=True)
  nodes=[q for f in self.b.GetFootprints() for q in f.Pads() if q.GetNetname()==net]+[q for q in self.b.GetTracks() if isinstance(q,p.PCB_VIA) and q.GetNetname()==net]
  a=next((q for q in nodes if math.dist(xy(q),start)<1e-5),None);b=next((q for q in nodes if math.dist(xy(q),end)<1e-5),None)
  if a is not None and b is not None and self.connected(a,b):
   self.rows.append(dict(label=label,net=net,routed=True,already_physically_connected=True));return True
  before={str(t.m_Uuid.AsString()) for t in self.b.GetTracks()};self.fx.strict_data_spacing=True;self.fx.data_escape_regions=escape_regions;old_clr=fixer.CLR;fixer.CLR=.22
  try:okay=self.fx.route(net,start,end,w=width,step=.16,win=4,layers=(layer,'F' if layer=='B' else 'B') if allow_layer_changes else (layer,))
  finally:self.fx.strict_data_spacing=False;self.fx.data_escape_regions=();fixer.CLR=old_clr
  tracks=[t for t in self.b.GetTracks() if str(t.m_Uuid.AsString()) not in before]
  self.rows.append(dict(label=label,net=net,routed=okay,width_mm=width,layer=layer,layer_changes_allowed=allow_layer_changes,minimum_foreign_data_spacing_mm=.762,minimum_clock_spacing_mm=1.27,package_escape_regions=escape_regions,segments=[dict(start=tuple(p.ToMM(t.GetStart())),end=tuple(p.ToMM(t.GetEnd())),layer=self.b.GetLayerName(t.GetLayer())) for t in tracks]))
  return okay
 def via(self,label,net,q,diameter=.6,drill=.3,trial=False):
  old=fixer.VIA_D,fixer.VIA_DR;fixer.VIA_D,fixer.VIA_DR=diameter,drill
  try:
   existing=next((t for t in self.b.GetTracks() if isinstance(t,p.PCB_VIA) and math.dist(xy(t),q)<1e-6 and t.GetNetname()==net),None)
   okay=bool(existing) or self.fx.via_ok(net,*q)
   #The normal copper checker ignores same-net copper. Drill collisions and
   #ordinary component-hole spacing must still be checked independently.
   for f in self.b.GetFootprints():
    for pad in f.Pads():
     d=pad.GetDrillSize()
     if d.x and math.dist(xy(pad),q)<max(p.ToMM(d.x),p.ToMM(d.y))/2+drill/2+.45-1e-6:okay=False
   #Keep all new powervias outside every SMD solderland, including same-net.
   pt=vec(q)
   for f in self.b.GetFootprints():
    for pad in f.Pads():
     if not pad.GetDrillSize().x and pad.HitTest(pt,p.FromMM(diameter/2+.10)):okay=False
   if trial:return okay
   self.rows.append(dict(label=label,net=net,via_mm=q,diameter_mm=diameter,drill_mm=drill,routed=okay))
   if okay and not existing:self.fx.add_via(net,*q)
   return okay
  finally:fixer.VIA_D,fixer.VIA_DR=old
 def connected(self,a,b):
  return b.m_Uuid.AsString() in self.connected_ids(a)
 def connected_ids(self,a):
  cn=self.b.GetConnectivity();cn.Build(self.b);seen=set();queue=[a]
  while queue:
   item=queue.pop();key=item.m_Uuid.AsString()
   if key in seen:continue
   seen.add(key)
   queue.extend(q for q in list(cn.GetConnectedTracks(item))+list(cn.GetConnectedPads(item)) if q.GetNetname()==a.GetNetname())
  return seen
 def local_feed(self,net,root,pad,regions):
  connected=self.connected_ids(root);a=xy(pad)
  candidates=[q for f in self.b.GetFootprints() if f.GetReference().startswith(('C','L')) for q in f.Pads() if q.GetNetname()==net and q.m_Uuid.AsString() in connected and .001<math.dist(a,xy(q))<=4]
  fine=min(p.ToMM(pad.GetSize().x),p.ToMM(pad.GetSize().y))<.4
  low_current=pad.GetParent().GetReference() in ('U510','U512') and pad.GetNumber() in ('1','3')
  width=.17 if fine or low_current else .4
  for cap in sorted(candidates,key=lambda q:math.dist(a,xy(q)))[:3]:
   if self.maze(net+' local feed '+pad.GetParent().GetReference()+'.'+pad.GetNumber(),net,xy(cap),a,width,'F',regions):return True
  return False
 def distribute(self,net,root_ref,root_pin,source_via,width):
  root=self.pad(root_ref,root_pin)
  if not self.via(net+' source landing',net,source_via):return
  if not self.path(net+' source fanout',net,[xy(root),source_via],width):return
  connected=self.connected_ids(root)
  anchors=[source_via]+[xy(t) for t in self.b.GetTracks() if isinstance(t,p.PCB_VIA) and t.GetNetname()==net and t.m_Uuid.AsString() in connected and p.ToMM(t.GetWidth())>=.399]
  anchors.extend(xy(q) for f in self.b.GetFootprints() if f.GetReference().startswith('C') and f.GetReference()!='C521' and f.IsFlipped() for q in f.Pads() if q.GetNetname()==net and q.m_Uuid.AsString() in connected)
  targets=[pad for f in self.b.GetFootprints() for pad in f.Pads() if pad.GetNetname()==net]
  #Feed the individual hub I/O supply before adjacent core-rail copper
  #can enclose its small backside bypass. Other targets follow distance.
  targets.sort(key=lambda pad:(0 if pad.GetParent().GetReference()=='C521' else 1,math.dist(xy(pad),source_via)))
  regions=[(xy(self.b.FindFootprintByReference(ref)),rad) for ref,rad in [('U500',5.5),('U501',4),('U503',4)]]
  for pad in targets:
   if self.connected(root,pad):continue
   #A local preseed already joins the ICpin, its capacitor and a landing.
   #Feed that established cluster rather than inventing a second escape.
   group=self.connected_ids(pad)
   back_caps=[q for f in self.b.GetFootprints() if f.GetReference().startswith('C') and f.IsFlipped() for q in f.Pads() if q.GetNetname()==net and q.m_Uuid.AsString() in group]
   landings=[t for t in self.b.GetTracks() if isinstance(t,p.PCB_VIA) and t.GetNetname()==net and t.m_Uuid.AsString() in group and p.ToMM(t.GetWidth())>=.399]
   endpoints=[xy(q) for q in back_caps] or [xy(q) for q in landings]
   if endpoints:
    start,end=min(((a,c) for a in anchors for c in endpoints),key=lambda z:math.dist(*z))
    individual_io_pin=any(q.GetParent().GetReference()=='C521' for q in back_caps)
    low_current_strap=pad.GetParent().GetReference()=='R509'
    feed_width=.17 if low_current_strap else .2 if individual_io_pin else width
    if self.maze(net+' local-cluster feed '+pad.GetParent().GetReference()+'.'+pad.GetNumber(),net,start,end,feed_width,'B',regions,True):
     if not individual_io_pin and not low_current_strap:anchors.append(end)
     continue
   if self.local_feed(net,root,pad,regions):continue
   name=pad.GetParent().GetReference()+'.'+pad.GetNumber();a=xy(pad);centre=xy(pad.GetParent());dx,dy=a[0]-centre[0],a[1]-centre[1]
   outward=(math.copysign(1,dx),0) if abs(dx)>abs(dy) else (0,math.copysign(1,dy))
   if pad.GetDrillSize().x:
    start=min(anchors,key=lambda q:math.dist(q,a))
    if self.maze(net+' distribution '+name,net,start,a,width,'B',regions,True):anchors.append(a)
    continue
   fine=min(p.ToMM(pad.GetSize().x),p.ToMM(pad.GetSize().y))<.4;stub=.17 if fine else .4;diameter,drill=(.25,.15) if fine else (.6,.3)
   candidate=None
   for angle in (0,math.pi/4,-math.pi/4,math.pi/2,-math.pi/2):
    direction=(outward[0]*math.cos(angle)-outward[1]*math.sin(angle),outward[0]*math.sin(angle)+outward[1]*math.cos(angle))
    for distance in (.8,1.1,1.4,1.7,2):
     q=(a[0]+direction[0]*distance,a[1]+direction[1]*distance)
     if self.via(name,net,q,diameter,drill,trial=True) and self.path(name,net,[a,q],stub,trial=True):candidate=q;break
    if candidate is not None:break
   if candidate is None:
    self.rows.append(dict(label=net+' pad escape '+name,net=net,routed=False,reason='No legal short outward pad escape/via'));continue
   self.via(net+' landing '+name,net,candidate,diameter,drill);self.path(net+' pad escape '+name,net,[a,candidate],stub)
   start=min(anchors,key=lambda q:math.dist(q,candidate))
   if self.maze(net+' distribution '+name,net,start,candidate,width,'B',regions,True) and not fine:anchors.append(candidate)
  #A later nearby bypass may provide the short local feed that was not yet
  #available on the first pass. Do not force a separate via at every ICpin.
  for pad in targets:
   if not self.connected(root,pad):self.local_feed(net,root,pad,regions)

def route(board,distribute_rails=True):
 r=Power(board)
 #Input landing: broad cap connection and a6-via adjacent array. These vias
 #are outside the POSCAP solderland; no filled/capped via-in-pad is assumed.
 source=xy(r.pad('C546',1));assert r.pad('C546',1).GetNetname()=='+5_USB_RAW'
 assert math.dist(source,(79.95,90))<.01,('unexpected placement',source)
 r.path('raw landing','+5_USB_RAW',[source,(77.1,90)],1.5)
 for col,x in enumerate((77.1,78.0)):
  for row,y in enumerate((89.2,90,90.8)):
   if r.via(f'raw input stitch{col}/{row}','+5_USB_RAW',(x,y)):
    r.path(f'raw stitch fanout{col}/{row}','+5_USB_RAW',[(77.1,90),(x,y)],.6)
 spine=[(78,90),(78.1,88),(78.1,83.675),(79.95,83.675)]
 r.path('raw camera spine','+5_USB_RAW',spine,1.5,'B')
 for num in ('2','4'):
  a=xy(r.pad('U502',num));q=(79.95,a[1])
  if r.via('camera parallel input via'+num,'+5_USB_RAW',q,.4,.15):
   r.path('camera parallel input F'+num,'+5_USB_RAW',[a,q],.20)
   r.path('camera parallel input B'+num,'+5_USB_RAW',[q,(79.95,83.675)],.4,'B')
 #Only the microphone's <=900mA branch continues across the cell, so it
 #does not inherit the camera/main landing's6A trunk width.
 mic_via=(131.4,75.5)
 mic_landing=r.via('microphone input landing','+5_USB_RAW',mic_via)
 #Three camera input contacts: short parallel package escapes into the bus.
 for num in ('2','3','4'):
  q=xy(r.pad('U502',num));r.path('camera input'+num,'+5_USB_RAW',[(79.3,q[1]),q],.20)
 q=xy(r.pad('U504',1));mic_cap=xy(r.pad('C547',1))
 if math.dist(mic_cap,(129.775,75.5))<.01:
  r.path('microphone input bypass','+5_USB_RAW',[mic_via,mic_cap],.6)
  r.path('microphone input','+5_USB_RAW',[mic_cap,(129.775,76.4),(q[0],77.1),q],.30)
 else:r.rows.append(dict(label='microphone input placement',routed=False,expected_cap1=(129.775,75.5),actual_cap1=mic_cap))
 #Two parallel camera switch output escapes, each to a non-pad throughvia.
 output_vias=[]
 for num,q in [('14',(84.5,83.75)),('15',(84.5,82.75))]:
  a=xy(r.pad('U502',num));assert r.pad('U502',num).GetNetname()=='CAM_VBUS'
  if r.via('camera output via'+num,'CAM_VBUS',q,.56,.30):
   r.path('camera output'+num,'CAM_VBUS',[a,(84.0,a[1]),q],.25)
   output_vias.append(q)
 bus=[(89,86.3),(89,94.9),(77.5,94.9)]
 r.path('camera3A bottom spine','CAM_VBUS',bus,2,'B')
 r.path('camera connector shoulder','CAM_VBUS',[(77.5,94.9),(68.5,94.9)],1.5,'B')
 for q in output_vias:r.path('camera via escape','CAM_VBUS',[q,(85.5,q[1]),(85.5,86.3)],.56,'B')
 r.path('camera bottom shoulder','CAM_VBUS',[(85.5,86.3),(89,86.3)],1.5,'B')
 for cap in ('C544','C545'):r.path('camera output bypass '+cap,'CAM_VBUS',[xy(r.pad(cap,1)),(xy(r.pad(cap,1))[0],94.9)],.6,'B')
 #Connector power lands use the same between-row throughvia process as its
 #data escape. Local VBUS feed geometry is checked from actual pad positions.
 for num in ('B4','B9','A9','A4'):
  #.59mm toward the inter-row gap retains .20mm foreign copper clearance
  #where a .65mm launch would leave only .191mm to the adjacent A contact.
  pad=r.pad('J501',num);a=xy(pad);q=(a[0],a[1]-(.59 if num.startswith('B') else 1.20))
  if r.via('camera connector power'+num,'CAM_VBUS',q,.25,.15):
   r.path('camera inner-row power'+num,'CAM_VBUS',[a,q],.17)
   #Each A and B contact has its own via; an F.Cu cross-row merge would
   #thread between data escapevias with less than .20mm clearance.
   bx=xy(r.pad('J501',{'A9':'B4','A4':'B9'}.get(num,num)))[0]
   feed=[q,(bx,q[1]+.65),(bx,94.9)] if num.startswith('A') else [q,(bx,94.9)]
   r.path('camera connector bottom feed'+num,'CAM_VBUS',feed,.30,'B')
 #Compact local buck switching/filter geometry. Output capacitors receive
 #the load rail from the inductor before distribution to remote bypasses.
 for uref,lref,crefs in [('U510','L501',('C503','C504')),('U511','L502',('C507','C508'))]:
  sw=xy(r.pad(uref,3));l_in=xy(r.pad(lref,1));l_out=xy(r.pad(lref,2));net=r.pad(lref,1).GetNetname()
  neck=(sw[0]-1.15,sw[1]);r.path(uref+' switch escape',net,[sw,neck],.35)
  r.path(uref+' switch to inductor',net,[neck,l_in],.8)
  net=r.pad(lref,2).GetNetname()
  cap0,cap1=(xy(r.pad(ref,1)) for ref in crefs)
  tap=(cap0[0],l_out[1])
  r.path(uref+' output filter',net,[l_out,tap],1)
  r.path(uref+' output capacitors',net,[cap0,tap,cap1],1)
 #Low-current enable/sense/strap pins get explicit local escapes. They
 #must not be mistaken for high-current supply trunks of the same net.
 if distribute_rails:
  en=xy(r.pad('U510',1));vin=xy(r.pad('U510',4))
  r.path('core regulator hardware enable','+5_USB_RAW',[en,(en[0],en[1]-.85),(vin[0]+.95,en[1]-.85),(vin[0]+.95,vin[1]),vin],.17)
  sense=xy(r.pad('U513',5));strap=xy(r.pad('R509',1))
  for ref,pin,q in [('U513',5,(sense[0]+1.0125,sense[1])),('R516',1,(77,51.3)),('R509',1,(strap[0],strap[1]-1.1))]:
   pad=r.pad(ref,pin);net=pad.GetNetname()
   if r.via('supply sense landing '+ref,net,q,.4,.15):r.path('supply sense escape '+ref,net,[xy(pad),q],.17)
 #Mic output is a separately switched <=900mA port; its local bulk is not
 #placed on the camera branch or on upstream hostVBUS.
 mic_out=(132.7,78.8);mic_bulk=xy(r.pad('C550',1))
 mic_output_landing=r.via('microphone output landing','MIC_VBUS',mic_out)
 if mic_output_landing:
  r.path('microphone output escape','MIC_VBUS',[xy(r.pad('U504',6)),(132.0,78.4),mic_out],.35)
 if mic_output_landing:r.maze('microphone switch to bulk','MIC_VBUS',mic_out,mic_bulk,.8,'B')
 port=xy(r.pad('J502',1));r.maze('microphone bulk to port','MIC_VBUS',mic_bulk,port,.8,'B',[(port,2)])
 r.path('battery expansion switched power','BMS_USB_VBUS',[xy(r.pad('U505',6)),(50.7,21.05),(52.2,18),xy(r.pad('J505',1))],.5)
 #The camera's higher-current geometry is reserved first. The later small
 #branch must find a legal path around it while keeping SS/clock separation.
 if mic_landing:r.maze('raw microphone branch','+5_USB_RAW',(78,90),mic_via,.6,'B')
 if distribute_rails:
  r.distribute('+5_USB_RAW','C546',1,(78,90),.6)
  r.distribute('+3V3_USB','L502',2,(106.775,35),.4)
  r.distribute('+1V2_USB','L501',2,(106.775,22),.4)
  #Revisit still-isolated local clusters using all newly connected rail
  #landings; a useful approach may be available from the opposite side.
  r.distribute('+1V2_USB','L501',2,(106.775,22),.4)
  r.distribute('+3V3_USB','L502',2,(106.775,35),.4)
 return r.rows

def power_connectivity(board):
 physical=Power(board);connectivity=[]
 for net,ref,pin in [('+5_USB_RAW','C546',1),('+1V2_USB','L501',2),('+3V3_USB','L502',2),('CAM_VBUS','U502',14),('MIC_VBUS','U504',6),('BMS_USB_VBUS','U505',6),('U510_SW','U510',3),('U511_SW','U511',3)]:
  connected=physical.connected_ids(physical.pad(ref,pin));pads=[q for f in board.GetFootprints() for q in f.Pads() if q.GetNetname()==net]
  connectivity.append(dict(net=net,root=f'{ref}.{pin}',pads=len(pads),unconnected=[q.GetParent().GetReference()+'.'+q.GetNumber() for q in pads if q.m_Uuid.AsString() not in connected]))
 return connectivity

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--report',type=Path);args=parser.parse_args()
 assert args.input.resolve()!=args.output.resolve(),'Preserve the input snapshot'
 board=p.LoadBoard(str(args.input));connectivity=power_connectivity(board)
 already_connected=all(not q['unconnected'] for q in connectivity)
 rows=[] if already_connected else route(board)
 connectivity=power_connectivity(board)
 args.output.parent.mkdir(parents=True,exist_ok=True)
 if already_connected:shutil.copyfile(args.input,args.output)
 else:p.SaveBoard(str(args.output),board)
 for suffix in ('.kicad_pro','.kicad_dru'):
  source=args.input.with_suffix(suffix)
  if not source.exists():source=Path(__file__).resolve().parents[2]/('revisions/usb3-front-end/kicad/usb3_frontend'+suffix)
  if source.exists():shutil.copyfile(source,args.output.with_suffix(suffix))
 report=dict(status='POWER_CONNECTED' if all(not x['unconnected'] for x in connectivity) else 'INCOMPLETE',already_connected=already_connected,input=str(args.input),output=str(args.output),input_sha256=hashlib.sha256(args.input.read_bytes()).hexdigest(),output_sha256=hashlib.sha256(args.output.read_bytes()).hexdigest(),power_connectivity=connectivity,routes=rows,qualification='Development power-routing stage only, not a cell release. Failed exploratory attempts remain recorded even when later local feeds close the circuit. Native DRC, independent reference/spacing inspection, voltage drop, temperature and port compliance remain required.')
 path=args.report or args.output.with_suffix('.power.json');path.write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(dict(status=report['status'],routes=len(rows),power_unconnected=[x for x in connectivity if x['unconnected']],failed_attempts=[x['label'] for x in rows if not x['routed']],report=str(path)),indent=2))

if __name__=='__main__':main()
