"""Place and route the independent USB CAN/PWM prototype, preserving native DRC.

Run via source/fabrication/with_kicad.sh. No main or motor PCB is edited.
The output is an engineering prototype, with route failures/DRC recorded rather
than hidden. High-speed USB and buck qualification remain explicit bench gates.
"""
import os, re, json, math, shutil, signal
from pathlib import Path
import pcbnew as p
from cells import Board,tps_cell
from robot_io import PARTS,MOUNTING_HOLES_MM
from indexed_fixer import IndexedFixer
import fixer
fixer.CLR=.20  # Match the native0.20mm netclass rule; 1oz process required.

root=Path(__file__).resolve().parents[2]
dest=root/'revisions/robot-io/kicad';dest.mkdir(parents=True,exist_ok=True)
custom=dest/'Robot_PDB.pretty';custom.mkdir(exist_ok=True)
source=root/'revisions/motor-addon/kicad/Robot_PDB.pretty/Power_WirePort_P7.2mm.kicad_mod'
shutil.copy2(source,custom/source.name)
(dest/'fp-lib-table').write_text('(fp_lib_table\n'+''.join(f'(lib (name "{lib}")(type "KiCad")(uri "'+ ('${KIPRJMOD}/Robot_PDB.pretty' if lib=='Robot_PDB' else str(Path(os.environ['KICAD7_FOOTPRINT_DIR'])/(lib+'.pretty')))+'")(options "")(descr ""))\n' for lib in sorted({q['fp'].split(':')[0] for q in PARTS}))+')\n')
g=Board([q for q in PARTS if not q['fp'].startswith('Robot_PDB:')]);b=g.b
for s in PARTS:
 if not s['fp'].startswith('Robot_PDB:'):continue
 f=p.FootprintLoad(str(custom),s['fp'].split(':')[1]);assert f
 f.SetReference(s['ref']);f.SetValue(s['value']);f.SetFPID(p.LIB_ID('Robot_PDB',s['fp'].split(':')[1]));b.Add(f)
 g.fps[s['ref']]=f;g.parts[s['ref']]=s
 for pad in f.Pads():pad.SetNet(g.net(s['pins'][pad.GetNumber()]))
 f.SetAttributes(f.GetAttributes()|p.FP_EXCLUDE_FROM_BOM|p.FP_EXCLUDE_FROM_POS_FILES)
g.outline(112,100)
tps_cell(g,0,'V5_SERVO',20,35,label='SERVO 5V')
# The300R trim is in series with the top feedback resistor. Remove the inherited
# final FB segment into R101.2, which now belongs to PWM_FB_TOP.
q=g.pad('R101','2')
for t in list(b.GetTracks()):
 if t.GetNetname()=='PWM_FB' and any(math.dist(p.ToMM(v),q)<.01 for v in (t.GetStart(),t.GetEnd())):b.Remove(t)
pos={'R108':(26,47,0),'C111':(12,56,0),'C112':(35,10,0),'D1':(17,67,90),'J9':(9,77,90),
 'U4':(58,19,0),'C41':(54,15,0),'C42':(58,13,0),'R41':(65,20,90),'R42':(53,20,90),
 'J3':(47,8,90),'R43':(48,15,0),'JP1':(48,19,0),
 'D3':(52,51,0),'D4':(58,51,0),'R44':(52,48,90),'R45':(58,48,90),
 'U7':(70,65,0),'C43':(74,59,90),'Q1':(62,60,0),'R46':(66,60,90),'R47':(58,60,0),'R48':(58,64,0),'R49':(54,61,90),
 'J4':(26,70,90),'J5':(37,70,90),'J6':(48,70,90),
 'R51':(67,54,90),'R52':(71,54,90),'R53':(75,54,90),
 'R54':(67,72,90),'R55':(71,72,90),'R56':(75,72,90),
 'R57':(66,77,90),'R58':(71,77,90),'R59':(76,77,90),
 'TP1':(44,50,0),'TP2':(105,49,0),'TP3':(62,70,0),'TP4':(59,76,0)}
for prefix,ox,oy,cb,rb,mc,reg,esd,jusb,sw,yref,boot,reset in (
 ('CAN',64,35,1,1,'U1','U5','U8','J1','J7','Y1','JP2','JP4'),
 ('PWM',92,35,21,21,'U2','U6','U9','J2','J8','Y2','JP3','JP5')):
 pos.update({mc:(ox,oy,0),reg:(ox+8,oy-16,0),esd:(ox+10,oy,0),jusb:(ox+(11 if prefix=='CAN' else 9),oy-11,90),sw:((45 if prefix=='CAN' else 80),56,90),yref:(ox-10,oy-1,180),boot:((ox+3 if prefix=='CAN' else ox-1),(oy-11 if prefix=='CAN' else oy-14),0),reset:(ox-13,oy+10,0),
  f'C{cb}':(ox+12,oy-19,0),f'C{cb+1}':(ox+(7 if prefix=='CAN' else 5),oy-11,0),
  f'C{cb+2}':(ox-3,oy+8,90),f'C{cb+3}':(ox-1,oy-8,90),f'C{cb+4}':(ox+8,oy-4,0),
  f'R{rb}':((ox-13 if prefix=='CAN' else 80),(oy+4 if prefix=='CAN' else 50),0),f'C{cb+5}':(ox-7,oy+6,90),f'C{cb+6}':(ox-10,oy+6,90),
  f'C{cb+7}':(ox-6,oy+9.5,90),f'R{rb+1}':(ox-9,oy+11,90),f'R{rb+2}':(ox+2,oy-7,90),
  f'C{cb+8}':(ox-13,oy-3,90),f'C{cb+9}':(ox-13,oy+1,90)})
pos.update({r:(*xy,0) for r,xy in MOUNTING_HOLES_MM.items()})
cellrefs={f'U3','L2'}|{f'C{i}' for i in range(101,111)}|{f'R{i}' for i in range(101,108)}|{'D101','D102','JP101','TP101','TP102'}
assert set(g.fps)==set(pos)|cellrefs,(set(g.fps)-(set(pos)|cellrefs))
for r,xyz in pos.items():g.place(r,*xyz)
for f in g.fps.values():
 f.Reference().SetLayer(p.F_Fab);f.Value().SetVisible(False)
 for pad in f.Pads():pad.SetZoneConnection(p.ZONE_CONNECTION_FULL)
for text,x,y in [('INTERNAL USB CAN / PWM PROTOTYPE',57,95),('BATTERY IN',14,84),('GND 5V PWM',38,76),('CAN G H L',48,5),('CAN USB',75,21),('PWM USB',102,21),('SERVOS SIGNAL OFF IS NOT POWER OFF',49,89)]:g.text(text,x,y,.8)
sheet=dest/'robot_io.kicad_sch'
if sheet.exists():
 ids={r:u for u,r in re.findall(r'\(uuid ([^)]*)\)\s+\(property "Reference" "([^\"]+)"',sheet.read_text())}
 if set(ids)==set(g.fps):
  for r,f in g.fps.items():f.SetPath(p.KIID_PATH('/'+ids[r]))
out=dest/'robot_io.kicad_pcb'
def save():
 tmp=out.with_name('robot_io.routing-tmp.kicad_pcb');p.SaveBoard(str(tmp),b);tmp.replace(out)
save()
# Withhold zones during candidate trace routing, then restore/refill and run
# native DRC. This router does not qualify clearances or impedance by itself.
zones=list(b.Zones())
for z in zones:b.Remove(z)
fx=IndexedFixer(b);evidence=[]
def route_timeout(signum,frame):raise TimeoutError('candidate route time budget')
signal.signal(signal.SIGALRM,route_timeout)
fanouts={}
for r in ('U1','U2'):
 for pad in g.fps[r].Pads():
  if pad.GetNetname().startswith('NC_'):continue
  num=int(pad.GetNumber());xy=p.ToMM(pad.GetPosition())
  dx,dy=(-1.2,0) if num<=12 else (0,1.2) if num<=24 else (1.2,0) if num<=36 else (0,-1.2)
  fanouts[tuple(round(v,5) for v in xy)]=(xy,(xy[0]+dx,xy[1]+dy),pad.GetNetname())
for pad in g.fps['U7'].Pads():
 if pad.GetNetname().startswith('NC_'):continue
 num=int(pad.GetNumber());xy=p.ToMM(pad.GetPosition());dx=-1.2 if num<=7 else 1.2
 fanouts[tuple(round(v,5) for v in xy)]=(xy,(xy[0]+dx,xy[1]),pad.GetNetname())
fanout_paths={}
#0.4/0.2mm vias let these0.5mm-pitch signal-level supply pins escape without
# blocking adjacent clock/reset traces. Alternate depths separate the via pads.
for r in ('U1','U2'):
 for pin in ('1','8','9','23','24','35','36','47','48'):
  pad=next(q for q in g.fps[r].Pads() if q.GetNumber()==pin);a=p.ToMM(pad.GetPosition());x,y=a
  d=1.8 if pin in ('9','24','36','48') else 1.2
  num=int(pin);q=(x-d,y) if num<=12 else (x,y+d) if num<=24 else (x+d,y) if num<=36 else (x,y-d)
  key=tuple(round(v,5) for v in a);fanout_paths[key]=[a,q];fanouts[key]=(a,q,pad.GetNetname())
created_fanouts=set()
def fanout(n,xy):
 key=tuple(round(v,5) for v in xy)
 if key not in fanouts:return xy
 a,c,net=fanouts[key]
 if net!=n:return xy
 if key not in created_fanouts:
  path=fanout_paths.get(key,[a,c])
  if not all(fx.free(p.F_Cu,n,u[0]+(v[0]-u[0])*k/24,u[1]+(v[1]-u[1])*k/24,.09) for u,v in zip(path,path[1:]) for k in range(25)):return xy
  g.track(n,path,.18);fx._index=None;created_fanouts.add(key)
 return c

# Reserve every fine-pitch escape before routing can block a later neighbor.
for a,c,n in fanouts.values():fanout(n,a)
reserved_power=set()
for r in ('U1','U2'):
 for pin in ('1','8','9','23','24','35','36','47','48'):
  pad=next(q for q in g.fps[r].Pads() if q.GetNumber()==pin);n=pad.GetNetname();a=p.ToMM(pad.GetPosition());q=fanout(n,a)
  if all(fx.free(L,n,*q,.2) for L in (p.F_Cu,p.In1_Cu,p.In2_Cu,p.B_Cu)):
   g.via(n,*q,.4,.2);fx._index=None;reserved_power.add((r,pin))
# Give OE and CAN-TX explicit layer transitions before other nets consume their
# escape corridors. These slow controls can then join on the bottom layer.
for f in g.fps.values():
 for pad in f.Pads():
  n=pad.GetNetname()
  if n not in ('SERVO_OE_N','CAN_TXD','V3_CAN_A','V3_PWM_A') or (f.GetReference(),pad.GetNumber()) in reserved_power:continue
  a=p.ToMM(pad.GetPosition());q=fanout(n,a)
  if f.GetReference()=='U1' and n=='CAN_TXD':
   q=(q[0],q[1]-1.0)
   if not all(fx.free(p.F_Cu,n,a[0]+(q[0]-a[0])*k/32,a[1]+(q[1]-a[1])*k/32,.09) for k in range(33)):continue
   g.track(n,[a,q],.18);fx._index=None
   key=tuple(round(v,5) for v in a);fanouts[key]=(a,q,n)
  if all(fx.free(L,n,*q,.3) for L in (p.F_Cu,p.In1_Cu,p.In2_Cu,p.B_Cu)):
   g.via(n,*q);fx._index=None

def route(n,a,c,w=.18,layers=('F','B')):
 if math.dist(a,c)<.001:return True
 a=fanout(n,a);c=fanout(n,c)
 if n in ('SERVO_OE_N','CAN_TXD','V3_CAN_A','V3_PWM_A'):layers=('B','F')
 signal.alarm(15)
 try:ok=fx.route(n,a,c,w=w,step=.15,win=4,layers=layers)
 except TimeoutError:ok=False
 finally:signal.alarm(0)
 evidence.append({'net':n,'a':a,'b':c,'routed':bool(ok)})
 print('route',n,a,c,ok,flush=True);save();return ok
def stitch(n,xy):
 x,y=xy
 for t in b.GetTracks():
  if t.GetClass()=='PCB_VIA' and math.dist(xy,p.ToMM(t.GetPosition()))<.65:return False
 if all(fx.free(L,n,x,y,.3) for L in (p.F_Cu,p.In1_Cu,p.In2_Cu,p.B_Cu)):
  g.via(n,x,y);fx._index=None;return True
 return False
# USB pair fanouts remain top-layer only, short and adjacent. Route failures
# remain visible. Differential impedance/skew requires final stackup review.
for prefix,mcu,esd,j in (('CAN','U1','U8','J1'),('PWM','U2','U9','J2')):
 for a,c,suffix in (('1','6','DP'),('3','4','DM')):
  g.track(f'USB_{prefix}_{suffix}',[g.pad(esd,a),g.pad(esd,c)],.18);fx._index=None
 for suffix,mpin,epin,outpin,jpin in (('DM','32','3','4','2'),('DP','33','1','6','3')):
  net=f'USB_{prefix}_{suffix}';route(net,g.pad(mcu,mpin),g.pad(esd,epin),.18,('F',));route(net,g.pad(esd,outpin),g.pad(j,jpin),.18,('F',))

power={'GND','VIN','V5_SERVO','V3_CAN','V3_PWM'}
for n in sorted({pad.GetNetname() for f in g.fps.values() for pad in f.Pads()}-power):
 if not n or n.startswith('NC_') or n.startswith('USB_') and n.endswith(('_DM','_DP')):continue
 if n in {'PWM_BST','PWM_COMP','PWM_CZ','PWM_EN','PWM_RT','PWM_SW','D102_A'}:continue
 pads=[pad for f in g.fps.values() for pad in f.Pads() if pad.GetNumber() and pad.GetNetname()==n]
 if len(pads)<2:continue
 done=[pads.pop(0)]
 while pads:
  _,i,a=min((math.dist(p.ToMM(q.GetPosition()),p.ToMM(d.GetPosition())),i,d) for i,q in enumerate(pads) for d in done)
  c=pads.pop(i)
  # Cell-local TPS tracks are already hand-laid; still complete every logical
  # connection here so changed series feedback trim cannot become disconnected.
  route(n,p.ToMM(a.GetPosition()),p.ToMM(c.GetPosition()),.18);done.append(c)
# Local SMD power and ground returns into dedicated continuous planes.
for f in g.fps.values():
 for pad in f.Pads():
  n=pad.GetNetname()
  if n not in power or pad.GetAttribute()!=p.PAD_ATTRIB_SMD:continue
  if f.GetReference() in cellrefs or (f.GetReference(),pad.GetNumber()) in reserved_power:continue
  x,y=p.ToMM(pad.GetPosition());x,y=fanout(n,(x,y))
  for d in (.8,1.1,1.5,2.0):
   connected=False
   for dx,dy in ((d,0),(-d,0),(0,d),(0,-d)):
    q=(x+dx,y+dy)
    if stitch(n,q) and route(n,(x,y),q,.22):connected=True;break
   if connected:break
# Stitch quiet ground beneath and just below the MCU bodies so top-side ground
# islands cannot remain connected only to an isolated IC lead.
for cx,cy in ((64,35),(92,35),(90,47)):
 for dx,dy in ((0,0),(.7,0),(-.7,0),(0,.7),(0,-.7),(1,1),(-1,-1)):
  if stitch('GND',(cx+dx,cy+dy)):break
# Collapse same-net duplicate router vias before native hole-clearance DRC.
kept=[];removed=[]
for via in list(b.GetTracks()):
 if via.GetClass()!='PCB_VIA':continue
 xy=p.ToMM(via.GetPosition())
 near=next((q for q in kept if q.GetNetname()==via.GetNetname() and math.dist(xy,p.ToMM(q.GetPosition()))<.55),None)
 if near:
  qxy=p.ToMM(near.GetPosition());net=via.GetNetname()
  removed.append(via);b.Remove(via)
  if math.dist(xy,qxy)>.001:
   for layer in ('F','B'):g.track(net,[xy,qxy],.25,layer)
 else:kept.append(via)
for z in zones:b.Add(z)
def rect(n,layer,a,c,d,e,priority=0):g.zone(n,layer,[(a,c),(d,c),(d,e),(a,e)],priority,.25)
rect('GND','In1',.5,.5,111.5,99.5)
rect('GND','F',.5,.5,111.5,99.5)
rect('GND','B',.5,.5,111.5,99.5)
rect('VIN','In2',3,47,25,84)
rect('VIN','In2',7,27,16,56,1)
rect('V5_SERVO','In2',24,5,42,45)
rect('V5_SERVO','In2',25,45,42,60)
rect('V5_SERVO','In2',25,60,79,74)
rect('V3_CAN','In2',44,10,78,57)
rect('V3_PWM','In2',79,10,109,58)
# Explicit output power bridge uses several parallel vias into a broad layer.
for net,points in [('V5_SERVO',[(x,y) for x in (28,30,32,34) for y in (23,25)]),('GND',[(6,67),(6,69),(52,81),(78,83),(108,91)])]:
 for x,y in points:g.via(net,x,y)
save()
# Native zone refill is deliberately run in a fresh KiCad process below.
import subprocess
subprocess.run(['python3',str(root/'source/fabrication/refill_drc.py'),str(out),str(dest.parent/'drc.rpt')],check=True)
(dest.parent/'routing-evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
subprocess.run(['python3',str(root/'source/generator/finalize_robot_io.py')],check=True)
for ext in ('kicad_pro','kicad_prl'):(dest/('robot_io.routing-tmp.'+ext)).unlink(missing_ok=True)
print('Saved',out,'failed routes',sum(not q['routed'] for q in evidence),flush=True)
