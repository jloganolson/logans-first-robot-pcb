"""Derive a held simple motor cell from the audited motor-addon converter.

Run gen_sch with CIRCUIT=motor_simple, PROJ=motor_simple first. This preserves
the buck's critical routing and shunt Kelvin connections; it does not release
the new 24V operating point or establish safe motor deceleration.
"""
import hashlib, json, re, shutil
from pathlib import Path
import pcbnew as p
from cells import Board
from motor_simple import PARTS

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'revisions/motor-addon/kicad/motor_supply.kicad_pcb'
DEST = ROOT/'revisions/motor-simple/kicad'
DEST.mkdir(parents=True, exist_ok=True)
source_profile = SOURCE.with_suffix('.kicad_pro').read_bytes()
shutil.copytree(SOURCE.parent/'Robot_PDB.pretty', DEST/'Robot_PDB.pretty', dirs_exist_ok=True)
b = p.LoadBoard(str(SOURCE))
g = Board.__new__(Board)
g.b, g.nets, g.zones, g.parts = b, {}, [], {s['ref']:s for s in PARTS}
dead = []
def remove(item):
    dead.append(item)
    b.Remove(item)
for f in list(b.GetFootprints()):
    if f.GetReference() not in g.parts:
        remove(f)
g.fps = {f.GetReference():f for f in b.GetFootprints()}
for d in list(b.GetDrawings()):
    remove(d)
kept, discarded = [], []
for t in list(b.GetTracks()):
    net = t.GetNetname()
    points = [tuple(p.ToMM(q)) for q in (t.GetStart(), t.GetEnd())]
    keep = (net.startswith('T_') or net in ('M_SENSE','D3_A') or net.startswith('CAN_') or
            (net in ('GND', 'VIN', '+24V') and all(x <= 43.0 for x,y in points)))
    # T_EN used to run to the removed thermal transistor as well as its
    # surviving converter/disable-jumper connections.
    if net == 'T_EN':
        keep = (t.GetClass() != 'PCB_VIA' and t.GetLayer() == p.F_Cu and
                all(x <= 30.75 for x,y in points))
    if net == 'GND' and all(40 < x < 44 and y > 70 for x,y in points):
        keep = False
    entry = dict(net=net, kind=t.GetClass(), points_mm=points,
                 width_mm=p.ToMM(t.GetWidth()), layer=t.GetLayer())
    (kept if keep else discarded).append(entry)
    if not keep:
        remove(t)
    elif net == '+24V':
        t.SetNet(g.net('MOTOR_BUS'))
for z in list(b.Zones()):
    net = z.GetNetname()
    if net not in ('GND', 'VIN', '+24V', 'M_SENSE', 'T_SW'):
        remove(z)
    elif net == '+24V':
        z.SetNet(g.net('MOTOR_BUS'))
for ref, f in g.fps.items():
    spec = g.parts[ref]
    f.SetValue(spec['value'])
    for pad in f.Pads():
        net = spec['pins'].get(pad.GetNumber())
        pad.SetNet(g.net(net)) if net else pad.SetNetCode(0)
        pad.SetZoneConnection(p.ZONE_CONNECTION_FULL)
g.outline(112,100)
for layer in ('F','B'):
    g.zone('MOTOR_BUS',layer,[(30,53),(110,53),(110,96),(30,96)],5,.5,minw=.8)
# The surviving input TVS needs a new explicit local ground transition after
# removal of the old thermal/controller ground fanout. This is not via-in-pad.
g.track('GND',[g.pad('D1','2'),(59.4,21.5)],.8)
g.via('GND',59.4,21.5,.8,.4)
g.track('GND',[g.pad('TP2','1'),(59.4,15),(59.4,21.5)],.4)
# Broad power spreader transitions; these support copper distribution but are
# not an independent ampacity or temperature certification.
for x in (48,49.2,50.4,51.6):
    for y in (75,76.2,77.4):
        g.via('MOTOR_BUS',x,y,.7,.35)
for x,y in ((60,30),(70,30),(80,30),(90,30),(100,30),(60,50),(80,50),(100,50),(108,80)):
    g.via('GND',x,y,.7,.35)
for text,x,y,size in (
    ('MOTOR SUPPLY DEVELOPMENT - NOT QUALIFIED',57,98,.8),
    ('24V NOM / NO BRAKE ENERGY SINK',76,26,.8),
    ('FUSED + REVERSE-PROTECTED INPUT',57,3,.8),
    ('LEFT MOTOR',62,96,.8),('RIGHT MOTOR',83,96,.8),
    ('CAN IN',72,5,.8),('CAN L',86,5,.8),('CAN R',100,5,.8)):
    g.text(text,x,y,size)
sheet = (DEST/'motor_simple.kicad_sch').read_text()
ids = {r:u for u,r in re.findall(r'\(uuid ([^)]*)\)\s+\(property "Reference" "([^"]+)"',sheet)}
assert set(ids) == set(g.fps)
for ref,f in g.fps.items():
    f.SetPath(p.KIID_PATH('/'+ids[ref]))
shutil.copyfile(SOURCE.parent/'fp-lib-table', DEST/'fp-lib-table')
profile = DEST/'motor_simple.kicad_pro'
profile.write_bytes(source_profile)
out = DEST/'motor_simple.kicad_pcb'
p.ZONE_FILLER(b).Fill(b.Zones())
try:
    p.SaveBoard(str(out),b)
finally:
    profile.write_bytes(source_profile)
(DEST.parent/'build-evidence.json').write_text(json.dumps(dict(
    source=str(SOURCE.relative_to(ROOT)),source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    board_sha256=hashlib.sha256(out.read_bytes()).hexdigest(),
    retained_tracks=kept,removed_tracks=discarded,
    disposition='DEVELOPMENT ONLY; motor coast/regen and voltage qualification HELD'),indent=2)+'\n')
print('Saved',out,'parts',len(g.fps),'retained tracks',len(kept),'removed tracks',len(discarded))
