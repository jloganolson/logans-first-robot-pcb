"""Deterministic v0.6 candidate from frozen v0.5. Never alters v0.5."""
import os,re,shutil,json,math
from pathlib import Path
import pcbnew as pcb
from rev06 import PARTS
from cells import Board
from indexed_fixer import IndexedFixer
root=Path(__file__).resolve().parents[2];dest=root/'revisions/v0.6/kicad';dest.mkdir(parents=True,exist_ok=True)
b=pcb.LoadBoard(str(root/'revisions/v0.5/kicad/robot_pdb.kicad_pcb'))
g=Board.__new__(Board);g.b=b;g.nets={};g.zones=[]
fps={f.GetReference():f for f in b.GetFootprints()};spec={p['ref']:p for p in PARTS};dead=[]
def remove(x):dead.append(x);b.Remove(x)
def place(ref,x,y,rot=0):fps[ref].SetPosition(pcb.VECTOR2I(pcb.FromMM(x),pcb.FromMM(y)));fps[ref].SetOrientationDegrees(rot)
# Remove only explicitly replaced copper, retaining all unrelated small-signal routes.
rebuild={'PACK_A_POS','PACK_B_POS','VBAT','VMOT','VBAT_L'}
for z in list(b.Zones()):
 if z.GetNetname() in rebuild:remove(z)
for t in list(b.GetTracks()):
 n=t.GetNetname();x,y=pcb.ToMM(t.GetPosition());isvia=t.GetClass()=='PCB_VIA'
 if n in rebuild or n=='VBUS_IN':remove(t)
 elif n in ('GND','VIN') and x<25 and 35<y<52:remove(t)
 elif isvia and n=='GND' and abs(y-64)<.01 and 41.5<x<50:remove(t)
 elif n in ('DXL330_DATA','DXL430_DATA') and min(pcb.ToMM(t.GetStart())[1],pcb.ToMM(t.GetEnd())[1])>99 and x<170:remove(t)
# Replace the provisional switch by a wire port with the same four circuit identities.
remove(fps.pop('SW1'))
positions={'J5':(25,82.35,0),'F1':(14,7,-90),'F2':(27,47,90),'J2':(5.5,7,-90),
 'J1':(58,94,180),'J4':(79,94,180),'J301':(91.6,103,0),'J302':(110,103,0),
 'J401':(136.6,103,0),'J402':(154.5,103,0),'U18':(214,94,0),'C67':(219,94,90),'C68':(214,99,0)}
for ref,p in spec.items():
 old=fps.get(ref)
 if old is None or str(old.GetFPID().GetUniStringLibId())!=p['fp']:
  if old is not None:remove(old)
  lib,name=p['fp'].split(':');directory=dest/(lib+'.pretty') if lib=='Robot_PDB' else Path(os.environ['KICAD7_FOOTPRINT_DIR'])/(lib+'.pretty')
  f=pcb.FootprintLoad(str(directory),name);assert f is not None,(ref,p['fp']);b.Add(f);fps[ref]=f;f.SetReference(ref);f.SetFPID(pcb.LIB_ID(lib,name))
 if ref in positions:place(ref,*positions[ref])
 f=fps[ref];f.SetValue(p['value']);f.Value().SetVisible(False)
 if p['dnp']:f.SetAttributes(f.GetAttributes()|pcb.FP_EXCLUDE_FROM_BOM|pcb.FP_EXCLUDE_FROM_POS_FILES)
 for pad in f.Pads():
  n=p['pins'].get(pad.GetNumber(),'');pad.SetNet(g.net(n)) if n else pad.SetNetCode(0)
  if ref in ('J1','J2','J4','J5','F1','F2'):pad.SetZoneConnection(pcb.ZONE_CONNECTION_FULL)
place('C3',41,80);place('C4',41,92)
# Solid motor return; remove the old local ground-priority barrier near moved J3.
for p in fps['J2'].Pads():p.SetZoneConnection(pcb.ZONE_CONNECTION_FULL)
def pour(n,ly,pts,prio=8,clr=.6,mw=1):return g.zone(n,ly,pts,prio,clr,minw=mw)
a=[(7,95),(24,95),(45,83),(54,83),(54,97),(50,107),(7,107)]
c=[(25,95),(46,95),(67,88),(75.5,88),(75.5,98),(49,107),(25,107)]
pour('PACK_A_POS','B',a);pour('PACK_B_POS','F',c)
bus=[(18,3),(34,3),(34,40),(22,42),(22,62),(37,62),(37,73),(5,73),(5,40),(18,40)]
for ly in ('F','B'):pour('VBAT',ly,bus)
for ly in ('F','B'):
 pour('VMOT',ly,[(2,12),(10,3),(17,3),(17,12),(11,20),(2,20)])
 pour('VBAT_L',ly,[(19,51),(22,43),(35,43),(35,59),(24,59),(24,57),(19,57)])
# Bulk fanout on the moved capacitors; explicit top tracks to plated plane stitches.
for ref in ('C3','C4'):
 for p in fps[ref].Pads():
  x,y=pcb.ToMM(p.GetPosition());n=p.GetNetname()
  for dx in (-1.5,0,1.5):
   yy=y+(-2.6 if p.GetNumber()=='1' else 2.6)
   g.track(n,[(x,y),(x+dx,yy)],.55);g.via(n,x+dx,yy,d=.7,drill=.35)
# Via additions are collision-checked against pads and tracks on every copper layer.
fx=IndexedFixer(b)
def stitch(n,points,diam=.7,drill=.35):
 added=[]
 for x,y in points:
  if all(fx.free(L,n,x,y,diam/2) for L in (pcb.F_Cu,pcb.In1_Cu,pcb.In2_Cu,pcb.B_Cu)):
   g.via(n,x,y,diam,drill);fx._index=None;added.append((x,y))
 return added
stitches={}
stitches['VIN']=stitch('VIN',[(x,y) for x in (25.5,26.7,27.9,29.1,30.3,31.5) for y in (63,64.2,65.4)])
stitches['VBAT_L']=stitch('VBAT_L',[(x,y) for x in (27,28.2,29.4,30.6,31.8,33) for y in (53.8,55,56.2)])
stitches['GND_D1']=stitch('GND',[(x,y) for x in (12.3,13.5,14.7) for y in (52.3,56.7)])
# Shared bus layer transitions are explicit, independent of replaceable parts.
stitches['VBAT']=stitch('VBAT',[(x,y) for x in (8,10,12,14,16,18,20) for y in (64,66)])
stitches['VMOT']=stitch('VMOT',[(x,y) for x in (9,11,13,15) for y in (10,12)])
# Wider Thor output extension, keeping all ground-return planes intact.
pour('+24V','F',[(35.5,52),(40.4,52),(40.4,61.5),(50,61.5),(50,69),(35.5,69)],7)
# Extend rail pours to the new, split servo-chain outlets.
pour('+5V_SRV','B',[(89,98),(120,98),(120,107),(89,107)],6)
pour('+12V_SRV','B',[(134,98),(165,98),(165,107),(134,107)],6)
# Existing audio bridge supplemented with a wide bottom strip; zones avoid other nets.
pour('+12V_AUD','B',[(181,9),(187,9),(187,39),(181,39)],6,.35,.5)
stitches['AUDIO']=stitch('+12V_AUD',[(x,y) for x in (182.5,183.5,184.5,185.5) for y in (10.5,37.2)])
# Route changed low-speed/USB-power nets, then reconnect each new header data pin.
fx=IndexedFixer(b);route_results=[]
def route_tree(n,refs=None,w=.25):
 pads=[p for f in b.GetFootprints() for p in f.Pads() if p.GetNumber() and p.GetNetname()==n and (refs is None or f.GetReference() in refs)]
 if len(pads)<2:return
 done=[pads.pop(0)]
 while pads:
  _,i,p0=min(((math.dist(pcb.ToMM(a.GetPosition()),pcb.ToMM(p.GetPosition())),i,a) for i,p in enumerate(pads) for a in done), key=lambda q:(q[0],q[1]))
  p=pads.pop(i);start=pcb.ToMM(p0.GetPosition());end=pcb.ToMM(p.GetPosition())
  print('routing',n,p0.GetParent().GetReference(),p.GetParent().GetReference(),start,end,flush=True)
  ok=math.dist(start,end)<.01 or fx.route(n,start,end,w=w,step=.15,win=3,layers=('F','B'))
  route_results.append({'net':n,'from':p0.GetParent().GetReference()+'.'+p0.GetNumber(),'to':p.GetParent().GetReference()+'.'+p.GetNumber(),'routed':ok});done.append(p)
for n in ('VBUS_IN','USB_RAMPED','USB_SLEW_CT'):route_tree(n,w=.3)
route_tree('GND',{'U18','C67','C68'},.3)
# Ground pin reaches the ground plane at its own small stitch.
for ref,num in [('U18','2'),('C67','2'),('C68','2')]:
 p=next(p for p in fps[ref].Pads() if p.GetNumber()==num);x,y=pcb.ToMM(p.GetPosition())
 st=stitch('GND',[(x+dx,y+dy) for dx,dy in [(1.2,0),(-1.2,0),(0,1.3),(0,-1.3)]])
 if st:fx._index=None;fx.route('GND',(x,y),st[0],w=.3,step=.1,win=2)
for ref,n in [('J301','DXL330_DATA'),('J302','DXL330_DATA'),('J401','DXL430_DATA'),('J402','DXL430_DATA')]:
 p=next(p for p in fps[ref].Pads() if p.GetNumber()=='3');end=pcb.ToMM(p.GetPosition())
 anchors=[(pcb.ToMM(t.GetStart()),b.GetLayerName(t.GetLayer())) for t in b.GetTracks() if t.GetNetname()==n and t.GetClass()=='PCB_TRACK' and t.GetLayer() in (pcb.F_Cu,pcb.B_Cu)]
 anchors += [(pcb.ToMM(t.GetEnd()),b.GetLayerName(t.GetLayer())) for t in b.GetTracks() if t.GetNetname()==n and t.GetClass()=='PCB_TRACK' and t.GetLayer() in (pcb.F_Cu,pcb.B_Cu)]
 start,layer=min(anchors,key=lambda q:math.dist(q[0],end));print('header routing',ref,start,end,flush=True)
 ok=fx.route(n,start,end,w=.25,step=.15,win=3,layers=('F','B'));route_results.append({'net':n,'to':ref+'.3','routed':ok})
# Refresh labels; all component reference marks stay on fabrication layer to prevent silkscreen clutter.
for f in b.GetFootprints():f.Reference().SetLayer(pcb.F_Fab)
for d in list(b.GetDrawings()):
 if isinstance(d,pcb.PCB_TEXT):
  s=d.GetText()
  if 'ROBOT PDB' in s:d.SetText('ROBOT PDB v0.6 PROTOTYPE')
  elif s in ('PACK SWITCH','THOR 24V','XL330 5V','XL430 10.8V'):remove(d)
for s,x,y in [('EXTERNAL DPST - 12AWG',23,82),('STOP BEFORE OFF',23,85),('A IN',12,100),('A OUT',12,65),('B IN',33,100),('B OUT',33,65),('XL330 5V 2+2',104,97),('XL430 10.8V 2+1',150,97),('HAND SOLDER POWER WIRES / FUSES',22,76)]:g.text(s,x,y,.8)
shutil.copyfile(root/'revisions/v0.5/kicad/robot_pdb.kicad_pro',dest/'robot_pdb.kicad_pro')
libs=sorted({p['fp'].split(':')[0] for p in PARTS})
(dest/'fp-lib-table').write_text('(fp_lib_table\n'+''.join(f' (lib (name "{l}")(type "KiCad")(uri "'+('${KIPRJMOD}/Robot_PDB.pretty' if l=='Robot_PDB' else '${KICAD7_FOOTPRINT_DIR}/'+l+'.pretty')+'")(options "")(descr ""))\n' for l in libs)+')\n')
sheet=(dest/'robot_pdb.kicad_sch').read_text();symbols={ref:uid for uid,ref in re.findall(r'\(in_bom (?:yes|no)\) \(on_board yes\) \(dnp no\)\s+\(uuid ([^)]*)\)\s+\(property "Reference" "([^"]+)"',sheet)}
# DNP marks vary; match the UUID immediately preceding the Reference property.
symbols={ref:uid for uid,ref in re.findall(r'\(uuid ([^)]*)\)\s+\(property "Reference" "([^"]+)"',sheet)}
assert set(symbols)==set(fps),(set(symbols)^set(fps))
for r,f in fps.items():f.SetPath(pcb.KIID_PATH('/'+symbols[r]))
out=dest/'robot_pdb.kicad_pcb';pcb.SaveBoard(str(out),b)
pcb.ZONE_FILLER(b).Fill(b.Zones());pcb.SaveBoard(str(out),b);pcb.WriteDRCReport(b,str(dest.parent/'drc.rpt'),pcb.EDA_UNITS_MILLIMETRES,True)
(dest.parent/'build-evidence.json').write_text(json.dumps({'route_results':route_results,'added_stitches':stitches},indent=2)+'\n')
print('Saved',out,'routing failures',sum(not x['routed'] for x in route_results))
