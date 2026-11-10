"""Canonical final geometry tidy after the v0.6 integration stages."""
from pathlib import Path
import pcbnew as p
root=Path(__file__).resolve().parents[2];path=root/'revisions/v0.6/kicad/robot_pdb.kicad_pcb';b=p.LoadBoard(str(path));dead=[];rule_seen=False
for z in list(b.Zones()):
 remove=False
 if z.GetIsRuleArea():
  if rule_seen:remove=True
  rule_seen=True
 if z.GetNetname()=='GND' and z.GetLayer()==p.F_Cu:
  bb=z.Outline().BBox();x,y=p.ToMM(bb.GetOrigin())
  if 40<x<42 and 56<y<58:remove=True
 if remove:dead.append(z);b.Remove(z)
for t in list(b.GetTracks()):
 if t.GetNetname()=='DXL330_DATA' and t.GetClass()=='PCB_TRACK' and p.ToMM(t.GetLength())<.05:dead.append(t);b.Remove(t)
 if t.GetNetname() in ('USB_DP','USB_DM') and t.GetClass()=='PCB_TRACK':t.SetWidth(p.FromMM(.2))
for t in b.GetTracks():
 if t.GetClass()=='PCB_TRACK' and t.GetLayer() in (p.F_Cu,p.B_Cu) and p.ToMM(t.GetWidth())<.16:t.SetWidth(p.FromMM(.16))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(path),b)
