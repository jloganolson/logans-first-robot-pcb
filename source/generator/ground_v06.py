from pathlib import Path
import math
import pcbnew as p
from indexed_fixer import IndexedFixer
from cells import Board
root=Path(__file__).resolve().parents[2];path=root/'revisions/v0.6/kicad/robot_pdb.kicad_pcb';b=p.LoadBoard(str(path));g=Board.__new__(Board);g.b=b;g.nets={};g.zones=[];dead=[]
zones=list(b.Zones())
for z in zones:b.Remove(z)
fx=IndexedFixer(b)
for xy in [(21.8625,61),(24.2,58.375)]:
 candidates=[(xy[0]+dx*.4,xy[1]+dy*.4) for dx in range(-8,9) for dy in range(-8,9)]
 candidates.sort(key=lambda q:math.dist(q,xy))
 for q in candidates:
  if all(fx.free(L,'GND',*q,.3) for L in (p.F_Cu,p.In1_Cu,p.In2_Cu,p.B_Cu)) and fx.route('GND',xy,q,w=.25,step=.1,win=1,layers=('F',)):
   g.via('GND',*q,.6,.3);fx._index=None;print('ground island connected',xy,q,flush=True);break
 else:raise RuntimeError('No GND connection')
for z in zones:b.Add(z)
for t in list(b.GetTracks()):
 if t.GetClass()=='PCB_VIA' and t.GetNetname()=='DXL330_DATA' and math.dist(p.ToMM(t.GetPosition()),(182.6438,95.2891))<.01:dead.append(t);b.Remove(t)
for d in list(b.GetDrawings()):
 if isinstance(d,p.PCB_TEXT) and d.GetText() in ('PACK A','PACK B','MOTORS','C4'):
  dead.append(d);b.Remove(d)
 if isinstance(d,p.PCB_TEXT) and d.GetText()=='EXTERNAL DPST - 12AWG':d.SetPosition(p.VECTOR2I(p.FromMM(21),p.FromMM(78)))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(path),b);b=p.LoadBoard(str(path));p.WriteDRCReport(b,str(path.parent.parent/'drc.rpt'),p.EDA_UNITS_MILLIMETRES,True)
