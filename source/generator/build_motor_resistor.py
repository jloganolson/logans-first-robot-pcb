"""Derive the resistor-clamp development cell without editing frozen sources."""
import hashlib,json,re,shutil
from pathlib import Path
import pcbnew as p
from cells import Board
from motor_resistor import PARTS,REMOVED_REFS

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'revisions/motor-addon/kicad/motor_supply.kicad_pcb'
DEST=ROOT/'revisions/motor-resistor/kicad';DEST.mkdir(parents=True,exist_ok=True)
shutil.copytree(SOURCE.parent/'Robot_PDB.pretty',DEST/'Robot_PDB.pretty',dirs_exist_ok=True)
profile_bytes=SOURCE.with_suffix('.kicad_pro').read_bytes()
b=p.LoadBoard(str(SOURCE));g=Board.__new__(Board)
g.b,g.nets,g.zones,g.parts=b,{},[],{s['ref']:s for s in PARTS}
dead=[];removed=[]
def remove(item):dead.append(item);b.Remove(item)
def inside(q):
    x,y=q;return 40<=x<=55 and 64<=y<=80
for f in list(b.GetFootprints()):
    if f.GetReference() in REMOVED_REFS:remove(f)
g.fps={f.GetReference():f for f in b.GetFootprints()}
for t in list(b.GetTracks()):
    n=t.GetNetname();points=[tuple(p.ToMM(q)) for q in (t.GetStart(),t.GetEnd())]
    if n in ('Q1_G','U1_VCAP') or (n in ('+24V','MOTOR_BUS','GND') and all(inside(q) for q in points)):
        removed.append(dict(net=n,points_mm=points,kind=t.GetClass(),layer=t.GetLayer()))
        remove(t)
    elif n=='+24V':t.SetNet(g.net('MOTOR_BUS'))
for z in b.Zones():
    if z.GetNetname()=='+24V':z.SetNet(g.net('MOTOR_BUS'))
for ref,f in g.fps.items():
    s=g.parts[ref];f.SetValue(s['value'])
    for q in f.Pads():
        n=s['pins'].get(q.GetNumber())
        if ref=='Q4' and not q.GetNumber() and q.IsOnLayer(p.F_Cu):n='DUMP_LOW'
        q.SetNet(g.net(n)) if n else q.SetNetCode(0)
        q.SetZoneConnection(p.ZONE_CONNECTION_FULL)
for d in list(b.GetDrawings()):remove(d)
g.outline(112,100)
# The continuous shared output replaces the ideal-diode isolation gap. Existing
# higher-priority switch-node/sense/dump zones remain authoritative locally.
for layer in ('F','B'):
    g.zone('MOTOR_BUS',layer,[(30,53),(110,53),(110,96),(30,96)],5,.5,minw=.8)
for text,x,y,size in (
    ('MOTOR SUPPLY DEVELOPMENT - NOT QUALIFIED',57,98,.8),
    ('22V34 BUCK / AUTONOMOUS RESISTOR CLAMP',82,24,.8),
    ('INPUT',48,4,.8),('LEFT MOTOR',62,96,.8),('RIGHT MOTOR',83,96,.8),
    ('BRAKE R 3R3',101,92,.8),('THERMAL NC',58,24,.8)):
    g.text(text,x,y,size)
sheet=(DEST/'motor_resistor.kicad_sch').read_text()
ids={r:u for u,r in re.findall(r'\(uuid ([^)]*)\)\s+\(property "Reference" "([^"]+)"',sheet)}
assert set(ids)==set(g.fps)==set(g.parts)
for ref,f in g.fps.items():f.SetPath(p.KIID_PATH('/'+ids[ref]))
shutil.copyfile(SOURCE.parent/'fp-lib-table',DEST/'fp-lib-table')
profile=DEST/'motor_resistor.kicad_pro';profile.write_bytes(profile_bytes)
out=DEST/'motor_resistor.kicad_pcb'
p.ZONE_FILLER(b).Fill(b.Zones())
try:p.SaveBoard(str(out),b)
finally:profile.write_bytes(profile_bytes)
(DEST.parent/'build-evidence.json').write_text(json.dumps(dict(
    source=str(SOURCE.relative_to(ROOT)),source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    board_sha256=hashlib.sha256(out.read_bytes()).hexdigest(),
    removed_references=sorted(REMOVED_REFS),removed_ideal_tracks=removed,
    shared_output_net='MOTOR_BUS',parts=len(PARTS),
    disposition='DEVELOPMENT; measured voltage/energy/current/thermal qualification remains HELD'),indent=2)+'\n')
print('Saved',out,'parts',len(PARTS),'removed ideal tracks',len(removed),flush=True)
