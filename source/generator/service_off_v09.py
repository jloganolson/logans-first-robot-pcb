"""Optional local service OFF shunts. Never edits an existing PCB file.

Seven independent regulator EN inputs; shunt fitted = OFF. Existing solder
jumpers remain. Placement is anchored to their actual positions, not cell offsets.
Call add_headers only after all ordinary cell copper/components have been added.
Native DRC and physical access review remain required after final plane filling.
"""
import math,os
from pathlib import Path
import pcbnew as p
from indexed_fixer import IndexedFixer

FOOTPRINT='Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical'
# ref, existing solder-jumper reference, expected EN net, label
CONTROLS=[('J9921','JP1','T_EN','THOR'),('J9922','JP101','P_EN','PI'),
 ('J9923','JP201','O_EN','USB CONTROL'),('J9924','JP301','S_EN','XL330'),
 ('J9925','JP401','H_EN','XL430'),('J9926','JP501','A_EN','AUDIO AUX'),
('J9928','JP7101','IO_PWM_EN','MG90S')]
PARTS=[dict(ref=ref,sym='Connector_Generic:Conn_01x02',value=label+' OFF SHUNT',
 fp=FOOTPRINT,pins={'1':net,'2':'GND'},block='SERVICE. Optional local regulator OFF shunts',
 lcsc='',mpn='Optional hand-fit 2.54mm two-pin header and removable shunt',
 status='short=OFF; open=normal UVLO; no external voltage; optional service control, not protection',
 dnp=True,source_cell='service_off',source_ref=ref) for ref,jp,net,label in CONTROLS]
WIDTH_MM=.25
CLEARANCE_MM=.25
MAX_LINK_MM=10.
MAX_DISTANCE_FROM_JP_MM=8.
# Preferred (pin1 dx,dy,rotation) relative to the existing jumper centre.
# Verified against the actual base/motor/I/O cell copper on 2026-11-09.
LOCAL_PLACEMENTS={ref:((4.,2.,90.) if ref=='J9921' else
                       (0.,-3.5,270.) if ref in ('J9924','J9925') else (0.,3.5,90.))
                  for i,(ref,*_) in enumerate(CONTROLS)}
# Keep removed SWIG wrappers alive through the build, like the composition
# builder's dead-item list. They are not part of any exported board.
_RETIRED_ITEMS=[]

def vec(q):return p.VECTOR2I(p.FromMM(q[0]),p.FromMM(q[1]))
def xy(q):return tuple(p.ToMM(q))
def box(bb):return tuple(p.ToMM(v) for v in (bb.GetLeft(),bb.GetTop(),bb.GetRight(),bb.GetBottom()))
def pad(fp,n):return next(q for q in fp.Pads() if q.GetNumber()==str(n))
def overlap(a,b):return not(a[2]<b[0] or b[2]<a[0] or a[3]<b[1] or b[3]<a[1])

def courtyard(fp):
 items=[q for q in fp.GraphicalItems() if q.GetLayer()==p.F_CrtYd]
 if not items:return None
 bs=[box(q.GetBoundingBox()) for q in items]
 return min(q[0] for q in bs),min(q[1] for q in bs),max(q[2] for q in bs),max(q[3] for q in bs)

def free(index,net,q,radius,layers):
 """Conservative disk sweep against actual track/pad copper on named layers.

 Planes deliberately refill around new through-hole pads; their clearances are
 checked by final native DRC. Existing routed copper is never deleted.
 """
 pt=vec(q);acc=p.FromMM(radius+CLEARANCE_MM)
 bb=box(index.b.GetBoardEdgesBoundingBox())
 if not(bb[0]+radius+.5<q[0]<bb[2]-radius-.5 and bb[1]+radius+.5<q[1]<bb[3]-radius-.5):return False
 for layer in layers:
  for item in index._items(layer,net,*q,radius+CLEARANCE_MM+2):
   # Additional engineering keep-away from the switching phase node for EN.
   margin=max(CLEARANCE_MM,1.0) if net.endswith('_EN') and item.GetNetname().endswith('_SW') else CLEARANCE_MM
   if item.HitTest(pt,p.FromMM(radius+margin)):return False
 return True

def clear_path(index,net,points):
 if sum(math.dist(a,b) for a,b in zip(points,points[1:]))>MAX_LINK_MM:return False
 for a,b in zip(points,points[1:]):
  count=max(1,math.ceil(math.dist(a,b)/.04))
  for i in range(count+1):
   q=tuple(a[k]+(b[k]-a[k])*i/count for k in (0,1))
   if not free(index,net,q,WIDTH_MM/2,[p.F_Cu]):return False
 return True

def drill_clear(board,header):
 # Hole-to-hole spacing also applies to same-net copper, which the electrical
 # clearance sweep correctly excludes. This screen uses a0.30mm hole-edge gap.
 holes=[(xy(t.GetPosition()),p.ToMM(t.GetDrillValue())/2) for t in board.GetTracks() if t.GetClass()=='PCB_VIA']
 holes.extend((xy(q.GetPosition()),max(xy(q.GetDrillSize()))/2)
              for f in board.GetFootprints() for q in f.Pads() if q.GetDrillSize().x)
 return all(math.dist(xy(q.GetPosition()),c)>=p.ToMM(q.GetDrillSize().x)/2+r+.30
            for q in header.Pads() for c,r in holes)

def paths(a,b):
 # Direct or orthogonal short local routes. No vias or long maze detours.
 yield [a,b]
 yield [a,(a[0],b[1]),b]
 yield [a,(b[0],a[1]),b]

def candidate_positions(anchor):
 # Pin1, not body centre, is the placement anchor for this stock footprint.
 offsets=[(x*.5,y*.5) for x in range(-16,17) for y in range(-16,17)
          if 2.5<=math.hypot(x*.5,y*.5)<=MAX_DISTANCE_FROM_JP_MM]
 for dx,dy in sorted(offsets,key=lambda q:(math.hypot(*q),q)):
  for angle in (0,90,180,270):yield (anchor[0]+dx,anchor[1]+dy),angle

def add_headers(board,cell_offsets=None,placements=None):
 """Add eight optional headers and short EN/GND routes; return evidence rows.

 cell_offsets is accepted for integration-call compatibility but actual JP
 positions are authoritative. placements optionally maps header refs to absolute
 (pin1_x_mm,pin1_y_mm,rotation_deg); every supplied position is still checked.
 On failure, any additions made by this call are removed before raising.
 """
 del cell_offsets
 fp_root=Path(os.environ['KICAD7_FOOTPRINT_DIR'])
 footprints={f.GetReference():f for f in board.GetFootprints()}
 assert not any(ref in footprints for ref,*_ in CONTROLS),'Service headers already exist'
 for ref,jp,net,label in CONTROLS:
  assert jp in footprints,(ref,'missing existing OFF jumper',jp)
  assert pad(footprints[jp],1).GetNetname()==net,(ref,'unexpected EN net',jp)
  assert pad(footprints[jp],2).GetNetname()=='GND',(ref,'OFF jumper lacks GND',jp)
 added=[];evidence=[]
 try:
  for ref,jp,net,label in CONTROLS:
   anchor=footprints[jp];anchor_xy=xy(anchor.GetPosition());index=IndexedFixer(board)
   others=[courtyard(f) for f in board.GetFootprints() if f.GetLayer()==p.F_Cu]
   lib,name=FOOTPRINT.split(':');header=p.FootprintLoad(str(fp_root/(lib+'.pretty')),name)
   assert header is not None
   header.SetReference(ref);header.SetValue(label+' OFF SHUNT');header.SetFPID(p.LIB_ID(lib,name))
   header.Reference().SetLayer(p.F_Fab);header.Value().SetVisible(False)
   header.SetAttributes(header.GetAttributes()|p.FP_EXCLUDE_FROM_BOM|p.FP_EXCLUDE_FROM_POS_FILES)
   for pin,pnet in ((1,net),(2,'GND')):pad(header,pin).SetNet(board.FindNet(pnet))
   preferred=LOCAL_PLACEMENTS[ref]
   candidates=([(placements[ref][:2],placements[ref][2])] if placements and ref in placements else
    [(tuple(anchor_xy[k]+preferred[k] for k in (0,1)),preferred[2])]+list(candidate_positions(anchor_xy)))
   chosen=None
   for pos,angle in candidates:
    if math.dist(pos,anchor_xy)>MAX_DISTANCE_FROM_JP_MM:continue
    header.SetPosition(vec(pos));header.SetOrientationDegrees(angle)
    cb=courtyard(header)
    if any(q and overlap(cb,q) for q in others):continue
    if not drill_clear(board,header):continue
    # Circular envelopes also cover square pin1's corners and all copper layers.
    if not all(free(index,q.GetNetname(),xy(q.GetPosition()),math.hypot(*xy(q.GetSize()))/2,
                    [p.F_Cu,p.In1_Cu,p.In2_Cu,p.B_Cu]) for q in header.Pads()):continue
    # Include the other header pad in each route's foreign-net copper checks.
    board.Add(header);index=IndexedFixer(board)
    route=[]
    for pin,pnet in ((1,net),(2,'GND')):
     start=xy(pad(header,pin).GetPosition());end=xy(pad(anchor,pin).GetPosition())
     path=next((q for q in paths(start,end) if clear_path(index,pnet,q)),None)
     if path is None:break
     new=[]
     for a,b in zip(path,path[1:]):
      if math.dist(a,b)<1e-6:continue
      t=p.PCB_TRACK(board);t.SetStart(vec(a));t.SetEnd(vec(b));t.SetWidth(p.FromMM(WIDTH_MM));t.SetLayer(p.F_Cu);t.SetNet(board.FindNet(pnet));board.Add(t);new.append(t)
     route.append((pin,pnet,path,new));index=IndexedFixer(board)
    if len(route)==2:chosen=(pos,angle,route);break
    for pin,pnet,path,new in route:
     for t in new:board.Remove(t);_RETIRED_ITEMS.append(t)
    board.Remove(header);index=IndexedFixer(board)
   if chosen is None:raise RuntimeError((ref,'No verified short local header placement; review this cell manually'))
   pos,angle,route=chosen;added.append(header)
   for pin,pnet,path,new in route:added.extend(new)
   footprints[ref]=header
   evidence.append(dict(reference=ref,jumper=jp,net=net,label=label,pin1_mm=pos,rotation_deg=angle,
    relative_to_jumper_mm=[pos[k]-anchor_xy[k] for k in (0,1)],copper_clearance_screen_mm=CLEARANCE_MM,
    links=[dict(pin=pin,net=n,path_mm=q,length_mm=sum(math.dist(a,b) for a,b in zip(q,q[1:]))) for pin,n,q,_ in route],
    optional_manual_fit=True,final_native_drc_required=True))
  return evidence
 except Exception:
  for item in reversed(added):board.Remove(item);_RETIRED_ITEMS.append(item)
  raise
