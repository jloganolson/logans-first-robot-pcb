"""Final v0.6 mechanical/copper and marking tidy, followed by native DRC."""
from pathlib import Path
import pcbnew as p
from cells import Board
from indexed_fixer import IndexedFixer
root=Path(__file__).resolve().parents[2];path=root/'revisions/v0.6/kicad/robot_pdb.kicad_pcb';b=p.LoadBoard(str(path));g=Board.__new__(Board);g.b=b;g.nets={};g.zones=[];dead=[]
def remove(x):dead.append(x);b.Remove(x)
for t in list(b.GetTracks()):
 x,y=p.ToMM(t.GetPosition())
 if t.GetNetname() in ('VIN','GND') and 28<x<48 and 76<y<99:remove(t)
 elif t.GetNetname()=='DXL330_DATA' and t.GetLayer()==p.In2_Cu:remove(t)
for ref,xy in [('C3',(35.5,81)),('C4',(40,94))]:
 f=b.FindFootprintByReference(ref);f.SetPosition(p.VECTOR2I(*[p.FromMM(v) for v in xy]))
 for pad in f.Pads():
  x,y=p.ToMM(pad.GetPosition());n=pad.GetNetname()
  for dx in (-1.5,0,1.5):
   yy=y+(-2.6 if pad.GetNumber()=='1' else 2.6);g.track(n,[(x,y),(x+dx,yy)],.55);g.via(n,x+dx,yy,.7,.35)
# Ground plane connections in the small controller islands; ignore zone outlines when
# choosing stitches, because KiCad's fill computes clearance to the actual pad/via.
zones=list(b.Zones())
for z in zones:b.Remove(z)
fx=IndexedFixer(b)
for x,y in [(21.8,61),(24,58.6)]:
 print('ground stitch',x,y,[fx.free(L,'GND',x,y,.3) for L in (p.F_Cu,p.In1_Cu,p.In2_Cu,p.B_Cu)],flush=True)
 if all(fx.free(L,'GND',x,y,.3) for L in (p.F_Cu,p.In1_Cu,p.In2_Cu,p.B_Cu)):
  g.via('GND',x,y,.6,.3);fx._index=None
for z in zones:b.Add(z)
# Remove outdated power-port text. Preserve component outlines except the obsolete
# retained connector artwork whose mask overlaps changed power wires.
for d in list(b.GetDrawings()):
 if isinstance(d,p.PCB_TEXT) and ('BATT PASS-THRU' in d.GetText() or d.GetText()=='- / +'):remove(d)
for ref in ('C3','C4','J3'):
 for d in list(b.FindFootprintByReference(ref).GraphicalItems()):
  if d.GetLayer()==p.F_SilkS:d.SetLayer(p.F_Fab)
# Explicit usable terminal labels on silk; reference identifiers remain on fab.
for s,x,y in [('J1 BAT A + / -',55,88),('J4 BAT B + / -',76,88),('F1 MOTOR 30A',6,29),('F2 LOGIC 30A',35,23),('J2 MOTOR - / +',6,21),('C3',31,73),('C4',37,102)]:
 g.text(s,x,y,.8,rot=90 if s.startswith('F') else 0)
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(path),b);b=p.LoadBoard(str(path));p.WriteDRCReport(b,str(path.parent.parent/'drc.rpt'),p.EDA_UNITS_MILLIMETRES,True)
