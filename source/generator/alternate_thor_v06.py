"""Install exact stocked Coilcraft Thor inductor, updating native footprint and schematic links."""
from pathlib import Path
import os,re
import pcbnew as p
root=Path(__file__).resolve().parents[2];k=root/'revisions/v0.6/kicad';path=k/'robot_pdb.kicad_pcb';b=p.LoadBoard(str(path));old=b.FindFootprintByReference('L1');pos=old.GetPosition();rot=old.GetOrientationDegrees();b.Remove(old)
f=p.FootprintLoad(os.environ['KICAD7_FOOTPRINT_DIR']+'/Inductor_SMD.pretty','L_Coilcraft_XAL1510-103');b.Add(f);f.SetReference('L1');f.SetValue('10uH 22A 60V');f.SetPosition(pos);f.SetOrientationDegrees(rot);f.SetFPID(p.LIB_ID('Inductor_SMD','L_Coilcraft_XAL1510-103'));f.Reference().SetLayer(p.F_Fab);f.Value().SetVisible(False)
for q in f.Pads():q.SetNet(b.FindNet('T_SW' if q.GetNumber()=='1' else '+24V'))
sheet=(k/'robot_pdb.kicad_sch').read_text();symbols={ref:uid for uid,ref in re.findall(r'\(uuid ([^)]*)\)\s+\(property "Reference" "([^"]+)"',sheet)}
for f in b.GetFootprints():f.SetPath(p.KIID_PATH('/'+symbols[f.GetReference()]))
for d in b.GetDrawings():
 if isinstance(d,p.PCB_TEXT) and d.GetText()=='24V THOR':d.SetPosition(p.VECTOR2I(p.FromMM(65),p.FromMM(70)))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(path),b);b=p.LoadBoard(str(path));p.WriteDRCReport(b,str(path.parent.parent/'drc.rpt'),p.EDA_UNITS_MILLIMETRES,True)
