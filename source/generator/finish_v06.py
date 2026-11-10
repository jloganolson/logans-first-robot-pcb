"""Resolve v0.6 layout integration; run after build_v06.py."""
from pathlib import Path
import math
import pcbnew as p
from indexed_fixer import IndexedFixer
from cells import Board
import fixer
root=Path(__file__).resolve().parents[2];path=root/'revisions/v0.6/kicad/robot_pdb.kicad_pcb'
b=p.LoadBoard(str(path));g=Board.__new__(Board);g.b=b;g.nets={};g.zones=[];dead=[]
def remove(x):dead.append(x);b.Remove(x)
# Coalesce same-net closely spaced plated stitches left by independent route fanouts.
kept=[]
for v in list(b.GetTracks()):
 if v.GetClass()!='PCB_VIA':continue
 if any(v.GetNetname()==q.GetNetname() and math.dist(p.ToMM(v.GetPosition()),p.ToMM(q.GetPosition()))<.65 for q in kept):remove(v)
 else:kept.append(v)
# C3 body clearance: keep at least 0.5mm to adjacent connector courtyard.
f=b.FindFootprintByReference('C3');f.SetPosition(p.VECTOR2I(p.FromMM(40),p.FromMM(82)))
for t in list(b.GetTracks()):
 x,y=p.ToMM(t.GetPosition())
 if t.GetNetname() in ('VIN','GND') and 37<x<45 and 76<y<85:remove(t)
for pad in f.Pads():
 x,y=p.ToMM(pad.GetPosition());n=pad.GetNetname()
 for dx in (-1.5,0,1.5):
  yy=y+(-2.6 if pad.GetNumber()=='1' else 2.6);g.track(n,[(x,y),(x+dx,yy)],.55);g.via(n,x+dx,yy,.7,.35)
# Split servo connector now intersects an old inner signal. Reroute the affected span.
fixer.LAY['I2']=p.In2_Cu
fx=IndexedFixer(b)
for t in list(b.GetTracks()):
 if t.GetNetname()=='DXL330_DATA' and t.GetClass()=='PCB_TRACK' and t.GetLayer()==p.In2_Cu and t.HitTest(p.VECTOR2I(p.FromMM(154.5),p.FromMM(103)),p.FromMM(1.2)):
  # Obsolete unterminated stub; new F/B traces already connect both headers.
  remove(t);fx._index=None
# Restore the logic-feed connections to controller pins after rebuilding the power copper.
zones=list(b.Zones())
for z in zones:b.Remove(z)
fx=IndexedFixer(b)
for a,z in [((21.8625,61.95),(24.1375,60.05)),((21.8625,61.95),(23.775,64)),((24.1375,60.05),(27,56.2))]:
 print('logic route',a,z,flush=True);assert fx.route('VBAT_L',a,z,w=.4,step=.1,win=2,layers=('F',))
for z in zones:b.Add(z)
# Old disconnected VIN stitches from the moved bulk capacitor have no function.
for t in list(b.GetTracks()):
 x,y=p.ToMM(t.GetPosition())
 if t.GetClass()=='PCB_VIA' and t.GetNetname()=='VIN' and x<10 and 34<y<35:remove(t)
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(path),b)
b=p.LoadBoard(str(path));p.WriteDRCReport(b,str(path.parent.parent/'drc.rpt'),p.EDA_UNITS_MILLIMETRES,True)
print('saved',flush=True)
