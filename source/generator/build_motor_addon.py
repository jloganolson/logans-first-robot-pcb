"""Reuse the reviewed Thor switching cell; place and route the motor companion.

This produces an engineering candidate, never a release merely by generation.
Native DRC and the independent inventory/calculation checks are separate steps.
"""
import os, re, json, math, shutil
from pathlib import Path
import pcbnew as p
from cells import Board
from indexed_fixer import IndexedFixer
from motor_addon import PARTS, MOUNTING_HOLES_MM

root=Path(__file__).resolve().parents[2]
dest=root/'revisions/motor-addon/kicad'
dest.mkdir(parents=True,exist_ok=True)
b=p.LoadBoard(str(root/'revisions/v0.6/kicad/robot_pdb.kicad_pcb'))
g=Board.__new__(Board); g.b=b; g.nets={}; g.zones=[]; g.parts={s['ref']:s for s in PARTS}
dead=[]
def remove(x): dead.append(x); b.Remove(x)
def v(x,y): return p.VECTOR2I(p.FromMM(x),p.FromMM(y))
def inside(xy,box):
 x,y=xy; a,c,d,e=box; return a<=x<=d and c<=y<=e
thor_box=(35,0,73,82); ideal_box=(19,52,34,68)
thor={s['ref'] for s in PARTS if s['ref'] in {'U2','Q2','Q3','L1','D3','JP1','TP3','TP4','TP5'} or re.fullmatch(r'C(?:1[0-9]|2[0-7])|R(?:1[0-7]|19)',s['ref'])}
ideal={'U1','Q1','C1','C2'}
for f in list(b.GetFootprints()):
 r=f.GetReference()
 if r not in thor|ideal: remove(f)
 else: f.Move(v(-30,8) if r in thor else v(21,12))
for d in list(b.GetDrawings()): remove(d)
# Retain only complete local routes, not the original global supply system.
for t in list(b.GetTracks()):
 n=t.GetNetname(); pts=[p.ToMM(t.GetStart()),p.ToMM(t.GetEnd())]
 is_thor=all(inside(q,thor_box) for q in pts) and (n.startswith('T_') or n in ('GND','VIN','+24V'))
 is_ideal=all(inside(q,ideal_box) for q in pts) and n in ('GND','VIN','VBAT_L','U1_VCAP','Q1_G')
 if is_thor:
  # The previous RDS(on) ILIM and grounded feedback-bottom routes are replaced.
  if n=='T_SW' and any(math.dist(q,(57.175,26.9))<.02 for q in pts): remove(t); continue
  if n=='GND' and any(math.dist(q,(65.225,30.1))<.02 for q in pts): remove(t); continue
  t.Move(v(-30,8))
  xy=p.ToMM(t.GetPosition())
  if n=='GND' and t.GetClass()=='PCB_VIA' and inside(xy,(18.4,28.5,23,37.2)):remove(t)
  elif n=='VIN' and t.GetClass()=='PCB_VIA' and 41.9<xy[0]<42.3 and 41<xy[1]<45:remove(t)
  elif n=='T_SW' and any(math.dist(p.ToMM(pt),(24.6,34.9))<.02 for pt in (t.GetStart(),t.GetEnd())):remove(t)
  elif n=='T_SW' and any(math.dist(p.ToMM(pt),(23.6,37.6))<.02 for pt in (t.GetStart(),t.GetEnd())):remove(t)
 elif is_ideal:
  t.Move(v(21,12)); t.SetNet(g.net({'VBAT_L':'+24V','VIN':'MOTOR_BUS'}.get(n,n)))
 else: remove(t)
for z in list(b.Zones()):
 bb=z.GetBoundingBox(); bounds=(p.ToMM(bb.GetLeft()),p.ToMM(bb.GetTop()),p.ToMM(bb.GetRight()),p.ToMM(bb.GetBottom()))
 if z.GetNetname() in ('T_SW','+24V','VIN') and inside(bounds[:2],thor_box) and inside(bounds[2:],thor_box):z.Move(v(-30,8))
 else:remove(z)
fps={f.GetReference():f for f in b.GetFootprints()};g.fps=fps
positions={'R20':(36.3,43,0),'R21':(24.5,30,0),'C28':(42,55,0),
 'J1':(45,8,0),'D1':(56,20,0),'J2':(58,92,0),'J3':(79,92,0),'J4':(97,86,0),'J5':(55,27,0),
 'J6':(70,8,0),'J7':(84,8,0),'J8':(98,8,0),'R36':(81,19,0),'JP2':(87,19,0),
 'Q5':(47,32,0),'R35':(44,29,0),'R37':(43,32,0),'C42':(44,35,0),'D4':(48,36,0),
 'U3':(57,43,0),'C30':(62,39,0),'C31':(52,43,0),'U4':(69,38,0),'C32':(66,35,0),'C33':(72,35,0),
 'U5':(78,40,0),'R30':(78,35,0),'R31':(74,40,0),'R32':(78,45,0),'C34':(83,40,0),
 'U6':(91,41,0),'C35':(95,38,0),'C36':(95,43,0),'Q4':(97,55,0),'R33':(91,51,0),'R34':(91,57,0),'D2':(104,63,180),
 'C40':(69,70,0),'C41':(86,70,0),'TP1':(55,15,0),'TP2':(58,15,0),'TP6':(62,62,0),'TP7':(67,50,0),'TP8':(87,48,0),'TP9':(76,30,0)}
positions.update({r:(*xy,0) for r,xy in MOUNTING_HOLES_MM.items()})
for s in PARTS:
 r=s['ref']; lib,name=s['fp'].split(':')
 if r not in fps:
  directory=dest/(lib+'.pretty') if lib=='Robot_PDB' else Path(os.environ['KICAD7_FOOTPRINT_DIR'])/(lib+'.pretty')
  f=p.FootprintLoad(str(directory),name);assert f is not None,(r,s['fp']);b.Add(f);fps[r]=f
 f=fps[r];f.SetReference(r);f.SetValue(s['value']);f.SetFPID(p.LIB_ID(lib,name));f.Reference().SetLayer(p.F_Fab);f.Value().SetVisible(False)
 if r in positions:g.place(r,*positions[r])
 if s.get('dnp'):f.SetAttributes(f.GetAttributes()|p.FP_EXCLUDE_FROM_BOM|p.FP_EXCLUDE_FROM_POS_FILES)
 for pad in f.Pads():
  net=s['pins'].get(pad.GetNumber());pad.SetNet(g.net(net)) if net else pad.SetNetCode(0)
  pad.SetZoneConnection(p.ZONE_CONNECTION_FULL)
  # Stock NexFET footprint has unnumbered copper lobes physically contiguous
  # with its drain land; these are drain copper, not independent NC lands.
  if r=='Q4' and not pad.GetNumber() and pad.IsOnLayer(p.F_Cu):pad.SetNet(g.net('DUMP_LOW'))
g.outline(112,100)
def rect(n,ly,x1,y1,x2,y2,prio=5,clearance=.3,minw=.25):return g.zone(n,ly,[(x1,y1),(x2,y1),(x2,y2),(x1,y2)],prio,clearance,minw=minw)
rect('GND','In1',.5,.5,111.5,99.5,0)
rect('VIN','In2',.5,.5,111.5,99.5,0,.4)
for ly in ('F','B'):
 if ly=='B':rect('GND',ly,.5,.5,111.5,99.5,0)
 rect('VIN',ly,5,5,54.5,28,5,.5,.6)
 rect('+24V',ly,30,52,55,72,5,.4,.6)
 rect('MOTOR_BUS',ly,45,72,110,96,5,.5,.8)
 rect('MOTOR_BUS',ly,52,55,110,78,5,.5,.8)
 rect('DUMP_LOW',ly,95.9,52,101,90,9,.4,.8)
rect('M_SENSE','F',18,35.55,21.8,36.85,12,.22)
g.track('M_SENSE',[(19.6,36.1),(19.6,30),g.pad('R21','1')],1.4)
# ILIM sense touches the shunt pad independently, approaching from its right.
# It must not terminate at Q3 or parallel the load-current trace.
g.track('M_SENSE',[g.pad('R13','2'),(27.175,33.8),(24,33.8),(23.2,33),(23.2,30.6),(21.8,30.6),g.pad('R21','1')],.25)
# TI pin12 requires a direct reference to the grounded side of the shunt.
# Route on the back to keep it separate from the positive Kelvin trace.
g.track('GND',[g.pad('U2','12'),(28.1,36.8)],.3)
g.via('GND',28.1,36.8,.6,.3)
g.track('GND',[(28.1,36.8),(29.5,36.8),(29.5,30)],.5,'B')
g.via('GND',29.5,30,.8,.4)
g.track('GND',[(29.5,30),g.pad('R21','2')],.6)
g.track('MOTOR_BUS',[g.pad('J4','2'),(109.5,86),(109.5,59),(86,59),g.pad('C41','1')],2)
for t,x,y in [('MOTOR SUPPLY PROTOTYPE - NOT QUALIFIED',59,98),('22V34 BUCK / REGEN DUMP',73,24),('INPUT',48,4),('LEFT MOTOR',62,96),('RIGHT MOTOR',83,96),('BRAKE R',101,92),('THERMAL NC',58,24)]:g.text(t,x,y,.8)
sheet=(dest/'motor_supply.kicad_sch').read_text();ids={r:u for u,r in re.findall(r'\(uuid ([^)]*)\)\s+\(property "Reference" "([^"]+)"',sheet)}
assert set(ids)==set(fps),(set(ids)^set(fps))
for r,f in fps.items():f.SetPath(p.KIID_PATH('/'+ids[r]))
shutil.copyfile(root/'revisions/v0.6/kicad/robot_pdb.kicad_pro',dest/'motor_supply.kicad_pro')
libs=sorted({s['fp'].split(':')[0] for s in PARTS})
(dest/'fp-lib-table').write_text('(fp_lib_table\n'+''.join(f' (lib (name "{l}")(type "KiCad")(uri "'+('${KIPRJMOD}/Robot_PDB.pretty' if l=='Robot_PDB' else '${KICAD7_FOOTPRINT_DIR}/'+l+'.pretty')+'")(options "")(descr ""))\n' for l in libs)+')\n')
out=dest/'motor_supply.kicad_pcb';p.SaveBoard(str(out),b)
# Zones are withheld only while the geometric router finds candidate traces.
# Native refill and DRC below check every resulting trace against those zones.
zones=list(b.Zones())
for z in zones:b.Remove(z)
fx=IndexedFixer(b)
evidence=[]
def stitch(n,xy,d=.7,drill=.35):
 x,y=xy
 for f in b.GetFootprints():
  for pad in f.Pads():
   ds=p.ToMM(pad.GetDrillSize())
   if any(q.GetAttribute()==p.PAD_ATTRIB_SMD and q.GetNumber()==pad.GetNumber() and q.HitTest(pad.GetPosition()) for q in f.Pads()):continue
   if max(ds)>0 and math.dist(xy,p.ToMM(pad.GetPosition()))<(drill+max(ds))/2+.45:return False
 for t in b.GetTracks():
  if t.GetClass()=='PCB_VIA' and math.dist(xy,p.ToMM(t.GetPosition())) < (drill+p.ToMM(t.GetDrillValue()))/2+.25:return False
 if all(fx.free(L,n,x,y,d/2) for L in (p.F_Cu,p.In1_Cu,p.In2_Cu,p.B_Cu)):
  g.via(n,x,y,d,drill);fx._index=None;return True
 return False
for n,pts in [('VIN',[(x,y) for x in (12,14,16,18,20) for y in (10,12,14)]),('+24V',[(x,y) for x in (40,42,44,46,48,50) for y in (64,66)]),('MOTOR_BUS',[(x,y) for x in (48,49.2,50.4,51.6) for y in (75,76.2,77.4)]),('DUMP_LOW',[(x,y) for x in (97.5,98.7,99.9) for y in (57,59,61,80,82,84)]),('GND',[(60.8,y) for y in (18,20,22)]+[(x,y) for x in (93.2,94.2) for y in (53,54,55,56,57)])]:
 for xy in pts:stitch(n,xy)
for x in range(5,111,10):
 for y in range(5,100,10):stitch('GND',(x,y))
def route(n,a,c,w=.25):
 if math.dist(a,c)<.01:return True
 ok=fx.route(n,a,c,w=w,step=.15,win=4,layers=('F','B'))
 evidence.append({'net':n,'a':a,'b':c,'routed':bool(ok)})
 print('route',n,a,c,ok,flush=True);p.SaveBoard(str(out),b);return ok
# Explicit local top-side capacitor returns avoid isolated top-ground pockets.
# The uninterrupted L2 ground and bottom spreader remain the common return.
for f in fps.values():
 if f.GetReference() not in thor|ideal:continue
 for pad in f.Pads():
  if pad.GetNetname()!='GND' or pad.GetAttribute()!=p.PAD_ATTRIB_SMD:continue
  xy=p.ToMM(pad.GetPosition())
  vias=[t for t in b.GetTracks() if t.GetClass()=='PCB_VIA' and t.GetNetname()=='GND']
  target=min(vias,key=lambda t:math.dist(xy,p.ToMM(t.GetPosition())))
  route('GND',xy,p.ToMM(target.GetPosition()),.5 if f.GetReference() in {f'C{i}' for i in range(10,21)} else .25)
# Every surface ground gets a nearby plated return into the continuous ground plane.
for f in fps.values():
 for pad in f.Pads():
  if f.GetReference() in thor|ideal or pad.GetNetname()!='GND' or pad.GetAttribute()!=p.PAD_ATTRIB_SMD:continue
  xy=p.ToMM(pad.GetPosition());x,y=xy
  choices=[(x+dx,y+dy) for d in (.9,1.2,1.6,2) for dx,dy in ((d,0),(-d,0),(0,d),(0,-d))]
  for q in choices:
   if stitch('GND',q):
    if route('GND',xy,q,.25):break
power={'GND','VIN','+24V','MOTOR_BUS','DUMP_LOW'}
for n in sorted({q.GetNetname() for f in fps.values() for q in f.Pads()}-power):
 if not n or n.startswith('NC_'):continue
 if n=='M_SENSE':continue
 if n.startswith('T_') and n not in ('T_FB_BOTTOM','T_EN'):continue
 if n in ('U1_VCAP','Q1_G'):continue
 pads=[q for f in fps.values() for q in f.Pads() if q.GetNumber() and q.GetNetname()==n]
 if len(pads)<2:continue
 done=[pads.pop(0)]
 while pads:
  _,i,a=min((math.dist(p.ToMM(q.GetPosition()),p.ToMM(d.GetPosition())),i,d) for i,q in enumerate(pads) for d in done)
  c=pads.pop(i);route(n,p.ToMM(a.GetPosition()),p.ToMM(c.GetPosition()),.3 if n=='+5_DUMP' else .25);done.append(c)
route('VIN',g.pad('R35','1'),g.pad('J1','2'),.3)
for r,num in [('U3','5'),('U3','8'),('C30','1'),('R30','1')]:route('MOTOR_BUS',g.pad(r,num),g.pad('C40','1'),.4)
for z in zones:b.Add(z)
# The grid router can leave a zero-length layer-transition via on a pad,
# without any segment on the other layer. These two are unnecessary; the
# nearby GND transition also crowds C42's filtered base land.
for t in list(b.GetTracks()):
 if t.GetClass()!='PCB_VIA':continue
 xy=p.ToMM(t.GetPosition())
 if (t.GetNetname(),tuple(round(v,4) for v in xy)) in {('GND',(42.3,35.0)),('THERMAL_CONTACT',(42.3,32.2))}:
  assert not any(q.GetClass()!='PCB_VIA' and any(math.dist(p.ToMM(pt),xy)<.001 for pt in (q.GetStart(),q.GetEnd())) for q in b.GetTracks())
  remove(t)
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
p.WriteDRCReport(b,str(dest.parent/'drc.rpt'),p.EDA_UNITS_MILLIMETRES,True)
(dest.parent/'build-evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
print('Saved',out,'failed routes',sum(not q['routed'] for q in evidence))
