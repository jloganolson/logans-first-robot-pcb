"""Build the v0.5 review PCB from the checked-in v0.4.1 board using KiCad 7."""
import os
import re
from pathlib import Path
import shutil
import pcbnew as pcb
from rev05 import PARTS
from cells import Board

root = Path(__file__).resolve().parents[2]
dest = root/'revisions/v0.5/kicad'
base = root/'kicad'
b = pcb.LoadBoard(str(base/'robot_pdb.kicad_pcb'))
geom = Board.__new__(Board)
geom.b, geom.nets, geom.zones = b, {}, []
fp = {f.GetReference():f for f in b.GetFootprints()}
spec = {p['ref']:p for p in PARTS}
detached = []
def remove(item):
    detached.append(item)
    b.Remove(item)

def place(ref,x,y,rot=None):
    fp[ref].SetPosition(pcb.VECTOR2I(pcb.FromMM(x),pcb.FromMM(y)))
    if rot is not None:
        fp[ref].SetOrientationDegrees(rot)

# Keep the populated sockets nearest the incoming data paths. Their original
# pads provided the layer transition at the last XL430 connector.
for old in ('J301','J302','J401','J402'):
    remove(fp.pop(old))
for old,new in [('J303','J301'),('J304','J302'),('J403','J401')]:
    fp[new]=fp.pop(old)
    fp[new].SetReference(new)
for t in list(b.GetTracks()):
    net=t.GetNetname()
    ends=[pcb.ToMM(t.GetStart()),pcb.ToMM(t.GetEnd())]
    xmax=max(x for x,y in ends)
    ymin=min(y for x,y in ends)
    if t.GetClass()=='PCB_VIA' and net=='VIN' and xmax<36 and ymin>=65 and ymin<=67:
        remove(t)
    elif ymin>99 and ((net=='DXL330_DATA' and xmax<=96.601) or
                    (net=='DXL430_DATA' and xmax<=141.601 and t.GetLayer()==pcb.In2_Cu)):
        remove(t)
    elif net in ('GND','VIN') and xmax<33 and max(y for x,y in ends)>64.5 and t.GetClass()=='PCB_TRACK':
        remove(t)

for ref in ('J4','SW1'):
    lib,name=spec[ref]['fp'].split(':')
    libdir=(dest if lib=='Robot_PDB' else Path(os.environ.get('KICAD7_FOOTPRINT_DIR','/usr/share/kicad/footprints')))/(lib+'.pretty')
    f=pcb.FootprintLoad(str(libdir),name)
    f.SetReference(ref)
    f.SetFPID(pcb.LIB_ID(lib,name))
    f.Value().SetVisible(False)
    b.Add(f)
    fp[ref]=f
place('SW1',25,82.35)
place('J1',58,94,180)
place('J4',79,94,180)
place('J3',52.5,67)
place('C3',18.6,44.8,0)
place('C4',6,43,-90)
place('TP1',5,55)
place('C5',12,62)
for ref in ('J1','J4','SW1','J301','J302','J401'):
    fp[ref].SetValue(spec[ref]['value'])
    for pad in fp[ref].Pads():
        if pad.GetNumber():
            pad.SetNet(geom.net(spec[ref]['pins'][pad.GetNumber()]))
            if ref in ('J1','J4','SW1'):
                pad.SetZoneConnection(pcb.ZONE_CONNECTION_FULL)

# Each battery has its own heavy copper corridor before the contacts.
# The two routes cross on different layers. SW1 has paired tails per terminal.
def pour(net,layer,points,priority=8):
    geom.zone(net,layer,points,prio=priority,clearance=.6,minw=1)
a=[(7,96),(20,96),(46,82),(55,82),(55,96),(51,98),(22,107.5),(7,107.5)]
c=[(25,96),(46,96),(66,91.5),(76,91.5),(76,98),(49,107.5),(25,107.5)]
pour('PACK_A_POS','B',a)
pour('PACK_B_POS','F',c)
# Reconnect the original two fuse feed groups on both outer layers. The
# bottom corridor runs beside the input protection stage; keep In1 as ground.
bus=[(4,33),(26,29),(28,36),(36,33),(36,40),(22,43),(14,48),
     (14,62),(37,62),(37,73),(5,73),(2,68),(2,36)]
pour('VBAT','B',bus)
pour('VBAT','F',[(2,33),(22,30),(28,32),(27,40),(8,41),(8,67),(36,66),(36,73),(1,73),(1,33)])
# Bring the relocated bulk pads into the VIN/GND inner planes via local arrays.
for ref in ('C3','C4','C5','TP1'):
    for p in fp[ref].Pads():
        x,y=pcb.ToMM(p.GetPosition())
        net=p.GetNetname()
        offsets=[(-1.5,-.9),(0,-.9),(1.5,-.9),(-1.5,.9),(0,.9),(1.5,.9)] if ref in ('C3','C4') else [(0,0)]
        for dx,dy in offsets:
            # SMD via fanout outside paste; connect the fanout with short tracks.
            yy=y+dy+(3.5 if p.GetNumber()=='2' else -3.5) if len(offsets)>1 else y+1.35
            geom.track(net,[(x,y),(x+dx,yy)],.55)
            geom.via(net,x+dx,yy,d=.7,drill=.35)
# Re-stitch the protected input at the drain before it reaches the new bus.
for x in (25.5,27,28.5,30):
    for y in (63,64.4):
        geom.via('VIN',x,y)
# Extend the Thor output from its existing converter output pour to J3.2.
pour('+24V','F',[(36,62),(50,62),(50,69),(36,69)],6)

for d in list(b.GetDrawings()):
    if not isinstance(d,pcb.PCB_TEXT):
        continue
    s=d.GetText()
    if s.isdigit() or s in ('BATTERY IN','8S / 33.6V MAX','XL330 SERVOS 5V','XL430 10.8V','JETSON THOR 24V'):
        remove(d)
    elif s=='ROBOT PDB v0.4 REVIEW':
        d.SetText('ROBOT PDB v0.5 REVIEW')
for ref,x,y in [('J1',54,89.5),('J4',75,89.5),('SW1',34,82)]:
    fp[ref].Reference().SetPosition(pcb.VECTOR2I(pcb.FromMM(x),pcb.FromMM(y)))
for label,x,y in [('PACK A',55,87),('PACK B',76,87),('8S / 33.6V MAX',65,82),('XL330 5V',99,97),
                  ('XL430 10.8V',139,97),('THOR 24V',49,83),('PACK SWITCH',34,85)]:
    geom.text(label,x,y,1)
shutil.copyfile(base/'robot_pdb.kicad_pro',dest/'robot_pdb.kicad_pro')
table=(base/'fp-lib-table').read_text().rstrip()
(dest/'fp-lib-table').write_text(table[:-1]+'  (lib (name "Fuse")(type "KiCad")(uri "${KICAD7_FOOTPRINT_DIR}/Fuse.pretty")(options "")(descr ""))\n  (lib (name "Robot_PDB")(type "KiCad")(uri "${KIPRJMOD}/Robot_PDB.pretty")(options "")(descr "Review switch footprint"))\n)\n')
# Link the board footprints to the exported sheet for native KiCad cross-probing.
sheet=(dest/'robot_pdb.kicad_sch').read_text()
symbols=dict((ref,uid) for uid,ref in re.findall(
    r'\(in_bom (?:yes|no)\) \(on_board yes\) \(dnp no\)\s+\(uuid ([^)]*)\)\s+\(property "Reference" "([^"]+)"',sheet))
assert symbols.keys()==fp.keys()
for ref,f in fp.items():
    f.SetPath(pcb.KIID_PATH('/'+symbols[ref]))
out=dest/'robot_pdb.kicad_pcb'
pcb.SaveBoard(str(out),b)
b=pcb.LoadBoard(str(out))
pcb.ZONE_FILLER(b).Fill(b.Zones())
pcb.SaveBoard(str(out),b)
pcb.WriteDRCReport(b,str(dest.parent/'drc.rpt'),pcb.EDA_UNITS_MILLIMETRES,True)
