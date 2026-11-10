"""Derive a USB power candidate from the routed, shunt-limited motor buck cell."""
import os,re,math,json,shutil
from pathlib import Path
import pcbnew as p
from cells import Board
from indexed_fixer import IndexedFixer
from usb_power import PARTS

root=Path(__file__).resolve().parents[2];dest=root/'revisions/usb-power/kicad';dest.mkdir(parents=True,exist_ok=True)
b=p.LoadBoard(str(root/'revisions/motor-addon/kicad/motor_supply.kicad_pcb'))
g=Board.__new__(Board);g.b=b;g.nets={};g.zones=[];dead=[]
spec={s['ref']:s for s in PARTS}
def rem(x):dead.append(x);b.Remove(x)
def point(x,y):return p.VECTOR2I(p.FromMM(x),p.FromMM(y))
def box(pts,x1,y1,x2,y2):return all(x1<=x<=x2 and y1<=y<=y2 for x,y in pts)
mapping={'+24V':'+5_USB_RAW','M_SENSE':'USB_SENSE'}
for f in list(b.GetFootprints()):
 if f.GetReference() not in spec:rem(f)
for d in list(b.GetDrawings()):rem(d)
for t in list(b.GetTracks()):
 n=t.GetNetname();pts=[p.ToMM(t.GetStart()),p.ToMM(t.GetEnd())]
 if n in ('T_FB_BOTTOM','T_FB','T_EN'):rem(t);continue
 if n in ('GND','VIN','+24V') and not box(pts,4,7,43.5,90):rem(t);continue
 if n=='GND' and (any(y>71 for x,y in pts) or any(math.dist(q,(37.125,43))<1.1 for q in pts)):rem(t);continue
 if n=='VIN' and any(x>35 and y>28 for x,y in pts):rem(t);continue
 if n not in ('GND','VIN','+24V','M_SENSE','D3_A') and not n.startswith('T_'):rem(t);continue
 # The upper feedback divider now has a7.5k series trim aboveFB.
 if n=='T_FB' and any(math.dist(x,(33.575,33.3))<.02 for x in pts):rem(t);continue
 t.SetNet(g.net(mapping.get(n,n)))
preserve=[]
for z in list(b.Zones()):
 bb=z.GetBoundingBox();pts=[p.ToMM(bb.GetPosition()),p.ToMM(bb.GetEnd())]
 if z.GetNetname()=='T_SW' or z.GetNetname()=='VIN' and z.GetLayer() in (p.F_Cu,p.B_Cu) and box(pts,0,0,60,100):preserve.append(z)
 else:rem(z)
fps={f.GetReference():f for f in b.GetFootprints()};g.fps=fps
positions={'R20':(36.3,43,0),'R22':(36.3,46,0),'J1':(45,8,0),'J2':(42,92,0),'D1':(51,20,0)}
for s in PARTS:
 r=s['ref'];lib,name=s['fp'].split(':')
 if r not in fps:
  directory=root/'revisions/v0.6/kicad/Robot_PDB.pretty' if lib=='Robot_PDB' else Path(os.environ['KICAD7_FOOTPRINT_DIR'])/(lib+'.pretty')
  f=p.FootprintLoad(str(directory),name);assert f is not None,(r,s['fp']);b.Add(f);fps[r]=f
 f=fps[r];f.SetReference(r);f.SetValue(s['value']);f.SetFPID(p.LIB_ID(lib,name));f.Reference().SetLayer(p.F_Fab);f.Value().SetVisible(False)
 if r in positions:g.place(r,*positions[r])
 if s.get('dnp'):f.SetAttributes(f.GetAttributes()|p.FP_EXCLUDE_FROM_BOM|p.FP_EXCLUDE_FROM_POS_FILES)
 for pad in f.Pads():
  n=s['pins'].get(pad.GetNumber());pad.SetNet(g.net(n)) if n else pad.SetNetCode(0);pad.SetZoneConnection(p.ZONE_CONNECTION_FULL)
g.outline(60,100)
for txt,x,y in [('USB POWER PROTOTYPE',30,96),('5V1 /8A TARGET UNQUALIFIED',30,98),('FUSED INPUT',48,4),('USB5V1',46,88)]:g.text(txt,x,y,.8)
def rect(n,ly,x1,y1,x2,y2,prio=0,clr=.3,mw=.25):return g.zone(n,ly,[(x1,y1),(x2,y1),(x2,y2),(x1,y2)],prio,clr,minw=mw)
rect('GND','In1',.5,.5,59.5,99.5)
rect('VIN','In2',.5,.5,59.5,99.5)
rect('GND','B',.5,.5,59.5,99.5)
for ly in ('F','B'):
 rect('VIN',ly,5,5,56,28,5,.5,.5)
 rect('+5_USB_RAW',ly,5,52,55,96,5,.4,.6)
rect('USB_SENSE','F',18,35.55,21.8,36.85,12,.22)
zones=list(b.Zones())
for z in zones:b.Remove(z)
fx=IndexedFixer(b);evidence=[]
def route(n,a,c,w=.25):
 ok=fx.route(n,a,c,w=w,step=.1,win=4,layers=('F','B'))
 evidence.append(dict(net=n,a=a,b=c,routed=bool(ok)));print(n,a,c,ok,flush=True);return ok
# Preserve the proven short feedback escape at the0.5mm-pitch controller.
g.track('T_FB',[(31.65,39.25),(32.6,39.25),(33.58,38.27)],.25)
fx._index=None
route('USB_FB_TOP',g.pad('R14','2'),g.pad('R20','1'))
for n in ('T_FB','T_EN'):
 pads=[q for f in fps.values() for q in f.Pads() if q.GetNumber() and q.GetNetname()==n and not(n=='T_FB' and f.GetReference()=='U2')]
 done=[pads.pop(0)]
 while pads:
  _,i,a=min((math.dist(p.ToMM(q.GetPosition()),p.ToMM(d.GetPosition())),i,d) for i,q in enumerate(pads) for d in done)
  c=pads.pop(i);route(n,p.ToMM(a.GetPosition()),p.ToMM(c.GetPosition()));done.append(c)
# Two stocked0.1%10k parts form the20k bottom divider.
route('USB_FB_BOTTOM',g.pad('R15','2'),g.pad('R22','1'))
g.via('GND',38.8,46,d=.7,drill=.35);fx._index=None
route('GND',g.pad('R22','2'),(38.8,46))
for r,num in [('D1','2')]:
 xy=g.pad(r,num);target=(xy[0],xy[1]+2.5)
 g.via('GND',*target,d=.8,drill=.4);fx._index=None;route('GND',xy,target,.6)
# Via arrays carry output to the lower-layer spreader and join input toIn2.
for n,pts in [('VIN',[(x,y) for x in (48,49.2,50.4,51.6) for y in (10,11.2,12.4)]),('+5_USB_RAW',[(x,y) for x in (38,39.2,40.4,41.6) for y in (82,83.2,84.4)])]:
 for x,y in pts:
  if n=='VIN' and (x,y)==(51.6,10):continue  # >=0.45mm drill gap to input port
  if all(fx.free(ly,n,x,y,.35) for ly in (p.F_Cu,p.In1_Cu,p.In2_Cu,p.B_Cu)):
   if any(t.GetClass()=='PCB_VIA' and math.dist((x,y),p.ToMM(t.GetPosition()))<.65 for t in b.GetTracks()):continue
   g.via(n,x,y,.7,.35);fx._index=None
for z in zones:b.Add(z)
sheet=(dest/'usb_power.kicad_sch').read_text();ids={r:u for u,r in re.findall(r'\(uuid ([^)]*)\)\s+\(property "Reference" "([^"]+)"',sheet)}
assert set(ids)==set(fps),(set(ids)^set(fps))
for r,f in fps.items():f.SetPath(p.KIID_PATH('/'+ids[r]))
(dest/'Robot_PDB.pretty').mkdir(exist_ok=True)
shutil.copyfile(root/'revisions/v0.6/kicad/Robot_PDB.pretty/Power_WirePort_P7.2mm.kicad_mod',dest/'Robot_PDB.pretty/Power_WirePort_P7.2mm.kicad_mod')
shutil.copyfile(root/'revisions/v0.6/kicad/robot_pdb.kicad_pro',dest/'usb_power.kicad_pro')
libs=sorted({s['fp'].split(':')[0] for s in PARTS})
(dest/'fp-lib-table').write_text('(fp_lib_table\n'+''.join(f' (lib (name "{l}")(type "KiCad")(uri "'+('${KIPRJMOD}/Robot_PDB.pretty' if l=='Robot_PDB' else '${KICAD7_FOOTPRINT_DIR}/'+l+'.pretty')+'")(options "")(descr ""))\n' for l in libs)+')\n')
out=dest/'usb_power.kicad_pcb';p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);b=p.LoadBoard(str(out));p.WriteDRCReport(b,str(dest.parent/'drc.rpt'),p.EDA_UNITS_MILLIMETRES,True)
(dest.parent/'build-evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
