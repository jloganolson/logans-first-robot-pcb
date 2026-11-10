from pathlib import Path
import math,json
import pcbnew as p
from indexed_fixer import IndexedFixer
from cells import Board
root=Path(__file__).resolve().parents[2];path=root/'revisions/v0.6/kicad/robot_pdb.kicad_pcb';b=p.LoadBoard(str(path));g=Board.__new__(Board);g.b=b;g.nets={};g.zones=[]
zones=list(b.Zones())
for z in zones:b.Remove(z)
fx=IndexedFixer(b);added=[]
for n,points,d,dr in [('VIN',[(x,y) for x in (25.5,26.7,27.9,29.1,30.3,31.5) for y in (63,64.2,65.4)],.7,.35),('GND',[(14.7,56.7),(13.5,56.7),(14.1,52.3)],.7,.35)]:
 for x,y in points:
  holes=[t for t in b.GetTracks() if t.GetClass()=='PCB_VIA']
  if any(math.dist(p.ToMM(t.GetPosition()),(x,y))<(p.ToMM(t.GetDrill())+dr)/2+.25 for t in holes):continue
  if all(fx.free(L,n,x,y,d/2) for L in (p.F_Cu,p.In1_Cu,p.In2_Cu,p.B_Cu)):
   g.via(n,x,y,d,dr);fx._index=None;added.append((n,x,y));print('added',n,x,y,flush=True)
for z in zones:b.Add(z)
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(path),b);b=p.LoadBoard(str(path));p.WriteDRCReport(b,str(path.parent.parent/'drc.rpt'),p.EDA_UNITS_MILLIMETRES,True)
(path.parent.parent/'power-stitches.json').write_text(json.dumps(added,indent=2))
